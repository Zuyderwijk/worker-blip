"""
RunPod | BLIP | schemas.py

Contains the schemas for input validation.
"""

# Input schema
INPUT_SCHEMA = {
    'data_url': {
        'type': str,
        'required': False
    },
    'data_urls': {
        'type': list,
        'required': False
    },
    'max_length': {
        'type': int,
        'required': False,
        'default': 75
    },
    'min_length': {
        'type': int,
        'required': False,
        'default': 5
    }
}
