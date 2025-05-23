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

    # Accept a list of URLs under 'data_urls' or a single URL under 'data_url'
    data_urls = job_input.get('data_urls')
    if data_urls is None:
        single_url = job_input.get('data_url')
        if single_url:
            data_urls = [single_url]
        else:
            return {"error": "No data_url or data_urls provided."}

    # Input validation (use the first URL for schema validation)
    validated_input = validate({**job_input, 'data_url': data_urls[0]}, INPUT_SCHEMA)
    if 'errors' in validated_input:
        return {"error": validated_input['errors']}
    validated_input = validated_input['validated_input']

    captions = []
    for url in data_urls:
        # Download the input data
        input_path_data = rp_download.file(url)
        input_path = input_path_data["file_path"]
        print(f"Input path: {input_path}")

        # Check if input data is an image or a zip file
        mime_type, _ = mimetypes.guess_type(input_path)
        is_zip = mime_type == "application/zip"

        if is_zip:
            # Unzip the file
            with zipfile.ZipFile(input_path, 'r') as zip_ref:
                zip_ref.extractall('/tmp')
            # Get the list of extracted images
            images = [os.path.join('/tmp', f) for f in os.listdir('/tmp')
                      if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        else:
            images = [input_path]

        for image_path in images:
            # Check if the current file is an image
            mime_type, _ = mimetypes.guess_type(image_path)
            if mime_type not in ["image/jpeg", "image/png", "image/jpg"]:
                continue
            # Load the image
            image = Image.open(image_path).convert("RGB")
            image_tensor = vis_processors["eval"](image).unsqueeze(0).to(DEVICE)

            # Generate the caption
            with torch.no_grad():
                caption = ' '.join(model.generate({"image": image_tensor}, max_length=validated_input['max_length'],
                                                  min_length=validated_input['min_length']))
            captions.append({"image_path": image_path, "caption": caption})

    # Cleanup
    rp_cleanup.clean(['/tmp'])

    # Return all captions directly in the response
    return {"captions": captions}


runpod.serverless.start({"handler": caption_image})
