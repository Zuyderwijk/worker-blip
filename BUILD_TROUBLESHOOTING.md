# RunPod Build Troubleshooting Guide

## Common Build Issues and Solutions

### 1. Pip Install Failures

If you encounter pip install errors, try these solutions in order:

#### Option A: Use Minimal Requirements
Replace `requirements.txt` with `requirements-minimal.txt`:

```dockerfile
# In Dockerfile, change this line:
COPY builder/requirements.txt /requirements.txt

# To this:
COPY builder/requirements-minimal.txt /requirements.txt
```

#### Option B: Update Requirements Step by Step
Test with progressively more dependencies:

```txt
# Start with just these:
runpod==0.9.3
numpy<2

# Then add:
salesforce-lavis>=1.0.0,<2.0.0
```

### 2. LAVIS Installation Issues

If LAVIS fails to install:

```dockerfile
# Add this before pip install in Dockerfile:
RUN apt-get update && apt-get install -y git

# Then in requirements.txt use git version:
git+https://github.com/salesforce/LAVIS.git@main
```

### 3. Model Loading Issues

If the model type `caption_coco_opt2.7b` fails, try alternatives:

```python
# In handler.py and fetch_model.py, try these alternatives:

# Option 1: Original working model
model_type="blip2_t5_flant5xl"

# Option 2: Smaller BLIP2 model
model_type="pretrain_opt2.7b"

# Option 3: Basic BLIP model
name="blip_caption"
model_type="base_coco"
```

### 4. Memory Issues During Build

Add these to Dockerfile if build runs out of memory:

```dockerfile
# Reduce parallel jobs
ENV MAKEFLAGS="-j1"
ENV MAX_JOBS="1"

# Set memory limits for pip
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
```

### 5. CUDA/PyTorch Issues

If PyTorch CUDA errors occur:

```dockerfile
# Use CPU-only version for testing
RUN pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu

# Or specify exact CUDA version
RUN pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
```

## Minimal Working Configuration

If all else fails, use this minimal setup:

### requirements-minimal.txt
```txt
runpod==0.9.3
torch>=1.13.0
torchvision>=0.14.0
transformers>=4.20.0
Pillow>=9.0.0
requests>=2.28.0
numpy<2
```

### Simplified handler.py
```python
# Use transformers instead of LAVIS if needed
from transformers import BlipProcessor, BlipForConditionalGeneration

processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
```

## Testing Your Build

Test locally with Docker:

```bash
# Build the container
docker build -t test-blip .

# Run a test
docker run --rm test-blip python -c "import torch; print('PyTorch:', torch.__version__)"
```

## Current Working Configuration

The current optimized setup should work with:
- `salesforce-lavis>=1.0.0,<2.0.0`
- `numpy<2`
- `runpod==0.9.3`
- Model: `blip2_opt` with `caption_coco_opt2.7b`

If this fails, fall back to the minimal configuration above.
