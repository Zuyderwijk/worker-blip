import os
import zipfile
import mimetypes
import shutil
import gc

import torch
from PIL import Image
import psutil

from lavis.models import load_model_and_preprocess
import runpod
from runpod.serverless.utils import rp_download, rp_cleanup
from runpod.serverless.utils.rp_validator import validate

from schemas import INPUT_SCHEMA

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Memory monitoring function
def log_memory_usage(stage=""):
    if torch.cuda.is_available():
        gpu_memory = torch.cuda.memory_allocated() / 1024**3
        gpu_reserved = torch.cuda.memory_reserved() / 1024**3
        print(f"🔍 {stage} - GPU Memory: {gpu_memory:.2f}GB allocated, {gpu_reserved:.2f}GB reserved")
    
    cpu_memory = psutil.virtual_memory().percent
    print(f"🔍 {stage} - CPU Memory: {cpu_memory:.1f}% used")

# Load the model and preprocessors - using faster, smaller model
print("🚀 Loading BLIP2 model...")
model, vis_processors, _ = load_model_and_preprocess(
    name="blip2_opt",
    model_type="caption_coco_opt2.7b",  # Smaller, faster model for better efficiency
    is_eval=True,
    device=DEVICE
)
log_memory_usage("Model loaded")

def caption_image(job):
    job_input = job.get("input", {})
    data_urls = job_input.get('data_urls')
    if not data_urls:
        single_url = job_input.get('data_url')
        if single_url:
            data_urls = [single_url]
        else:
            return {"error": "At least one of 'data_url' or 'data_urls' is required."}

    schema_input = {k: v for k, v in job_input.items() if k in INPUT_SCHEMA}
    for key in INPUT_SCHEMA:
        if key not in schema_input:
            schema_input[key] = None

    print("✅ SCHEMA INPUT BEFORE VALIDATE:", schema_input)

    validated = validate(schema_input, INPUT_SCHEMA)
    if 'errors' in validated:
        return {"error": validated['errors']}
    validated_input = validated['validated_input']

    captions = []

    for url in data_urls:
        try:
            input_path_data = rp_download.file(url)
            input_path = input_path_data["file_path"]
            mime_type, _ = mimetypes.guess_type(input_path)
            is_zip = mime_type == "application/zip"
        except Exception as e:
            return {"error": f"Failed to download or inspect file from URL: {url}. Error: {str(e)}"}

        images = []
        if is_zip:
            try:
                shutil.rmtree('/tmp', ignore_errors=True)
                with zipfile.ZipFile(input_path, 'r') as zip_ref:
                    zip_ref.extractall('/tmp')
                images = [os.path.join('/tmp', f) for f in os.listdir('/tmp')
                          if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
            except Exception as e:
                return {"error": f"Failed to unzip archive: {url}. Error: {str(e)}"}
        else:
            images = [input_path]

        # Process images in batches for better efficiency
        batch_size = validated_input.get('batch_size', 4)  # Use configurable batch size
        for i in range(0, len(images), batch_size):
            batch_images = images[i:i + batch_size]
            batch_tensors = []
            batch_paths = []
            
            # Prepare batch
            for image_path in batch_images:
                try:
                    mime_type, _ = mimetypes.guess_type(image_path)
                    if mime_type not in ["image/jpeg", "image/png", "image/jpg"]:
                        continue

                    image = Image.open(image_path).convert("RGB")
                    image_tensor = vis_processors["eval"](image).unsqueeze(0)
                    batch_tensors.append(image_tensor)
                    batch_paths.append(image_path)
                except Exception as e:
                    print(f"⚠️ Error preparing {image_path}: {str(e)}")
                    captions.append({
                        "image_path": image_path,
                        "caption": f"[ERROR: Failed to process image: {str(e)}]"
                    })
                    continue
            
            if not batch_tensors:
                continue
                
            # Process batch
            try:
                batch_tensor = torch.cat(batch_tensors, dim=0).to(DEVICE)
                
                with torch.no_grad():
                    # Use configurable generation parameters
                    batch_captions = model.generate({
                        "image": batch_tensor,
                        "prompt": validated_input.get('prompt', "a photo of"),
                        "num_beams": validated_input.get('num_beams', 3),
                        "max_length": validated_input.get('max_length', 50),
                        "min_length": validated_input.get('min_length', 5),
                        "repetition_penalty": 1.05
                    })

                for idx, caption in enumerate(batch_captions):
                    print(f"✅ Caption generated for {batch_paths[idx]}: {caption}")
                    captions.append({
                        "image_path": batch_paths[idx],
                        "caption": caption
                    })
                    
            except torch.cuda.OutOfMemoryError:
                # Fallback to individual processing if batch fails
                print("⚠️ Batch processing failed due to memory, falling back to individual processing")
                for idx, image_tensor in enumerate(batch_tensors):
                    try:
                        with torch.no_grad():
                            caption = model.generate({
                                "image": image_tensor.to(DEVICE),
                                "prompt": validated_input.get('prompt', "a photo of"),
                                "num_beams": validated_input.get('num_beams', 3),
                                "max_length": validated_input.get('max_length', 50),
                                "min_length": validated_input.get('min_length', 5),
                                "repetition_penalty": 1.05
                            })[0]

                        captions.append({
                            "image_path": batch_paths[idx],
                            "caption": caption
                        })
                    except Exception as e:
                        print(f"⚠️ Error processing {batch_paths[idx]}: {str(e)}")
                        captions.append({
                            "image_path": batch_paths[idx],
                            "caption": f"[ERROR: Failed to process image: {str(e)}]"
                        })
            except Exception as e:
                print(f"⚠️ Batch processing error: {str(e)}")
                # Fallback to individual processing
                for idx, image_tensor in enumerate(batch_tensors):
                    try:
                        with torch.no_grad():
                            caption = model.generate({
                                "image": image_tensor.to(DEVICE),
                                "prompt": validated_input.get('prompt', "a photo of"),
                                "num_beams": validated_input.get('num_beams', 3),
                                "max_length": validated_input.get('max_length', 50),
                                "min_length": validated_input.get('min_length', 5),
                                "repetition_penalty": 1.05
                            })[0]

                        captions.append({
                            "image_path": batch_paths[idx],
                            "caption": caption
                        })
                    except Exception as e:
                        print(f"⚠️ Error processing {batch_paths[idx]}: {str(e)}")
                        captions.append({
                            "image_path": batch_paths[idx],
                            "caption": f"[ERROR: Failed to process image: {str(e)}]"
                        })

        # Clean up memory after processing
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    gc.collect()
    log_memory_usage("After processing")
    
    rp_cleanup.clean(['/tmp'])
    return {"captions": captions}

runpod.serverless.start({"handler": caption_image})
