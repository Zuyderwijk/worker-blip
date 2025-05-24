from lavis.models import load_model_and_preprocess
import torch

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

load_model_and_preprocess(
    name="blip2_t5",
    model_type="flan_t5_xl",
    is_eval=True,
    device=DEVICE
)