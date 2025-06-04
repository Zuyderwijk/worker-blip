FROM runpod/pytorch:3.10-2.0.0-117

WORKDIR /

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive
# Optimize PyTorch for inference
ENV TORCH_CUDNN_V8_API_ENABLED=1
ENV CUDA_LAUNCH_BLOCKING=0
# Enable memory optimization
ENV PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:128

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    wget \
    libgl1-mesa-glx \
    libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies with optimizations
COPY builder/requirements.txt /requirements.txt
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r /requirements.txt && \
    rm /requirements.txt

# Set the HF_HOME environment variable
ENV HF_HOME=/huggingface_cache

# Create the necessary directories for the model
COPY builder/fetch_model.py /fetch_model.py
RUN python /fetch_model.py
RUN rm /fetch_model.py

ADD src .

CMD [ "python", "-u", "/handler.py" ]
