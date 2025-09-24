#!/usr/bin/env python3
"""
Test script for Geocodable Address API endpoints

Tests the /extract-address endpoint of the deployed Modal app.
"""

import requests
import json
import sys
import argparse

# Sample ACORD data based on your example
SAMPLE_ACORD_DATA = {
    "agency_customer_id": "00038610",
    "document_date": "3/21/2018",
    "agency_name": "Mack, Mack & Waltz Insurance Group, Inc.",
    "carrier": "*New",
    "naic_code": None,
    "policy_number": "PROP. MASTER",
    "effective_date": "5/16/2018",
    "named_insured": "Plum at Boca Pointe Homeowners Association Inc. (The)",
    "premises_information": [
        {
            "premises_number": "1",
            "building_number": "1",
            "street": "6680-6688 Via Regina",
            "occupancy_description": "5 Units Style A",
            "construction": {
                "type": "Frame",
                "distance_to": "500 FT 1 MI",
                "fire_district": "Palm Beach",
                "code_number": "4",
                "protection_class": "2",
                "num_stories": None,
                "num_basements": None,
                "year_built": "1986",
                "total_area": "9,809"
            },
            "coverage": {
                "subject": "Building",
                "amount": "896,529",
                "coinsurance": "RC",
                "valuation": None,
                "causes_of_loss": "Special Form",
                "deductible_amount": "2,500",
                "deductible_type": "DO",
                "hurricane_deductible": "3%",
                "forms_conditions": "HURR CLDYR DED"
            }
        }
    ]
}

def test_geocoding_api(base_url: str, acord_data: dict = None, token: str = None, verbose: bool = False):
    """Test the geocodable address API endpoints"""

    print(f"🔸 Testing Geocodable Address API at: {base_url}")
    if token:
        print(f"🔸 Using Bearer token authentication")

    # Use provided data or sample data
    test_data = acord_data or SAMPLE_ACORD_DATA

    # Setup headers
    headers = {"Content-Type": "application/json"}
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

        # Test address extraction
        print("\n🏠 Testing address extraction...")

        if verbose:
            print("📊 Input ACORD data:")
            print(json.dumps(test_data, indent=2)[:500] + "...")

        payload = {"acord_data": test_data}

        extract_response = requests.post(
            f"{base_url}/extract-address",
            headers=headers,
            json=payload,
            timeout=30
        )

        if extract_response.status_code != 200:
            print(f"❌ Address extraction failed: {extract_response.status_code}")
            print(f"   Response: {extract_response.text}")
            return False

        result_data = extract_response.json()

        print(f"✅ Address extraction successful!")

        if "address" in result_data:
            print(f"📍 Extracted Address: {result_data['address']}")

        if "error" in result_data:
            print(f"⚠️ Warning: {result_data['error']}")
            if verbose and "raw_response" in result_data:
                print(f"   Raw Response: {result_data['raw_response']}")

        if verbose:
            print(f"📋 Full Response:")
            print(json.dumps(result_data, indent=2))

        # Test with minimal data
        print("\n🧪 Testing with minimal data...")
        minimal_data = {
            "named_insured": "Sunset Beach Condos",
            "premises_information": [
                {
                    "street": "123 Ocean Drive",
                    "construction": {
                        "fire_district": "Miami-Dade"
                    }
                }
            ]
        }

        minimal_payload = {"acord_data": minimal_data}
        minimal_response = requests.post(
            f"{base_url}/extract-address",
            headers=headers,
            json=minimal_payload,
            timeout=30
        )

        if minimal_response.status_code == 200:
            minimal_result = minimal_response.json()
            print(f"✅ Minimal data test successful!")
            print(f"📍 Address: {minimal_result.get('address', 'N/A')}")
            if verbose:
                print(f"📋 Response: {json.dumps(minimal_result, indent=2)}")
        else:
            print(f"⚠️ Minimal data test failed: {minimal_response.status_code}")

        return True

    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

def load_acord_data_from_file(file_path: str) -> dict:
    """Load ACORD data from a JSON file"""
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Failed to load ACORD data from {file_path}: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Test Geocodable Address API")
    parser.add_argument('--url', '-u', required=True,
                       help='Base URL of the API (e.g., https://your-geocode-app.modal.run)')
    parser.add_argument('--token', '-t',
                       help='Bearer token for authentication')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose output')
    parser.add_argument('--data', '-d',
                       help='Path to JSON file containing ACORD data to test with')

    args = parser.parse_args()

    # Clean up URL
    base_url = args.url.rstrip('/')

    # Load ACORD data if provided
    acord_data = None
    if args.data:
        print(f"📂 Loading ACORD data from: {args.data}")
        acord_data = load_acord_data_from_file(args.data)
        print(f"✅ Loaded ACORD data with keys: {list(acord_data.keys())}")

    success = test_geocoding_api(base_url, acord_data, args.token, args.verbose)

    if success:
        print("\n🎉 All tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Tests failed!")
        sys.exit(1)

if __name__ == '__main__':
    main()