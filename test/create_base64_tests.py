#!/usr/bin/env python3
"""
Create base64 test data URLs for testing the optimized handler
"""
import base64
import json
import os

def create_base64_data_url(image_path):
    """Convert a local image file to a base64 data URL"""
    try:
        with open(image_path, 'rb') as image_file:
            image_data = image_file.read()
            base64_data = base64.b64encode(image_data).decode('utf-8')
            
            # Determine MIME type
            if image_path.lower().endswith('.png'):
                mime_type = 'image/png'
            elif image_path.lower().endswith(('.jpg', '.jpeg')):
                mime_type = 'image/jpeg'
            elif image_path.lower().endswith('.gif'):
                mime_type = 'image/gif'
            else:
                mime_type = 'image/jpeg'  # Default
                
            return f"data:{mime_type};base64,{base64_data}"
    except Exception as e:
        print(f"Error processing {image_path}: {e}")
        return None

def create_sample_base64_tests():
    """Create sample test files with base64 data URLs"""
    
    # Test 1: Fast processing parameters
    test_fast = {
        "input": {
            "data_url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==",
            "prompt": "describe this",
            "max_length": 20,
            "min_length": 3,
            "num_beams": 1
        }
    }
    
    # Test 2: Quality processing parameters  
    test_quality = {
        "input": {
            "data_url": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAYEBQYFBAYGBQYHBwYIChAKCgkJChQODwwQFxQYGBcUFhYaHSUfGhsjHBYWICwgIyYnKSopGR8tMC0oMCUoKSj/2wBDAQcHBwoIChMKChMoGhYaKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCj/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAv/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwCdABmX/9k=",
            "prompt": "a detailed description of",
            "max_length": 50,
            "min_length": 10,
            "num_beams": 3
        }
    }
    
    # Save test files
    tests = {
        'test_base64_fast.json': test_fast,
        'test_base64_quality.json': test_quality
    }
    
    for filename, test_data in tests.items():
        filepath = os.path.join('test', filename)
        with open(filepath, 'w') as f:
            json.dump(test_data, f, indent=2)
        print(f"✅ Created {filepath}")

if __name__ == "__main__":
    create_sample_base64_tests()
    print("\n🎯 Base64 test files created for optimized handler testing!")
    print("📝 These tests use minimal base64 images for fast validation")
    print("🚀 Use these to test your optimized single-image processing pipeline")
