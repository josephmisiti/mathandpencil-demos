import modal
import os
import json
import time
from typing import Dict, Any
from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Modal app setup
app = modal.App("geocodable-address-api")

# API authentication - same as acord_api.py
api_secret = modal.Secret.from_name("acord-api-secret")

# AWS credentials for Claude access
aws_secret = modal.Secret.from_name("aws-credentials")

# Modal image with dependencies
image = modal.Image.debian_slim().pip_install(
    "fastapi",
    "boto3",
    "botocore",
    "python-multipart",
    "pydantic"
)

# Geocoding prompt
GEOCODING_PROMPT = """Look at this insurance data and create a complete address for geocoding.

Data:
{acorddata}

Instructions:
- Find the street address in "premises_information" -> "street"
- Use "named_insured" to guess the city (e.g. "Boca Pointe" means Boca Raton, FL)
- Use "fire_district" to guess the state/county (e.g. "Palm Beach" means Florida)
- Create a complete address like: "123 Main St, Miami, FL"

Respond with ONLY this JSON format (no other text):
{{"address": "complete address here"}}"""

# Request/Response models
class GeocodeRequest(BaseModel):
    acord_data: Dict[Any, Any]

class GeocodeResponse(BaseModel):
    address: str

@app.function(
    image=image,
    secrets=[aws_secret],
    timeout=120
)
def extract_geocodable_address(acord_data: dict) -> dict:
    """Extract geocodable address from ACORD data using Claude"""
    import boto3
    from botocore.exceptions import ClientError

    print(f"[GEOCODE] Starting address extraction...")
    print(f"[GEOCODE] Input data: {json.dumps(acord_data, indent=2)}")

    try:
        # Setup Bedrock client
        bedrock_client = boto3.client(
            'bedrock-runtime',
            aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
            region_name=os.environ.get('AWS_DEFAULT_REGION', 'us-east-1')
        )
        print(f"[GEOCODE] Bedrock client created successfully")

        # Format the prompt with the ACORD data - handle both dict and string cases
        if isinstance(acord_data, str):
            print(f"[GEOCODE] ACORD data received as string, parsing...")
            try:
                parsed_data = json.loads(acord_data)
                acorddata_str = json.dumps(parsed_data, indent=2)
            except json.JSONDecodeError:
                print(f"[GEOCODE] Failed to parse ACORD data string, using as-is")
                acorddata_str = acord_data
        else:
            print(f"[GEOCODE] ACORD data received as dict/object")
            acorddata_str = json.dumps(acord_data, indent=2)

        print(f"[GEOCODE] ACORD data for prompt (first 300 chars): {acorddata_str[:300]}...")

        formatted_prompt = GEOCODING_PROMPT.format(acorddata=acorddata_str)
        print(f"[GEOCODE] =========================")
        print(f"[GEOCODE] FULL FORMATTED PROMPT:")
        print(formatted_prompt)
        print(f"[GEOCODE] =========================")
        print(f"[GEOCODE] Prompt length: {len(formatted_prompt)} characters")

        # Call Claude
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1000,
            "temperature": 0.1,
            "messages": [{
                "role": "user",
                "content": formatted_prompt
            }]
        })

        print(f"[GEOCODE] Request body being sent to Claude: {body[:500]}...")
        print(f"[GEOCODE] Calling Claude for address extraction...")

        response = bedrock_client.invoke_model(
            body=body,
            modelId="us.anthropic.claude-3-5-sonnet-20241022-v2:0",
            accept='application/json',
            contentType='application/json'
        )

        print(f"[GEOCODE] Claude response received, parsing...")
        response_body = json.loads(response.get('body').read())
        print(f"[GEOCODE] Raw response body: {json.dumps(response_body, indent=2)}")

        response_text = response_body.get('content', [{}])[0].get('text', '')

        if not response_text:
            print(f"[GEOCODE] ERROR: No response text from Claude!")
            print(f"[GEOCODE] Response body content: {response_body.get('content', 'NO CONTENT')}")
            raise Exception("No response from Claude")

        print(f"[GEOCODE] Claude response text (length {len(response_text)}): '{response_text}'")

        # Parse JSON response
        try:
            # Clean response - be more aggressive about cleaning
            cleaned_response = response_text.strip()

            # Remove markdown code blocks
            if cleaned_response.startswith('```json'):
                cleaned_response = cleaned_response.replace('```json', '').replace('```', '').strip()
            elif cleaned_response.startswith('```'):
                cleaned_response = cleaned_response.replace('```', '').strip()

            # Remove any leading/trailing whitespace and newlines
            cleaned_response = cleaned_response.strip().strip('\n').strip()

            print(f"[GEOCODE] Cleaned response for parsing: '{cleaned_response}'")

            # Try to find JSON object in the response
            if '{' in cleaned_response and '}' in cleaned_response:
                # Extract just the JSON part
                start = cleaned_response.find('{')
                end = cleaned_response.rfind('}') + 1
                json_part = cleaned_response[start:end]
                print(f"[GEOCODE] Extracted JSON part: '{json_part}'")

                result = json.loads(json_part)
            else:
                # Try parsing the whole cleaned response
                result = json.loads(cleaned_response)

            # Validate that we have an address field
            if not isinstance(result, dict) or 'address' not in result:
                raise ValueError("Response does not contain 'address' field")

            print(f"[GEOCODE] Successfully extracted address: {result['address']}")
            return result

        except json.JSONDecodeError as e:
            print(f"[GEOCODE] JSON parsing failed: {str(e)}")
            print(f"[GEOCODE] Raw response: '{response_text}'")
            print(f"[GEOCODE] Cleaned response: '{cleaned_response}'")

            # Try to extract address manually if JSON parsing fails
            if 'address' in response_text.lower():
                # Look for patterns like "address": "some address"
                import re
                address_match = re.search(r'"address"\s*:\s*"([^"]+)"', response_text, re.IGNORECASE)
                if address_match:
                    extracted_address = address_match.group(1)
                    print(f"[GEOCODE] Manually extracted address: {extracted_address}")
                    return {"address": extracted_address}

            # Return a fallback response
            return {"address": "Unable to parse address", "error": f"JSON parsing failed: {str(e)}", "raw_response": response_text}

    except Exception as e:
        error_msg = f"Address extraction failed: {str(e)}"
        print(f"[GEOCODE] EXCEPTION CAUGHT: {error_msg}")
        print(f"[GEOCODE] Exception type: {type(e)}")
        import traceback
        print(f"[GEOCODE] Full traceback: {traceback.format_exc()}")
        return {"address": "Error extracting address", "error": error_msg}

# Authentication setup - same as acord_api.py
security = HTTPBearer()

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify the Bearer token"""
    expected_token = os.environ.get("API_TOKEN")
    if not expected_token:
        raise HTTPException(status_code=500, detail="Server configuration error")

    if credentials.credentials != expected_token:
        raise HTTPException(status_code=401, detail="Invalid authentication token")

    return credentials.credentials

# FastAPI app
web_app = FastAPI(title="Geocodable Address API", version="1.0.0")

web_app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Your Vite dev server
        "http://localhost:3000",  # Common React dev port
        "https://demos.mathandpencil.com",  # Add your production domain
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

@web_app.post("/extract-address", response_model=GeocodeResponse)
async def extract_address(request: GeocodeRequest, token: str = Depends(verify_token)):
    """Extract geocodable address from ACORD data"""
    try:
        print(f"[API] =========================")
        print(f"[API] Received address extraction request")
        print(f"[API] Request type: {type(request)}")
        print(f"[API] Request acord_data type: {type(request.acord_data)}")
        print(f"[API] ACORD data keys: {list(request.acord_data.keys()) if isinstance(request.acord_data, dict) else 'NOT A DICT'}")
        print(f"[API] ACORD data (first 200 chars): {str(request.acord_data)[:200]}...")
        print(f"[API] =========================")

        # Call the Modal function
        print(f"[API] Calling extract_geocodable_address.remote() with data type: {type(request.acord_data)}")
        result = extract_geocodable_address.remote(request.acord_data)

        print(f"[API] =========================")
        print(f"[API] Extraction completed")
        print(f"[API] Result type: {type(result)}")
        print(f"[API] Result: {result}")
        print(f"[API] =========================")

        if "error" in result:
            print(f"[API] Returning error result")
            return JSONResponse(content=result, status_code=200)

        print(f"[API] Returning success result")
        return JSONResponse(content=result)

    except Exception as e:
        print(f"[API] EXCEPTION: {str(e)}")
        print(f"[API] Exception type: {type(e)}")
        import traceback
        print(f"[API] Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Address extraction failed: {str(e)}")

@web_app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "geocodable-address-api", "timestamp": time.time()}

# Deploy the web app
@app.function(image=image, secrets=[api_secret])
@modal.asgi_app()
def fastapi_app():
    return web_app

if __name__ == "__main__":
    # For local development
    import uvicorn
    uvicorn.run(web_app, host="0.0.0.0", port=8001)