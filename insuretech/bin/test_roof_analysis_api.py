#!/usr/bin/env python3
"""
Test script for Roof Analysis API endpoints

Tests the /save-image endpoint of the deployed Modal app.
"""

import requests
import json
import sys
import argparse
import base64
from PIL import Image, ImageDraw
from io import BytesIO

def create_dummy_image() -> str:
    """Create a dummy image and return it as a base64 encoded string"""
    img = Image.new('RGB', (100, 100), color = 'red')
    draw = ImageDraw.Draw(img)
    draw.rectangle(((10, 10), (90, 90)), fill = 'blue')
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
    return f"data:image/png;base64,{img_str}"

def test_save_image_endpoint(base_url: str, verbose: bool = False, token: str = None):
    """Test the /save-image endpoint"""

    print(f"🔸 Testing Roof Analysis API at: {base_url}")
    if token:
        print(f"🔸 Using Bearer token authentication")

    # Setup headers
    headers = {
        "Content-Type": "application/json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        # Test health endpoint first
        print("\n📋 Testing health endpoint...")
        health_response = requests.get(f"{base_url}/health", timeout=10)
        if health_response.status_code == 200:
            print("✅ Health check passed")
            if verbose:
                print(f"   Response: {health_response.json()}")
        else:
            print(f"⚠️ Health check failed: {health_response.status_code}")

        # Test /save-image endpoint
        print("\n📤 Testing /save-image endpoint...")

        image_data = create_dummy_image()
        payload = {"image_data": image_data}

        save_image_response = requests.post(f"{base_url}/save-image", headers=headers, json=payload, timeout=30)

        if save_image_response.status_code != 200:
            print(f"❌ /save-image endpoint failed: {save_image_response.status_code}")
            print(f"   Response: {save_image_response.text}")
            return False

        response_data = save_image_response.json()
        print(f"✅ /save-image endpoint successful!")
        print(f"   Response: {response_data}")

        return True

    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Test Roof Analysis API")
    parser.add_argument('--url', '-u', required=True, help='Base URL of the API (e.g., https://your-app.modal.run)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--token', '-t', help='Bearer token for authentication')

    args = parser.parse_args()

    # Clean up URL
    base_url = args.url.rstrip('/')

    result = test_save_image_endpoint(base_url, args.verbose, args.token)

    if result:
        print("\n🎉 All tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Tests failed!")
        sys.exit(1)

if __name__ == '__main__':
    main()
