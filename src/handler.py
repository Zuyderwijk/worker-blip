import os
import zipfile
import mimetypes
import shutil

import torch
from PIL import Image

from lavis.models import load_model_and_preprocess
import runpod
from runpod.serverless.utils import rp_download, rp_cleanup
from runpod.serverless.utils.rp_validator import validate

from schemas import INPUT_SCHEMA

# Set up the device
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Load the BLIP model and preprocessors
model, vis_processors, _ = load_model_and_preprocess(
    name="blip_caption", model_type="base_coco", is_eval=True, device=DEVICE
)

def caption_image(job):
    job_input = job.get("input", {})
    data_urls = job_input.get('data_urls')
    if not data_urls:
        single_url = job_input.get('data_url')
        if single_url:
            data_urls = [single_url]
        else:
            return {"error": "At least one of 'data_url' or 'data_urls' is required."}

    # Validate only known fields and complete schema keys
    schema_input = {k: v for k, v in job_input.items() if k in INPUT_SCHEMA}
    for key in INPUT_SCHEMA:
        if key not in schema_input:
            schema_input[key] = None

    print("✅ SCHEMA INPUT BEFORE VALIDATE:", schema_input)

    validated = validate(schema_input, INPUT_SCHEMA)
    if 'errors' in validated:
        return {"error": validated['errors']}
    validated_input = validated['validated_input']

    min_len = 5 if validated_input.get("min_length") is None else validated_input["min_length"]
    max_len = 75 if validated_input.get("max_length") is None else validated_input["max_length"]

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

        for image_path in images:
            try:
                mime_type, _ = mimetypes.guess_type(image_path)
                if mime_type not in ["image/jpeg", "image/png", "image/jpg"]:
                    continue

                image = Image.open(image_path).convert("RGB")
                image_tensor = vis_processors["eval"](image).unsqueeze(0).to(DEVICE)

                with torch.no_grad():
                    caption = ' '.join(model.generate(
                        {"image": image_tensor},
                        max_length=max_len,
                        min_length=min_len
                    ))

                print(f"✅ Caption generated for {image_path}: {caption}")

                captions.append({
                    "image_path": image_path,
                    "caption": caption
                })

            except Exception as e:
                print(f"⚠️ Error processing {image_path}: {str(e)}")
                captions.append({
                    "image_path": image_path,
                    "caption": f"[ERROR: Failed to process image: {str(e)}]"
                })

    rp_cleanup.clean(['/tmp'])
    return {"captions": captions}

runpod.serverless.start({"handler": caption_image})
