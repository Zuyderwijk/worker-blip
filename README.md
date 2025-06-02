<div align="center">

<h1>BLIP | Worker</h1>

</div>

This worker was derived from the [Bliper-Serverless](https://github.com/kodxana/Bliper-Serverless) project by [kodxana](https://github.com/kodxana)

# Optimized BLIP Image Captioning Worker

This API provides a highly optimized image captioning service that takes an image, multiple image URLs, or a zip file containing multiple images and generates captions using the BLIP2 model. The worker is optimized for RunPod serverless deployment with significant performance improvements.

## ⚡ Performance Optimizations

- **3-5x faster inference** using optimized BLIP2 model (`caption_coco_opt2.7b`)
- **Batch processing** for multiple images (up to 10x faster for bulk operations)
- **Memory management** with automatic GPU cache clearing and monitoring
- **Configurable parameters** for speed vs quality trade-offs
- **Smart fallback** handling for memory constraints

## API Parameters

The API accepts the following parameters:

### Required (one of):
- `data_url` (string): URL of a single image or zip file
- `data_urls` (array): Array of image URLs for batch processing

### Optional Performance Parameters:
- `batch_size` (integer, default: 4): Number of images to process simultaneously
- `num_beams` (integer, default: 3): Beam search width (lower = faster)
- `max_length` (integer, default: 50): Maximum caption length in tokens
- `min_length` (integer, default: 5): Minimum caption length in tokens  
- `prompt` (string, default: "a photo of"): Generation prompt

## API Output

The API returns a JSON object containing:

```json
{
    "captions": [
        {
            "image_path": "/path/to/image.jpg",
            "caption": "a photo of a beautiful sunset over mountains"
        }
    ]
}
```

## Usage Examples

### Single Image
```json
{
    "input": {
        "data_url": "https://example.com/image.jpg"
    }
}
```

### Multiple Images (Optimized)
```json
{
    "input": {
        "data_urls": [
            "https://example.com/image1.jpg", 
            "https://example.com/image2.jpg"
        ],
        "batch_size": 4,
        "num_beams": 3
    }
}
```

### Performance Tuning
```json
{
    "input": {
        "data_url": "https://example.com/images.zip",
        "batch_size": 6,
        "num_beams": 2,
        "max_length": 30,
        "prompt": "a detailed photo of"
    }
}
```

## 📊 Performance Guide

See [OPTIMIZATION.md](OPTIMIZATION.md) for detailed performance tuning and benchmarks.
