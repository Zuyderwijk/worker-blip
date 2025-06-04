import os
import mimetypes
import gc
import time
from typing import Dict, Any, Optional

import torch
from PIL import Image
import runpod
from runpod.serverless.utils import rp_download, rp_cleanup
from runpod.serverless.utils.rp_validator import validate

from lavis.models import load_model_and_preprocess

# Optimized input schema for single image processing
INPUT_SCHEMA = {
    'data_url': {
        'type': str,
        'required': True,
        'description': 'Base64 encoded image data URL (data:image/...;base64,...)'
    },
    'prompt': {
        'type': str,
        'required': False,
        'default': 'a photo of',
        'description': 'Caption generation prompt'
    },
    'max_length': {
        'type': int,
        'required': False,
        'default': 40,
        'description': 'Maximum caption length (optimized for speed)'
    },
    'min_length': {
        'type': int,
        'required': False,
        'default': 8,
        'description': 'Minimum caption length'
    },
    'num_beams': {
        'type': int,
        'required': False,
        'default': 3,
        'description': 'Number of beams for beam search (max 3 for speed)'
    }
}

# Use faster, more efficient device detection
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"🔧 Using device: {DEVICE}")

# Memory monitoring (simplified for speed)
def log_memory_usage(stage: str = "") -> None:
    """Log GPU memory usage if available"""
    if torch.cuda.is_available():
        allocated = torch.cuda.memory_allocated() / 1024**3
        reserved = torch.cuda.memory_reserved() / 1024**3
        print(f"🔍 {stage} - GPU: {allocated:.2f}GB allocated, {reserved:.2f}GB reserved")

# Load optimized model for single image processing
print("🚀 Loading optimized BLIP2 model...")
start_time = time.time()

try:
    # Use the smallest, fastest BLIP2 variant for production
    model, vis_processors, _ = load_model_and_preprocess(
        name="blip2_opt",
        model_type="caption_coco_opt2.7b",  # Much faster and smaller model
        is_eval=True,
        device=DEVICE
    )
    
    # Optimize model for inference
    model.eval()
    if hasattr(model, 'half') and DEVICE.type == 'cuda':
        model = model.half()  # Use FP16 for faster inference
    
    load_time = time.time() - start_time
    print(f"✅ Model loaded and optimized in {load_time:.2f} seconds")
    log_memory_usage("Model loaded")
    
except Exception as e:
    print(f"❌ Failed to load model: {str(e)}")
    raise

def health_check() -> Dict[str, Any]:
    """Optimized health check"""
    try:
        return {
            "status": "healthy",
            "device": str(DEVICE),
            "cuda_available": torch.cuda.is_available(),
            "model_loaded": model is not None,
            "timestamp": time.time(),
            "gpu_memory_gb": torch.cuda.memory_allocated() / 1024**3 if torch.cuda.is_available() else 0
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

def process_single_image(job: Dict[str, Any]) -> Dict[str, Any]:
    """
    Optimized single image processing function
    
    Expected input format:
    {
        "input": {
            "data_url": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQ...",
            "prompt": "a photo of",
            "max_length": 40,
            "min_length": 8,
            "num_beams": 3
        }
    }
    """
    process_start = time.time()
    
    try:
        print(f"🚀 Processing job at {time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Validate input
        job_input = job.get("input", {})
        if not job_input:
            return {"error": "No input provided"}
        
        # Validate against schema
        validated = validate(job_input, INPUT_SCHEMA)
        if 'errors' in validated:
            print(f"❌ Validation errors: {validated['errors']}")
            return {"error": f"Validation failed: {validated['errors']}"}
        
        params = validated['validated_input']
        data_url = params['data_url']
        
        if not data_url or not data_url.startswith('data:image/'):
            return {"error": "Invalid data_url format. Expected: data:image/...;base64,..."}
        
        print(f"📥 Processing single image with params: max_length={params['max_length']}, num_beams={params['num_beams']}")
        
        # Download and process image
        download_start = time.time()
        try:
            input_path_data = rp_download.file(data_url)
            input_path = input_path_data["file_path"]
            download_time = time.time() - download_start
            print(f"⬇️ Downloaded in {download_time:.3f}s: {input_path}")
        except Exception as e:
            error_msg = f"Failed to download/decode image: {str(e)}"
            print(f"❌ {error_msg}")
            return {"error": error_msg}
        
        # Validate file type
        mime_type, _ = mimetypes.guess_type(input_path)
        if mime_type not in ["image/jpeg", "image/png", "image/jpg"]:
            error_msg = f"Unsupported image format: {mime_type}"
            print(f"❌ {error_msg}")
            return {"error": error_msg}
        
        # Process image
        try:
            # Load and preprocess image
            prep_start = time.time()
            image = Image.open(input_path).convert("RGB")
            
            # Resize large images for faster processing
            max_size = 512
            if max(image.size) > max_size:
                image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
                print(f"🔄 Resized image to {image.size} for faster processing")
            
            image_tensor = vis_processors["eval"](image).unsqueeze(0).to(DEVICE)
            prep_time = time.time() - prep_start
            print(f"🖼️ Image preprocessed in {prep_time:.3f}s")
            
            # Generate caption with optimized parameters
            gen_start = time.time()
            with torch.no_grad():
                # Clamp parameters for optimal performance
                max_length = min(params['max_length'], 50)  # Cap at 50 for speed
                num_beams = min(params['num_beams'], 3)     # Max 3 beams for speed
                
                caption = model.generate({
                    "image": image_tensor,
                    "prompt": params['prompt'],
                    "num_beams": num_beams,
                    "max_length": max_length,
                    "min_length": params['min_length'],
                    "repetition_penalty": 1.05,
                    "do_sample": False,  # Deterministic for consistency
                    "early_stopping": True  # Stop when EOS is generated
                })[0]
                
            gen_time = time.time() - gen_start
            print(f"🧠 Generated caption in {gen_time:.3f}s: '{caption}'")
            
            # Clear GPU cache immediately
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            process_time = time.time() - process_start
            print(f"✅ Total processing time: {process_time:.3f}s")
            
            return {
                "caption": caption,
                "processing_time": process_time,
                "model_info": {
                    "device": str(DEVICE),
                    "max_length": max_length,
                    "num_beams": num_beams
                }
            }
            
        except Exception as e:
            error_msg = f"Caption generation failed: {str(e)}"
            print(f"❌ {error_msg}")
            return {"error": error_msg}
            
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        print(f"❌ {error_msg}")
        return {"error": error_msg}
        
    finally:
        # Always cleanup
        try:
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            gc.collect()
            rp_cleanup.clean(['/tmp'])
            log_memory_usage("After cleanup")
        except Exception as cleanup_error:
            print(f"⚠️ Cleanup warning: {cleanup_error}")

def caption_image_legacy(job: Dict[str, Any]) -> Dict[str, Any]:
    """
    Legacy handler for backward compatibility with batch processing
    Converts batch requests to single image format
    """
    try:
        job_input = job.get("input", {})
        
        # Handle legacy batch format
        if 'data_urls' in job_input:
            data_urls = job_input['data_urls']
            if not data_urls:
                return {"error": "Empty data_urls array"}
            
            print(f"🔄 Legacy batch mode: processing {len(data_urls)} images sequentially")
            
            captions = []
            for i, data_url in enumerate(data_urls):
                print(f"📸 Processing image {i+1}/{len(data_urls)}")
                
                # Create single image job
                single_job = {
                    "input": {
                        "data_url": data_url,
                        "prompt": job_input.get('prompt', 'a photo of'),
                        "max_length": job_input.get('max_length', 40),
                        "min_length": job_input.get('min_length', 8),
                        "num_beams": job_input.get('num_beams', 3)
                    }
                }
                
                result = process_single_image(single_job)
                
                if 'error' in result:
                    captions.append({
                        "image_path": f"image_{i+1}",
                        "caption": f"[ERROR: {result['error']}]"
                    })
                else:
                    captions.append({
                        "image_path": f"image_{i+1}",
                        "caption": result['caption']
                    })
            
            return {"captions": captions}
        
        # Single image processing (preferred)
        else:
            result = process_single_image(job)
            if 'error' in result:
                return result
            
            # Convert to legacy format for compatibility
            return {
                "captions": [{
                    "image_path": "single_image",
                    "caption": result['caption']
                }]
            }
            
    except Exception as e:
        return {"error": f"Legacy handler error: {str(e)}"}

# Register the optimized handler
print("🔧 Registering optimized single-image handler...")
runpod.serverless.start({
    "handler": process_single_image,  # Primary optimized handler
    "health_check": health_check
})

print("✅ RunPod serverless handler ready for optimized single-image processing!")
