from lavis.models import load_model_and_preprocess
import torch

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Use smaller, more efficient model for faster inference
# blip2_opt with caption_coco_opt2.7b is much faster than flant5xl
load_model_and_preprocess(
    name="blip2_opt",
    model_type="caption_coco_opt2.7b",  # Smaller, faster model
    is_eval=True,
    device=DEVICE
)