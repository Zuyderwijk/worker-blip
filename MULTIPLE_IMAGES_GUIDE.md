# Multiple Image Processing Guide

## Overview

The BLIP image captioning worker now supports processing multiple images in a single request, with optimized batch processing and JSON responses.

## Input Formats

### Single Image
```json
{
  "input": {
    "data_url": "https://example.com/image.jpg",
    "batch_size": 1,
    "num_beams": 2,
    "max_length": 30,
    "min_length": 5,
    "prompt": "a photo of"
  }
}
```

### Multiple Images
```json
{
  "input": {
    "data_urls": [
      "https://example.com/image1.jpg",
      "https://example.com/image2.jpg",
      "https://example.com/image3.jpg"
    ],
    "batch_size": 3,
    "num_beams": 2,
    "max_length": 25,
    "min_length": 5,
    "prompt": "describe this image"
  }
}
```

### ZIP Archive (Single or Multiple)
```json
{
  "input": {
    "data_url": "https://example.com/images.zip",
    "batch_size": 4,
    "num_beams": 2,
    "max_length": 30,
    "min_length": 5,
    "prompt": "a detailed photo of"
  }
}
```

## Response Format

The worker now returns captions directly as JSON instead of uploading to S3:

```json
{
  "captions": [
    {
      "image_path": "/path/to/image1.jpg",
      "caption": "a photo of a cat sitting on a windowsill"
    },
    {
      "image_path": "/path/to/image2.jpg", 
      "caption": "a beautiful landscape with mountains and trees"
    }
  ]
}
```

## Next.js Integration

### API Route Example

```javascript
// pages/api/caption-images.js (Pages Router)
// or app/api/caption-images/route.js (App Router)

export async function POST(request) {
  try {
    const { imageUrls, options = {} } = await request.json();
    
    // Prepare the payload for RunPod
    const payload = {
      input: {
        data_urls: imageUrls,
        batch_size: options.batchSize || 3,
        num_beams: options.numBeams || 2,
        max_length: options.maxLength || 25,
        min_length: options.minLength || 5,
        prompt: options.prompt || "a photo of"
      }
    };

    // Submit job to RunPod
    const runResponse = await fetch(`https://api.runpod.ai/v2/${process.env.RUNPOD_ENDPOINT_ID}/run`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${process.env.RUNPOD_API_KEY}`
      },
      body: JSON.stringify(payload)
    });

    const runResult = await runResponse.json();
    
    if (!runResult.id) {
      throw new Error('Failed to submit job to RunPod');
    }

    // Poll for results
    let attempts = 0;
    const maxAttempts = 60; // 5 minutes with 5-second intervals
    
    while (attempts < maxAttempts) {
      await new Promise(resolve => setTimeout(resolve, 5000)); // Wait 5 seconds
      
      const statusResponse = await fetch(`https://api.runpod.ai/v2/${process.env.RUNPOD_ENDPOINT_ID}/status/${runResult.id}`, {
        headers: {
          'Authorization': `Bearer ${process.env.RUNPOD_API_KEY}`
        }
      });
      
      const statusResult = await statusResponse.json();
      
      if (statusResult.status === 'COMPLETED') {
        return Response.json({
          success: true,
          captions: statusResult.output?.captions || [],
          processingTime: statusResult.executionTime
        });
      }
      
      if (statusResult.status === 'FAILED') {
        throw new Error(statusResult.error || 'Job failed');
      }
      
      attempts++;
    }
    
    throw new Error('Job timed out');
    
  } catch (error) {
    console.error('Error captioning images:', error);
    return Response.json({
      success: false,
      error: error.message
    }, { status: 500 });
  }
}
```

### Frontend Usage

```javascript
// Frontend component
import { useState } from 'react';

export default function ImageCaptioner() {
  const [imageUrls, setImageUrls] = useState(['']);
  const [captions, setCaptions] = useState([]);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    
    try {
      const validUrls = imageUrls.filter(url => url.trim());
      
      const response = await fetch('/api/caption-images', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          imageUrls: validUrls,
          options: {
            batchSize: 3,
            numBeams: 2,
            maxLength: 30,
            prompt: "a detailed photo of"
          }
        })
      });

      const result = await response.json();
      
      if (result.success) {
        setCaptions(result.captions);
      } else {
        console.error('Error:', result.error);
      }
    } catch (error) {
      console.error('Request failed:', error);
    } finally {
      setLoading(false);
    }
  };

  const addImageUrl = () => {
    setImageUrls([...imageUrls, '']);
  };

  const updateImageUrl = (index, value) => {
    const newUrls = [...imageUrls];
    newUrls[index] = value;
    setImageUrls(newUrls);
  };

  return (
    <div className="max-w-2xl mx-auto p-6">
      <h1 className="text-2xl font-bold mb-6">Image Caption Generator</h1>
      
      <form onSubmit={handleSubmit} className="space-y-4">
        {imageUrls.map((url, index) => (
          <div key={index}>
            <label className="block text-sm font-medium mb-1">
              Image URL {index + 1}
            </label>
            <input
              type="url"
              value={url}
              onChange={(e) => updateImageUrl(index, e.target.value)}
              placeholder="https://example.com/image.jpg"
              className="w-full p-2 border rounded"
            />
          </div>
        ))}
        
        <button
          type="button"
          onClick={addImageUrl}
          className="text-blue-600 hover:text-blue-800"
        >
          + Add Another Image
        </button>
        
        <button
          type="submit"
          disabled={loading}
          className="w-full bg-blue-600 text-white p-2 rounded hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? 'Processing...' : 'Generate Captions'}
        </button>
      </form>

      {captions.length > 0 && (
        <div className="mt-8">
          <h2 className="text-xl font-semibold mb-4">Results</h2>
          <div className="space-y-4">
            {captions.map((item, index) => (
              <div key={index} className="border p-4 rounded">
                <p className="text-sm text-gray-600 mb-2">
                  {item.image_path}
                </p>
                <p className="font-medium">
                  {item.caption}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
```

## Performance Optimization

### Recommended Settings

- **batch_size**: 2-4 for optimal memory usage
- **num_beams**: 2-3 for balance of quality and speed  
- **max_length**: 20-30 for faster processing
- **prompt**: Use specific prompts for better results

### Timeout Prevention

The worker includes several timeout prevention measures:

1. **Batch Processing**: Images are processed in small batches
2. **Memory Management**: GPU cache is cleared between batches
3. **Fallback Processing**: If batch fails, falls back to individual processing
4. **Conservative Limits**: Batch sizes and beam counts are automatically limited

### Error Handling

The worker gracefully handles:
- Invalid image URLs
- Unsupported image formats
- Memory errors (automatic fallback)
- Network timeouts
- ZIP archive extraction errors

Individual image failures don't stop the entire job - they're marked with `[ERROR: ...]` in the caption.

## Testing

Use the provided test files to verify functionality:

```bash
# Test single URL
curl -X POST https://api.runpod.ai/v2/YOUR_ENDPOINT/run \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d @test/test_single_url.json

# Test multiple URLs  
curl -X POST https://api.runpod.ai/v2/YOUR_ENDPOINT/run \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d @test/test_multiple_images.json
```

## Environment Variables

Make sure to set these in your Next.js environment:

```bash
RUNPOD_API_KEY=your_runpod_api_key
RUNPOD_ENDPOINT_ID=your_endpoint_id
```
