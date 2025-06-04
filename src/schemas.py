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
