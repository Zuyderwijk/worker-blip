import os
import mimetypes
import gc
import time
from typing import Dict, Any, Optional, List

import torch
from PIL import Image
import runpod
from runpod.serverless.utils import rp_download, rp_cleanup
from runpod.serverless.utils.rp_validator import validate

from lavis.models import load_model_and_preprocess

# Enhanced input schema for personalized image processing
INPUT_SCHEMA = {
    'data_url': {
        'type': str,
        'required': True,
        'description': 'Base64 encoded image data URL (data:image/...;base64,...) or HTTP URL'
    },
    'prompt': {
        'type': str,
        'required': False,
        'default': 'a photo of',
        'description': 'Caption generation prompt (can include tagged people names)'
    },
    'tags': {
        'type': list,
        'required': False,
        'default': [],
        'description': 'List of tagged people/objects: [{"name": "Hanna", "role": "daughter"}, ...]'
    },
    'max_length': {
        'type': int,
        'required': False,
        'default': 80,
        'description': 'Maximum caption length for detailed personalized descriptions'
    },
    'min_length': {
        'type': int,
        'required': False,
        'default': 15,
        'description': 'Minimum caption length for good detail'
    },
    'num_beams': {
        'type': int,
        'required': False,
        'default': 5,
        'description': 'Number of beams for beam search (higher for better quality)'
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

# Load optimized model for personalized image processing
print("🚀 Loading optimized BLIP2 model for personalized captions...")
start_time = time.time()

try:
    # Use the smallest, fastest BLIP2 variant for production
    model, vis_processors, _ = load_model_and_preprocess(
        name="blip2_opt",
        model_type="caption_coco_opt2.7b",  # Good balance of speed and quality
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

def create_personalized_prompt(base_prompt: str, tags: List[Dict[str, str]]) -> str:
    """
    Create a personalized prompt that incorporates tagged people/objects
    to encourage the AI to use their names in the caption
    """
    if not tags:
        return base_prompt
    
    # Extract people with names
    people = []
    for tag in tags:
        name = tag.get('name', '')
        role = tag.get('role', '')
        if name:
            if role:
                people.append(f"{name} ({role})")
            else:
                people.append(name)
    
    if not people:
        return base_prompt
    
    # Create enhanced prompts that encourage using the names
    people_str = ', '.join(people)
    
    # Enhanced prompts for better personalization
    enhanced_prompts = [
        f"detailed photo of {people_str}",
        f"photo showing {people_str}",
        f"{people_str} in a detailed photo",
        f"detailed scene with {people_str}"
    ]
    
    # Use the first enhanced prompt for consistency
    enhanced_prompt = enhanced_prompts[0]
    
    print(f"🏷️ Enhanced prompt with tags: '{enhanced_prompt}'")
    return enhanced_prompt

def post_process_caption_with_tags(caption: str, tags: List[Dict[str, str]]) -> str:
    """
    Post-process the caption to ensure tagged names are properly included
    and enhance the description for children's book context
    """
    if not tags or not caption:
        return caption
    
    # Extract names from tags
    names = [tag.get('name', '') for tag in tags if tag.get('name')]
    if not names:
        return caption
    
    processed_caption = caption
    
    # If the caption doesn't contain any of the tagged names, try to incorporate them
    caption_lower = caption.lower()
    names_in_caption = [name for name in names if name.lower() in caption_lower]
    
    if not names_in_caption:
        # Try to replace generic terms with specific names
        replacements = {
            'a person': names[0] if len(names) == 1 else names[0],
            'a man': next((tag['name'] for tag in tags if tag.get('role') in ['father', 'dad', 'papa', 'man']), names[0]),
            'a woman': next((tag['name'] for tag in tags if tag.get('role') in ['mother', 'mom', 'mama', 'woman']), names[0]),
            'a boy': next((tag['name'] for tag in tags if tag.get('role') in ['son', 'boy', 'child']), names[0]),
            'a girl': next((tag['name'] for tag in tags if tag.get('role') in ['daughter', 'girl', 'child']), names[0]),
            'a child': names[0],
            'someone': names[0],
            'they': names[0] if len(names) == 1 else f"{names[0]} and {names[1]}" if len(names) == 2 else f"{', '.join(names[:-1])} and {names[-1]}",
        }
        
        for generic_term, specific_name in replacements.items():
            if generic_term in caption_lower:
                # Replace first occurrence, maintaining original capitalization
                idx = caption_lower.find(generic_term)
                if idx != -1:
                    processed_caption = caption[:idx] + specific_name + caption[idx + len(generic_term):]
                    break
    
    # Enhance for children's book context
    if processed_caption and not any(phrase in processed_caption.lower() for phrase in ['little', 'sweet', 'cute', 'lovely']):
        # Add a gentle adjective before names when appropriate
        for name in names:
            if name in processed_caption:
                processed_caption = processed_caption.replace(name, f"little {name}", 1)
                break
    
    return processed_caption

def health_check() -> Dict[str, Any]:
    """Enhanced health check"""
    try:
        return {
            "status": "healthy",
            "device": str(DEVICE),
            "cuda_available": torch.cuda.is_available(),
            "model_loaded": model is not None,
            "timestamp": time.time(),
            "gpu_memory_gb": torch.cuda.memory_allocated() / 1024**3 if torch.cuda.is_available() else 0,
            "features": ["personalized_captions", "tag_integration", "children_book_context"]
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

def process_single_image(job: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enhanced single image processing function with personalized captions
    
    Expected input format:
    {
        "input": {
            "data_url": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQ..." or "https://...",
            "prompt": "detailed photo showing",
            "tags": [{"name": "Hanna", "role": "daughter"}, {"name": "Puck", "role": "son"}],
            "max_length": 80,
            "min_length": 15,
            "num_beams": 5
        }
    }
    """
    process_start = time.time()
    
    try:
        print(f"🚀 Processing personalized job at {time.strftime('%Y-%m-%d %H:%M:%S')}")
        
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
        tags = params.get('tags', [])
        
        if not data_url or not (data_url.startswith('data:image/') or data_url.startswith('http')):
            return {"error": "Invalid data_url format. Expected: data:image/...;base64,... or http(s)://..."}
        
        print(f"📥 Processing single image with personalized params:")
        print(f"   - max_length: {params['max_length']}, num_beams: {params['num_beams']}")
        print(f"   - tags: {tags}")
        
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
            
            # Resize large images for faster processing (but allow larger sizes for better detail)
            max_size = 768  # Increased for better detail in personalized captions
            if max(image.size) > max_size:
                image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
                print(f"🔄 Resized image to {image.size} for optimal processing")
            
            image_tensor = vis_processors["eval"](image).unsqueeze(0).to(DEVICE)
            prep_time = time.time() - prep_start
            print(f"🖼️ Image preprocessed in {prep_time:.3f}s")
            
            # Create personalized prompt
            original_prompt = params['prompt']
            personalized_prompt = create_personalized_prompt(original_prompt, tags)
            
            # Generate caption with personalized parameters
            gen_start = time.time()
            with torch.no_grad():
                # Enhanced parameters for better personalized descriptions
                max_length = min(params['max_length'], 100)  # Allow longer for detailed stories
                num_beams = min(params['num_beams'], 8)      # Higher quality for personalization
                
                caption = model.generate({
                    "image": image_tensor,
                    "prompt": personalized_prompt,
                    "num_beams": num_beams,
                    "max_length": max_length,
                    "min_length": params['min_length'],
                    "repetition_penalty": 1.2,   # Higher to avoid repetition with names
                    "do_sample": False,          # Deterministic for consistency
                    "early_stopping": True,      # Stop when EOS is generated
                    "length_penalty": 1.0        # Neutral length preference
                })[0]
                
            gen_time = time.time() - gen_start
            print(f"🧠 Generated raw caption in {gen_time:.3f}s: '{caption}'")
            
            # Post-process caption with tag integration
            processed_caption = post_process_caption_with_tags(caption, tags)
            
            if processed_caption != caption:
                print(f"✨ Enhanced caption with tags: '{processed_caption}'")
            
            # Clear GPU cache immediately
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            process_time = time.time() - process_start
            print(f"✅ Total processing time: {process_time:.3f}s")
            
            return {
                "caption": processed_caption,
                "raw_caption": caption,  # Keep original for debugging
                "processing_time": process_time,
                "personalization_info": {
                    "tags_used": tags,
                    "enhanced_prompt": personalized_prompt,
                    "post_processed": processed_caption != caption
                },
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
    Converts batch requests to single image format with personalization support
    """
    try:
        job_input = job.get("input", {})
        
        # Handle legacy batch format
        if 'data_urls' in job_input:
            data_urls = job_input['data_urls']
            if not data_urls:
                return {"error": "Empty data_urls array"}
            
            print(f"🔄 Legacy batch mode: processing {len(data_urls)} images sequentially")
            
            # Handle tags for batch processing
            batch_tags = job_input.get('tags', [])
            
            captions = []
            for i, data_url in enumerate(data_urls):
                print(f"📸 Processing image {i+1}/{len(data_urls)}")
                
                # Get tags for this specific image
                image_tags = batch_tags[i] if i < len(batch_tags) else []
                
                # Create single image job
                single_job = {
                    "input": {
                        "data_url": data_url,
                        "prompt": job_input.get('prompt', 'detailed photo showing'),
                        "tags": image_tags,
                        "max_length": job_input.get('max_length', 80),
                        "min_length": job_input.get('min_length', 15),
                        "num_beams": job_input.get('num_beams', 5)
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
                        "caption": result['caption'],
                        "personalization_info": result.get('personalization_info', {})
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
                    "caption": result['caption'],
                    "personalization_info": result.get('personalization_info', {})
                }]
            }
            
    except Exception as e:
        return {"error": f"Legacy handler error: {str(e)}"}

# Register the enhanced handler
print("🔧 Registering enhanced personalized handler...")
runpod.serverless.start({
    "handler": process_single_image,  # Primary enhanced handler
    "health_check": health_check
})

print("✅ RunPod serverless handler ready for personalized image captions!")
print("🏷️ Features: Tag integration, personalized prompts, children's book context")
