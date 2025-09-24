#!/usr/bin/env python3
"""
Test script for ACORD Processing API endpoints

Tests the /upload and /progress endpoints of the deployed Modal app.
"""

import requests
import json
import time
import sys
from pathlib import Path
import argparse

def test_endpoints(base_url: str, pdf_file: str, verbose: bool = False, write_json: bool = False, token: str = None):
    """Test the ACORD processing API endpoints"""

    print(f"🔸 Testing ACORD Processing API at: {base_url}")
    print(f"🔸 Using PDF file: {pdf_file}")
    if write_json:
        print(f"🔸 Will write JSON output to disk")
    if token:
        print(f"🔸 Using Bearer token authentication")

    # Check if PDF file exists
    pdf_path = Path(pdf_file)
    if not pdf_path.exists():
        print(f"❌ PDF file not found: {pdf_file}")
        return False

    # Setup headers
    headers = {}
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

        # Upload PDF file
        print("\n📤 Uploading PDF file...")

        with open(pdf_path, 'rb') as f:
            files = {'file': (pdf_path.name, f, 'application/pdf')}
            upload_response = requests.post(f"{base_url}/upload", files=files, headers=headers, timeout=30)

        if upload_response.status_code != 200:
            print(f"❌ Upload failed: {upload_response.status_code}")
            print(f"   Response: {upload_response.text}")
            return False

        upload_data = upload_response.json()
        job_id = upload_data.get('job_id')

        print(f"✅ Upload successful!")
        print(f"   Job ID: {job_id}")
        print(f"   Status: {upload_data.get('status')}")
        print(f"   Message: {upload_data.get('message')}")

        if not job_id:
            print("❌ No job ID returned")
            return False

        # Poll progress endpoint
        print(f"\n📊 Monitoring progress for job: {job_id}")

        max_wait_time = 300  # 5 minutes max
        poll_interval = 5    # Check every 5 seconds
        start_time = time.time()

        while True:
            elapsed = time.time() - start_time
            if elapsed > max_wait_time:
                print(f"⏰ Timeout after {max_wait_time} seconds")
                break

            try:
                progress_response = requests.get(f"{base_url}/progress/{job_id}", headers=headers, timeout=10)

                if progress_response.status_code != 200:
                    print(f"❌ Progress check failed: {progress_response.status_code}")
                    break

                progress_data = progress_response.json()
                status = progress_data.get('status')
                stage = progress_data.get('stage')
                progress_pct = progress_data.get('progress', 0)
                message = progress_data.get('message', '')

                print(f"   📈 [{elapsed:.1f}s] {status.upper()} | {stage} | {progress_pct}% | {message}")

                if verbose:
                    print(f"      Full response: {json.dumps(progress_data, indent=2)}")

                if status == 'completed':
                    print("🎉 Processing completed successfully!")

                    result = progress_data.get('result', {})
                    if result:
                        acord_type = result.get('acord_type', 'Unknown')
                        text_length = result.get('text_length', 0)
                        extracted_data = result.get('extracted_data')

                        print(f"   📄 ACORD Type: {acord_type}")
                        print(f"   📊 OCR Text Length: {text_length} characters")

                        if extracted_data:
                            print("   🎯 Structured data extracted successfully")
                            if verbose:
                                print("   📋 Extracted Data Preview:")
                                # Show first few keys
                                preview_keys = list(extracted_data.keys())[:5]
                                for key in preview_keys:
                                    value = extracted_data[key]
                                    if isinstance(value, str) and len(value) > 50:
                                        value = value[:50] + "..."
                                    print(f"      {key}: {value}")
                                if len(extracted_data) > 5:
                                    print(f"      ... and {len(extracted_data) - 5} more fields")
                        else:
                            print("   ⚠️ Raw response available (JSON parsing may have failed)")

                    # Write JSON to disk if requested
                    if write_json and result:
                        try:
                            output_filename = f"{pdf_path.name}.json"

                            with open(output_filename, 'w', encoding='utf-8') as f:
                                json.dump(result, f, indent=2, ensure_ascii=False)

                            print(f"   💾 JSON data written to: {output_filename}")

                        except Exception as write_error:
                            print(f"   ❌ Failed to write JSON file: {write_error}")

                    return result

                elif status == 'failed':
                    print("❌ Processing failed!")
                    error = progress_data.get('error', 'Unknown error')
                    print(f"   Error: {error}")
                    return False

                time.sleep(poll_interval)

            except requests.exceptions.RequestException as e:
                print(f"❌ Progress request failed: {e}")
                break

        print("⚠️ Processing did not complete within timeout")
        return None

    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        return None
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description="Test ACORD Processing API")
    parser.add_argument('--url', '-u', required=True, help='Base URL of the API (e.g., https://your-app.modal.run)')
    parser.add_argument('--file', '-f', required=True, help='Path to PDF file to test')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--write', '-w', action='store_true', help='Write JSON result to disk as filename.pdf.json')
    parser.add_argument('--token', '-t', help='Bearer token for authentication')

    args = parser.parse_args()

    # Clean up URL
    base_url = args.url.rstrip('/')

    result = test_endpoints(base_url, args.file, args.verbose, args.write, args.token)

    if result:
        print("\n🎉 All tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Tests failed!")
        sys.exit(1)

if __name__ == '__main__':
    main()