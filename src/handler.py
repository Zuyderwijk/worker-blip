import os
import zipfile
import mimetypes

import torch
from PIL import Image

from lavis.models import load_model_and_preprocess
import runpod
from runpod.serverless.utils import rp_download, rp_cleanup
from runpod.serverless.utils.rp_upload import files, upload_file_to_bucket
from runpod.serverless.utils.rp_validator import validate

from schemas import INPUT_SCHEMA

# Set up the device
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Load the BLIP model and preprocessors
model, vis_processors, _ = load_model_and_preprocess(
    name="blip_caption", model_type="base_coco", is_eval=True, device=DEVICE
)

def caption_image(job):
    job_input = job["input"]

    # Accept both data_url (single) or data_urls (list)
    data_urls = job_input.get('data_urls')
    if not data_urls:
        single_url = job_input.get('data_url')
        if single_url:
            data_urls = [single_url]
        else:
            return {"error": "At least one of 'data_url' or 'data_urls' is required."}

    # Validate only allowed fields
    schema_input = {k: v for k, v in job_input.items() if k in INPUT_SCHEMA}
    # Ensure all required keys from schema exist in schema_input
    for k in INPUT_SCHEMA:
        if k not in schema_input:
            schema_input[k] = None

    validated = validate(schema_input, INPUT_SCHEMA)
    if 'errors' in validated:
        return {"error": validated['errors']}
    validated_input = validated['validated_input']

    min_len = validated_input.get("min_length", 5)
    max_len = validated_input.get("max_length", 75)

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

                captions.append({
                    "image_path": image_path,
                    "caption": caption
                })

            except Exception as e:
                captions.append({
                    "image_path": image_path,
                    "caption": f"[ERROR: Failed to process image: {str(e)}]"
                })

    rp_cleanup.clean(['/tmp'])
    return {"captions": captions}

runpod.serverless.start({"handler": caption_image})