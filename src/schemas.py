"""
RunPod | BLIP | schemas.py

Contains the schemas for input validation with performance optimizations.
"""

# Input schema with performance tuning options
INPUT_SCHEMA = {
    "data_url": {"type": str, "required": False},
    "data_urls": {"type": list, "required": False},
    "min_length": {"type": int, "required": False, "default": 5},
    "max_length": {"type": int, "required": False, "default": 50},  # Reduced default for faster processing
    "batch_size": {"type": int, "required": False, "default": 4},   # Allow batch size tuning
    "num_beams": {"type": int, "required": False, "default": 3},    # Beam search optimization
    "prompt": {"type": str, "required": False, "default": "a photo of"}  # Customizable prompt
}