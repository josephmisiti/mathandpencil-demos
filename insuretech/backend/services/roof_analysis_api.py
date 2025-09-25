import json
import modal
import os
from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Modal app setup
app = modal.App("roof-analysis-api")

# Secrets
api_secret = modal.Secret.from_name("acord-api-secret")
aws_secret = modal.Secret.from_name("aws-credentials")

# Modal base image with dependencies for both FastAPI and Bedrock calls
image = modal.Image.debian_slim().pip_install(
    "fastapi",
    "pydantic",
    "boto3",
    "botocore",
)

# Request model
class SaveImageRequest(BaseModel):
    image_data: str

volume = modal.Volume.from_name("insuretech-demos")

MODEL_ID = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"

ROOF_ANALYSIS_PROMPT = """
You are an expert roof analyst specializing in evaluating roofing systems from aerial satellite imagery. Analyze the uploaded Google satellite image and provide a comprehensive assessment of the roof's quality, age, shape, and cover type.

ANALYSIS REQUIREMENTS:
1. **Quality Assessment**: Evaluate the overall condition based on visible indicators such as:
   - Color uniformity and fading
   - Visible damage, missing materials, or repairs
   - Structural integrity indicators
   - Debris accumulation
   - Gutter and edge conditions

2. **Age Estimation**: Estimate the roof age based on:
   - Material weathering patterns
   - Color degradation
   - Visible wear indicators
   - Technology/style indicators for installation period

3. **Shape Analysis**: Describe the roof geometry including:
   - Basic shape classification (gable, hip, shed, mansard, etc.)
   - Complexity level (simple, moderate, complex)
   - Number of planes/sections
   - Pitch/slope assessment
   - Architectural features (dormers, chimneys, skylights)

4. **Cover Material Identification**: Determine the roofing material type:
   - Asphalt shingles, metal, tile, slate, membrane, etc.
   - Color and texture characteristics
   - Installation pattern if visible

RESPONSE FORMAT:
Provide your analysis as a valid JSON object with this exact structure:

{
  "roof_analysis": {
    "quality": {
      "overall_rating": "excellent|good|fair|poor",
      "condition_score": 1-10,
      "visible_issues": ["list", "of", "observed", "problems"],
      "quality_indicators": ["positive", "indicators", "observed"],
      "analysis_reasoning": "detailed explanation of quality assessment"
    },
    "age": {
      "estimated_age_years": "range (e.g., '10-15')",
      "age_category": "new|moderate|aging|old",
      "weathering_indicators": ["signs", "of", "age", "observed"],
      "analysis_reasoning": "explanation of age estimation methodology"
    },
    "shape": {
      "primary_shape": "roof shape classification",
      "complexity": "simple|moderate|complex",
      "roof_planes": "number of distinct sections",
      "pitch_estimate": "low|medium|steep",
      "architectural_features": ["dormers", "chimneys", "etc"],
      "analysis_reasoning": "description of shape analysis"
    },
    "cover": {
      "material_type": "primary material identification",
      "material_confidence": "high|medium|low",
      "color_description": "dominant color(s)",
      "texture_pattern": "observed surface texture",
      "secondary_materials": ["other", "materials", "if", "present"],
      "analysis_reasoning": "explanation of material identification"
    },
    "overall_assessment": {
      "summary": "brief overall condition summary",
      "recommendations": ["suggested", "actions", "or", "inspections"],
      "analysis_limitations": ["factors", "limiting", "assessment", "accuracy"]
    },
    "image_analysis_metadata": {
      "image_quality": "assessment of satellite image clarity",
      "viewing_angle": "overhead|oblique|unclear",
      "resolution_adequacy": "sufficient|limited|poor",
      "weather_conditions": "clear|cloudy|shadows|unclear"
    }
  }
}

IMPORTANT GUIDELINES:
- Base all assessments solely on what is visible in the satellite image
- Be honest about limitations and uncertainty levels
- Use conservative estimates when details are unclear
- Provide specific reasoning for each major conclusion
- Ensure the JSON is properly formatted and valid
- If any category cannot be assessed, explain why in the reasoning field
- Focus on observable features rather than assumptions
"""


@app.function(
    image=image,
    secrets=[aws_secret],
    volumes={"/my-volume": volume},
    timeout=300
)
def analyze_roof_image(image_data: str):
    import base64
    from datetime import datetime
    import boto3

    if not image_data:
        raise ValueError("No image data provided")

    # Handle data URLs and raw base64 payloads
    media_type = "image/png"
    file_extension = "png"

    if "," in image_data:
        header, base64_payload = image_data.split(",", 1)
        if header.startswith("data:") and ";base64" in header:
            media_type = header.split(":", 1)[1].split(";", 1)[0] or media_type
            if "/" in media_type:
                file_extension = media_type.split("/", 1)[1] or file_extension
    else:
        base64_payload = image_data

    file_extension = (file_extension or "png").replace("+", "_")

    try:
        image_bytes = base64.b64decode(base64_payload)
    except Exception as exc:
        raise ValueError(f"Invalid base64 image data: {exc}")

    # Persist the image for traceability
    timestamp = datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
    input_dir = "/my-volume/roof-analysis-results/inputs"
    os.makedirs(input_dir, exist_ok=True)
    image_path = os.path.join(input_dir, f"{timestamp}.{file_extension}")
    with open(image_path, "wb") as image_file:
        image_file.write(image_bytes)

    # Prepare Bedrock client
    bedrock_client = boto3.client(
        "bedrock-runtime",
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
        region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
    )

    request_body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4000,
        "temperature": 0.2,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": base64_payload,
                        },
                    },
                    {
                        "type": "text",
                        "text": ROOF_ANALYSIS_PROMPT,
                    },
                ],
            }
        ],
    })

    response = bedrock_client.invoke_model(
        body=request_body,
        modelId=MODEL_ID,
        accept="application/json",
        contentType="application/json",
    )

    response_body = json.loads(response.get("body").read())
    model_text = response_body.get("content", [{}])[0].get("text", "").strip()

    if not model_text:
        raise RuntimeError("Bedrock returned an empty response")

    cleaned_text = model_text
    if cleaned_text.startswith("```json"):
        cleaned_text = cleaned_text.replace("```json", "", 1)
    if cleaned_text.startswith("```"):
        cleaned_text = cleaned_text.replace("```", "", 1)
    if cleaned_text.endswith("```"):
        cleaned_text = cleaned_text[: -3]
    cleaned_text = cleaned_text.strip()

    try:
        parsed_response = json.loads(cleaned_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Failed to parse model response as JSON: {exc}")

    # Persist analysis output alongside the image
    output_dir = "/my-volume/roof-analysis-results/outputs"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{timestamp}.json")
    with open(output_path, "w", encoding="utf-8") as output_file:
        json.dump(parsed_response, output_file, ensure_ascii=False, indent=2)

    return {
        "model_id": MODEL_ID,
        "analysis": parsed_response,
        "artifacts": {
            "image_path": image_path,
            "analysis_path": output_path,
        },
    }


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
web_app = FastAPI(title="Roof Analysis API", version="1.0.0")

web_app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "https://demos.mathandpencil.com",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@web_app.post("/save-image")
def save_image(request: SaveImageRequest, token: str = Depends(verify_token)):
    try:
        result = analyze_roof_image.remote(request.image_data)
        return JSONResponse(content=result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Roof analysis failed: {exc}")


# Deploy the web app
@app.function(image=image, secrets=[api_secret])
@modal.asgi_app()
def fastapi_app():
    return web_app
