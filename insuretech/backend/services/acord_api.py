import modal
import os
import json
import base64
import uuid
import time
from pathlib import Path
from typing import Dict, Optional
from io import BytesIO
from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, Header
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware

# Modal app setup
app = modal.App("acord-processing-api")

# AWS credentials
aws_secret = modal.Secret.from_name("aws-credentials")

# API authentication
api_secret = modal.Secret.from_name("acord-api-secret")

# Modal image with dependencies
image = modal.Image.debian_slim().pip_install(
    "fastapi",
    "boto3",
    "botocore",
    "PyPDF2",
    "pdf2image",
    "Pillow",
    "python-multipart"
).apt_install(
    "poppler-utils"
)

# Shared progress tracking using Modal Dict
progress_store = modal.Dict.from_name("acord-progress-store")

# ACORD prompts (same as bin/acord.py)
ACORD_125_PROMPT = """You are a data extraction specialist. Extract ALL information from the provided ACORD 125 insurance form document and return it in valid JSON format only. Do not include any explanatory text, comments, or markdown formatting - return only the JSON object.

Instructions:
1. Extract every field visible in the document, even if empty
2. Use null for empty/blank fields
3. Use boolean true/false for checkboxes (☒ = true, ☐ = false)
4. Preserve exact text formatting and spacing where relevant
5. Return only valid JSON - no additional text or formatting

JSON Structure:
{
  "agency_customer_id": "",
  "contact_information": {
    "accounting_records": {
      "contact_name": "",
      "primary_phone": {
        "number": "",
        "type": {
          "home": false,
          "business": false,
          "cell": false
        }
      },
      "secondary_phone": {
        "number": "",
        "type": {
          "home": false,
          "business": false,
          "cell": false
        }
      },
      "primary_email": "",
      "secondary_email": ""
    },
    "inspection": {
      "contact_name": "",
      "primary_phone": {
        "number": "",
        "type": {
          "home": false,
          "business": false,
          "cell": false
        }
      },
      "secondary_phone": {
        "number": "",
        "type": {
          "home": false,
          "business": false,
          "cell": false
        }
      },
      "primary_email": "",
      "secondary_email": ""
    }
  },
  "premises_information": [
    {
      "location_number": "",
      "building_number": "",
      "street": "",
      "city": "",
      "state": "",
      "county": "",
      "zip": "",
      "city_limits": {
        "inside": false,
        "outside": false
      },
      "interest": {
        "owner": false,
        "tenant": false
      },
      "full_time_employees": "",
      "part_time_employees": "",
      "annual_revenues": "",
      "occupied_area_sq_ft": "",
      "open_to_public_area_sq_ft": "",
      "total_building_area_sq_ft": "",
      "any_area_leased_to_others": "",
      "description_of_operations": ""
    }
  ],
  "nature_of_business": {
    "apartments": false,
    "condominiums": false,
    "contractor": false,
    "institutional": false,
    "manufacturing": false,
    "office": false,
    "restaurant": false,
    "retail": false,
    "service": false,
    "wholesale": false
  },
  "description_of_primary_operations": "",
  "date_business_started": "",
  "retail_stores_or_service_operations": {
    "installation_service_repair_work_percentage": "",
    "off_premises_installation_service_repair_work_percentage": ""
  },
  "description_of_operations_other_named_insureds": "",
  "additional_interest": {
    "interest_types": {
      "additional": false,
      "insured": false,
      "breach_of_warranty": false,
      "co_owner": false,
      "employee": false,
      "as_lessor": false,
      "leaseback": false,
      "lenders_loss_payable": false,
      "lienholder": false,
      "loss_payee": false,
      "mortgagee": false,
      "owner": false,
      "registrant": false,
      "trustee": false
    },
    "name_and_address": "",
    "rank": "",
    "reference_loan_number": "",
    "evidence": "",
    "certificate": false,
    "policy": false,
    "send_bill": false,
    "interest_in_item_number": "",
    "interest_end_date": "",
    "lien_amount": "",
    "phone": "",
    "fax": "",
    "email_address": "",
    "reason_for_interest": "",
    "location": "",
    "building": "",
    "vehicle": "",
    "boat": "",
    "airport": "",
    "aircraft": "",
    "item": "",
    "class": "",
    "item_description": ""
  }
}

Extract all data from the document and populate this JSON structure with the actual values found in the form. Return only the completed JSON object."""

ACORD_140_PROMPT = """You are a data extraction specialist. Extract ALL information from the provided ACORD 140 Property Section insurance form document and return it in valid JSON format only. Do not include any explanatory text, comments, or markdown formatting - return only the JSON object.

Instructions:
1. Extract every field visible in the document, even if empty
2. Use null for empty/blank fields
3. Use boolean true/false for checkboxes (☒ = true, ☐ = false, X = true)
4. Preserve exact text formatting and spacing where relevant
5. Return only valid JSON - no additional text or formatting

JSON Structure:
{
  "agency_customer_id": "",
  "date": "",
  "agency_name": "",
  "carrier": "",
  "naic_code": "",
  "policy_number": "",
  "effective_date": "",
  "named_insured": "",
  "blanket_summary": [
    {
      "blanket_number": "",
      "amount": "",
      "type": ""
    }
  ],
  "premises_information": {
    "premises_number": "",
    "street_address": "",
    "building_number": "",
    "building_description": "",
    "occupancy": ""
  },
  "subject_of_insurance": [
    {
      "subject": "",
      "amount": "",
      "coins_percentage": "",
      "valuation": "",
      "causes_of_loss": "",
      "inflation_guard_percentage": "",
      "deductible": "",
      "deductible_type": "",
      "blanket_number": "",
      "forms_and_conditions_to_apply": ""
    }
  ],
  "additional_information": {
    "business_income_extra_expense": "",
    "value_reporting_information": ""
  },
  "additional_coverages": {
    "spoilage_coverage": {
      "enabled": false,
      "description_of_property_covered": "",
      "limit": "",
      "deductible": "",
      "refrigeration_maintenance_agreement": false
    },
    "options": {
      "breakdown_or_contamination": false,
      "power_outage": false,
      "selling_price": false
    },
    "sinkhole_coverage": {
      "required_in_florida": true,
      "accept_coverage": false,
      "reject_coverage": false,
      "limit": ""
    },
    "mine_subsidence_coverage": {
      "required_states": ["IL", "IN", "KY", "WV"],
      "accept_coverage": false,
      "reject_coverage": false,
      "limit": "",
      "deductible": "",
      "type": ""
    }
  },
  "construction_details": {
    "construction_type": "",
    "distance_to_hydrant": {
      "feet": "",
      "miles": ""
    },
    "fire_district": "",
    "code_number": "",
    "protection_class": "",
    "number_of_stories": "",
    "number_of_basements": "",
    "year_built": "",
    "total_area": "",
    "building_code": "",
    "tax_code": "",
    "roof_type": "",
    "other_occupancies": "",
    "grade": "",
    "wind_class": {
      "semi_resistive": false,
      "resistive": false
    },
    "property_designated_historical_landmark": ""
  },
  "building_improvements": {
    "wiring_year": "",
    "roofing_year": "",
    "plumbing_year": "",
    "heating_year": "",
    "other_year": ""
  },
  "heating_source": {
    "including_woodburning": false,
    "stove_or_fireplace_insert": false,
    "manufacturer": "",
    "date_installed": "",
    "primary_heat": {
      "boiler": false,
      "solid_fuel": false,
      "insurance_placed_elsewhere": ""
    },
    "secondary_heat": {
      "boiler": false,
      "solid_fuel": false,
      "insurance_placed_elsewhere": ""
    }
  },
  "fire_protection": {
    "premises_fire_protection": {
      "sprinklers_standpipes_co2_chemical": true,
      "sprinkler_percentage": "",
      "central_station": false,
      "local_gong": false
    },
    "fire_alarm": {
      "manufacturer": "",
      "central_station": false,
      "local_gong": false
    }
  },
  "burglar_alarm": {
    "type": "",
    "certificate_number": "",
    "expiration_date": "",
    "installed_and_serviced_by": "",
    "extent": "",
    "grade": "",
    "central_with_keys": false,
    "number_of_guards_watchmen": "",
    "clock_hourly": false
  },
  "exposures": {
    "right_exposure_distance": "",
    "left_exposure_distance": "",
    "front_exposure_distance": "",
    "rear_exposure_distance": "",
    "number_of_open_sides_on_structure": ""
  },
  "additional_interest": {
    "acord_45_attached": false,
    "interest_types": {
      "loss_payee": false,
      "mortgagee": false
    },
    "name_and_address": "",
    "rank": "",
    "evidence": "",
    "certificate": false,
    "reference_loan_number": "",
    "interest_in_item_number": "",
    "location": "",
    "building": "",
    "item": "",
    "class": "",
    "item_description": ""
  }
}

Extract all data from the document and populate this JSON structure with the actual values found in the form. Return only the completed JSON object."""

def update_progress(job_id: str, status: str, stage: str, progress: float, message: str = "", error: str = "", result: dict = None):
    """Update progress for a job"""
    progress_data = {
        "job_id": job_id,
        "status": status,  # queued, processing, completed, failed
        "stage": stage,
        "progress": progress,  # 0-100
        "message": message,
        "error": error,
        "result": result,
        "timestamp": time.time()
    }
    progress_store[job_id] = progress_data
    print(f"[PROGRESS] Updated {job_id}: {status} | {stage} | {progress}% | {message}")

def determine_acord_type(ocr_text: str) -> str:
    """Determine ACORD type from OCR text"""
    ocr_upper = ocr_text.upper()
    if "ACORD 125" in ocr_upper or "125" in ocr_upper:
        return "125"
    elif "ACORD 140" in ocr_upper or "140" in ocr_upper:
        return "140"
    else:
        return "125"  # Default

@app.function(
    image=image,
    secrets=[aws_secret],
    timeout=600
)
def process_acord_document(pdf_bytes: bytes, job_id: str):
    """Process ACORD document with Claude"""
    import boto3
    from botocore.exceptions import ClientError
    from pdf2image import convert_from_bytes

    print(f"[{job_id}] Starting ACORD processing...")

    try:
        print(f"[{job_id}] Updating progress to initializing...")
        update_progress(job_id, "processing", "initializing", 10, "Initializing AWS connection...")

        print(f"[{job_id}] Setting up Bedrock client...")
        # Setup Bedrock client
        bedrock_client = boto3.client(
            'bedrock-runtime',
            aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
            region_name=os.environ.get('AWS_DEFAULT_REGION', 'us-east-1')
        )
        print(f"[{job_id}] Bedrock client created successfully")

        print(f"[{job_id}] Converting PDF to image...")
        update_progress(job_id, "processing", "converting", 25, "Converting PDF to image...")

        # Convert PDF to image
        images = convert_from_bytes(pdf_bytes, dpi=300)
        if not images:
            raise Exception("No images generated from PDF")

        # Use first page
        image = images[0]
        print(f"[{job_id}] PDF converted to {len(images)} image(s)")

        print(f"[{job_id}] Starting OCR with Claude...")
        update_progress(job_id, "processing", "ocr", 50, "Performing OCR with Claude...")

        # Convert image to base64
        buffer = BytesIO()
        image.save(buffer, format='PNG')
        image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

        # OCR with Claude
        ocr_prompt = "Extract all text from this document. Preserve the original formatting and structure as much as possible, including line breaks, paragraphs, and spacing."

        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4000,
            "temperature": 0.1,
            "messages": [{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": image_base64
                        }
                    },
                    {"type": "text", "text": ocr_prompt}
                ]
            }]
        })

        response = bedrock_client.invoke_model(
            body=body,
            modelId="us.anthropic.claude-3-5-sonnet-20241022-v2:0",
            accept='application/json',
            contentType='application/json'
        )

        response_body = json.loads(response.get('body').read())
        ocr_text = response_body.get('content', [{}])[0].get('text', '')

        if not ocr_text:
            raise Exception("No text extracted from document")

        update_progress(job_id, "processing", "extraction", 75, "Extracting structured data...")

        # Determine ACORD type and extract data
        acord_type = determine_acord_type(ocr_text)

        if acord_type == "140":
            extraction_prompt = ACORD_140_PROMPT
            prompt_text = f"ACORD 140 Document Text:\n\n{ocr_text}\n\n{extraction_prompt}"
        else:
            extraction_prompt = ACORD_125_PROMPT
            prompt_text = f"ACORD 125 Document Text:\n\n{ocr_text}\n\n{extraction_prompt}"

        # Extract structured data
        extraction_body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4000,
            "temperature": 0.1,
            "messages": [{
                "role": "user",
                "content": prompt_text
            }]
        })

        extraction_response = bedrock_client.invoke_model(
            body=extraction_body,
            modelId="us.anthropic.claude-3-5-sonnet-20241022-v2:0",
            accept='application/json',
            contentType='application/json'
        )

        extraction_body_response = json.loads(extraction_response.get('body').read())
        extraction_text = extraction_body_response.get('content', [{}])[0].get('text', '')

        # Parse JSON response
        try:
            # Clean response
            cleaned_response = extraction_text.strip()
            if cleaned_response.startswith('```json'):
                cleaned_response = cleaned_response.replace('```json', '').replace('```', '').strip()
            elif cleaned_response.startswith('```'):
                cleaned_response = cleaned_response.replace('```', '').strip()

            extracted_data = json.loads(cleaned_response)

            result = {
                "acord_type": acord_type,
                "ocr_text": ocr_text,
                "extracted_data": extracted_data,
                "text_length": len(ocr_text)
            }

            update_progress(job_id, "completed", "finished", 100, "Processing completed successfully", result=result)
            return result

        except json.JSONDecodeError as e:
            error_msg = f"JSON parsing failed: {str(e)}"
            result = {
                "acord_type": acord_type,
                "ocr_text": ocr_text,
                "raw_extraction_response": extraction_text,
                "error": error_msg,
                "text_length": len(ocr_text)
            }
            update_progress(job_id, "completed", "finished", 100, "Processing completed with parsing issues", result=result)
            return result

    except Exception as e:
        error_msg = f"Processing failed: {str(e)}"
        update_progress(job_id, "failed", "error", 0, error_msg, error=error_msg)
        raise

# Authentication setup
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
web_app = FastAPI(title="ACORD Processing API", version="1.0.0")

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

@web_app.post("/upload")
async def upload_acord(file: UploadFile = File(...), token: str = Depends(verify_token)):
    """Upload and process an ACORD PDF document"""
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="File must be a PDF")

    try:
        # Generate job ID
        job_id = str(uuid.uuid4())
        print(f"[UPLOAD] Generated job ID: {job_id}")

        # Read PDF file
        pdf_bytes = await file.read()
        print(f"[UPLOAD] Read PDF file: {len(pdf_bytes)} bytes")

        # Initialize progress
        update_progress(job_id, "queued", "uploaded", 5, "File uploaded, queuing for processing...")
        print(f"[UPLOAD] Progress initialized for job {job_id}")

        # Process asynchronously
        print(f"[UPLOAD] Spawning background processing for job {job_id}")
        process_acord_document.spawn(pdf_bytes, job_id)
        print(f"[UPLOAD] Background processing spawned for job {job_id}")

        return JSONResponse({
            "job_id": job_id,
            "status": "queued",
            "message": "File uploaded successfully and queued for processing"
        })

    except Exception as e:
        print(f"[UPLOAD] Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@web_app.get("/progress/{job_id}")
async def get_progress(job_id: str, token: str = Depends(verify_token)):
    """Get processing progress for a job"""
    try:
        if job_id not in progress_store:
            print(f"[PROGRESS] Job {job_id} not found in progress store")
            raise HTTPException(status_code=404, detail="Job not found")

        progress_data = progress_store[job_id]
        print(f"[PROGRESS] Retrieved progress for {job_id}: {progress_data.get('status')} | {progress_data.get('stage')}")
        return JSONResponse(progress_data)
    except Exception as e:
        print(f"[PROGRESS] Error retrieving progress for {job_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving progress: {str(e)}")

@web_app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": time.time()}

# Deploy the web app
@app.function(image=image, secrets=[api_secret])
@modal.asgi_app()
def fastapi_app():
    return web_app

if __name__ == "__main__":
    # For local development
    import uvicorn
    uvicorn.run(web_app, host="0.0.0.0", port=8000)