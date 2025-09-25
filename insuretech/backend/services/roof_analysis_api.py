import json
import os
import shutil
import subprocess
import tempfile
import time
import uuid
from datetime import datetime

import modal
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

# Modal app setup
app = modal.App("roof-analysis-api")

# Secrets
api_secret = modal.Secret.from_name("acord-api-secret")
aws_secret = modal.Secret.from_name("aws-credentials")

# Modal base image with dependencies for both FastAPI and Bedrock calls
image = (
    modal.Image.debian_slim()
    .apt_install(
        "texlive-latex-base",
        "texlive-latex-extra",
        "texlive-fonts-recommended",
        "texlive-pictures",
        "latexmk",
    )
    .pip_install(
        "fastapi",
        "pydantic",
        "boto3",
        "botocore",
    )
)

# Request model
class SaveImageRequest(BaseModel):
    image_data: str

volume = modal.Volume.from_name("insuretech-demos")
progress_store = modal.Dict.from_name("roof-analysis-progress-store")

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


class ReportGenerationError(Exception):
    """Raised when PDF report compilation fails."""

    def __init__(self, message: str, *, error: str | None = None):
        super().__init__(message)
        self.error = error


def latex_escape(value: str | None) -> str:
    """Escape special characters to keep LaTeX compilation stable."""
    if value is None:
        return "Unknown"

    text = str(value)
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    for original, escaped in replacements.items():
        text = text.replace(original, escaped)
    text = text.replace("\n", r"\\ ")
    return text


def format_value(value: object) -> str:
    """Convert arbitrary values into LaTeX-safe strings."""
    if value is None:
        return "Unknown"
    if isinstance(value, list):
        if not value:
            return "None"
        joined = ", ".join(str(item) for item in value)
        return latex_escape(joined)
    return latex_escape(str(value))


def build_latex_report(
    *,
    job_id: str,
    model_id: str,
    analysis_data: dict,
    report_timestamp: str,
    image_filename: str,
) -> str:
    """Create the LaTeX representation of the roof analysis report."""
    roof_analysis = analysis_data.get("roof_analysis", {})
    quality = roof_analysis.get("quality", {})
    age = roof_analysis.get("age", {})
    shape = roof_analysis.get("shape", {})
    cover = roof_analysis.get("cover", {})
    overall = roof_analysis.get("overall_assessment", {})
    metadata = roof_analysis.get("image_analysis_metadata", {})

    sections = [
        r"\section*{Roof Image}",
        r"\begin{figure}[H]",
        r"\centering",
        f"\\includegraphics[width=0.85\\textwidth]{{{image_filename}}}",
        r"\end{figure}",
        "",
        r"\section*{Job Summary}",
        f"\\textbf{{Job ID}}: {format_value(job_id)}\\",
        f"\\textbf{{Model ID}}: {format_value(model_id)}\\",
        f"\\textbf{{Generated At}}: {format_value(report_timestamp)}\\",
        "",
        r"\section*{Quality Assessment}",
        f"\\textbf{{Overall Rating}}: {format_value(quality.get('overall_rating'))}\\",
        f"\\textbf{{Condition Score}}: {format_value(quality.get('condition_score'))}\\",
        f"\\textbf{{Visible Issues}}: {format_value(quality.get('visible_issues'))}\\",
        f"\\textbf{{Quality Indicators}}: {format_value(quality.get('quality_indicators'))}\\",
        f"\\textbf{{Analysis Reasoning}}: {format_value(quality.get('analysis_reasoning'))}\\",
        "",
        r"\section*{Age Estimation}",
        f"\\textbf{{Estimated Age}}: {format_value(age.get('estimated_age_years'))}\\",
        f"\\textbf{{Age Category}}: {format_value(age.get('age_category'))}\\",
        f"\\textbf{{Weathering Indicators}}: {format_value(age.get('weathering_indicators'))}\\",
        f"\\textbf{{Analysis Reasoning}}: {format_value(age.get('analysis_reasoning'))}\\",
        "",
        r"\section*{Roof Shape}",
        f"\\textbf{{Primary Shape}}: {format_value(shape.get('primary_shape'))}\\",
        f"\\textbf{{Complexity}}: {format_value(shape.get('complexity'))}\\",
        f"\\textbf{{Roof Planes}}: {format_value(shape.get('roof_planes'))}\\",
        f"\\textbf{{Pitch Estimate}}: {format_value(shape.get('pitch_estimate'))}\\",
        f"\\textbf{{Architectural Features}}: {format_value(shape.get('architectural_features'))}\\",
        f"\\textbf{{Analysis Reasoning}}: {format_value(shape.get('analysis_reasoning'))}\\",
        "",
        r"\section*{Roof Cover Material}",
        f"\\textbf{{Material Type}}: {format_value(cover.get('material_type'))}\\",
        f"\\textbf{{Material Confidence}}: {format_value(cover.get('material_confidence'))}\\",
        f"\\textbf{{Color Description}}: {format_value(cover.get('color_description'))}\\",
        f"\\textbf{{Texture Pattern}}: {format_value(cover.get('texture_pattern'))}\\",
        f"\\textbf{{Secondary Materials}}: {format_value(cover.get('secondary_materials'))}\\",
        f"\\textbf{{Analysis Reasoning}}: {format_value(cover.get('analysis_reasoning'))}\\",
        "",
        r"\section*{Overall Assessment}",
        f"\\textbf{{Summary}}: {format_value(overall.get('summary'))}\\",
        f"\\textbf{{Recommendations}}: {format_value(overall.get('recommendations'))}\\",
        f"\\textbf{{Analysis Limitations}}: {format_value(overall.get('analysis_limitations'))}\\",
        "",
        r"\section*{Image Analysis Metadata}",
        f"\\textbf{{Image Quality}}: {format_value(metadata.get('image_quality'))}\\",
        f"\\textbf{{Viewing Angle}}: {format_value(metadata.get('viewing_angle'))}\\",
        f"\\textbf{{Resolution Adequacy}}: {format_value(metadata.get('resolution_adequacy'))}\\",
        f"\\textbf{{Weather Conditions}}: {format_value(metadata.get('weather_conditions'))}\\",
    ]

    sections_content = "\n".join(sections)

    return f"""\\documentclass[11pt]{{article}}
\\usepackage{{geometry}}
\\usepackage{{graphicx}}
\\usepackage{{float}}
\\usepackage{{enumitem}}
\\geometry{{margin=1in}}
\\setlist[itemize]{{itemsep=0pt, parsep=2pt, topsep=4pt}}
\\title{{Roof Analysis Report}}
\\date{{{latex_escape(report_timestamp)}}}
\\begin{{document}}
\\maketitle

{sections_content}

\\end{{document}}
"""


def wait_for_path(path: str, *, timeout: float = 10.0, interval: float = 0.25) -> bool:
    """Poll until the given path exists or the timeout elapses."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if os.path.exists(path):
            return True
        time.sleep(interval)
    return os.path.exists(path)


def update_progress(
    job_id: str,
    status: str,
    stage: str,
    progress: int,
    message: str,
    *,
    result: dict | None = None,
    error: str | None = None,
) -> None:
    payload = {
        "job_id": job_id,
        "status": status,
        "stage": stage,
        "progress": progress,
        "message": message,
        "timestamp": time.time(),
    }
    if result is not None:
        payload["result"] = result
    if error is not None:
        payload["error"] = error

    progress_store[job_id] = payload
    print(
        f"[ROOF] Job {job_id}: status={status} stage={stage} progress={progress} message='{message}'"
    )

def generate_roof_report(
    job_id: str,
    model_id: str,
    image_path: str,
    analysis_path: str,
) -> tuple[str, str]:
    """Compile the LaTeX report and return the PDF path and timestamp."""

    if not wait_for_path(image_path):
        raise ReportGenerationError(f"Roof image not found at {image_path}")
    if not wait_for_path(analysis_path):
        raise ReportGenerationError(f"Analysis JSON not found at {analysis_path}")

    with open(analysis_path, "r", encoding="utf-8") as analysis_file:
        analysis_data = json.load(analysis_file)

    report_timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            _, image_ext = os.path.splitext(image_path)
            local_image_name = f"roof_image{image_ext or '.png'}"
            local_image_path = os.path.join(tmpdir, local_image_name)
            shutil.copy(image_path, local_image_path)

            latex_content = build_latex_report(
                job_id=job_id,
                model_id=model_id,
                analysis_data=analysis_data,
                report_timestamp=report_timestamp,
                image_filename=local_image_name,
            )

            latex_filename = "roof_analysis.tex"
            latex_path = os.path.join(tmpdir, latex_filename)
            with open(latex_path, "w", encoding="utf-8") as latex_file:
                latex_file.write(latex_content)

            pdflatex_command = ["pdflatex", "-interaction=nonstopmode", latex_filename]
            for _ in range(2):
                subprocess.run(
                    pdflatex_command,
                    cwd=tmpdir,
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )

            pdf_source = os.path.join(tmpdir, "roof_analysis.pdf")
            if not os.path.exists(pdf_source):
                raise ReportGenerationError("Expected PDF artifact not produced by pdflatex")

            reports_dir = "/my-volume/roof-analysis-results/reports"
            os.makedirs(reports_dir, exist_ok=True)
            report_basename = os.path.splitext(os.path.basename(analysis_path))[0] or datetime.utcnow().strftime(
                "%Y-%m-%d_%H-%M-%S"
            )
            report_path = os.path.join(reports_dir, f"{report_basename}.pdf")
            shutil.move(pdf_source, report_path)

    except subprocess.CalledProcessError as exc:
        error_output = ""
        if exc.stderr:
            error_output = exc.stderr.decode("utf-8", errors="replace")
        elif exc.stdout:
            error_output = exc.stdout.decode("utf-8", errors="replace")
        raise ReportGenerationError(
            "Report generation failed during LaTeX compilation",
            error=error_output or str(exc),
        ) from exc
    except Exception as exc:  # noqa: BLE001 - bubble up rich error detail
        raise ReportGenerationError(str(exc)) from exc

    return report_path, report_timestamp


@app.function(
    image=image,
    secrets=[aws_secret],
    volumes={"/my-volume": volume},
    timeout=300
)
def process_roof_analysis(image_data: str, job_id: str):
    import base64
    import boto3

    try:
        if not image_data:
            raise ValueError("No image data provided")

        # Handle data URLs and raw base64 payloads
        media_type = "image/png"
        file_extension = "png"

        update_progress(
            job_id,
            status="processing",
            stage="received",
            progress=5,
            message="Image received, preparing for analysis"
        )

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
            update_progress(
                job_id,
                status="failed",
                stage="decode_error",
                progress=0,
                message="Failed to decode image data",
                error=str(exc),
            )
            raise ValueError(f"Invalid base64 image data: {exc}") from exc

        # Persist the image for traceability
        timestamp = datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
        input_dir = "/my-volume/roof-analysis-results/inputs"
        os.makedirs(input_dir, exist_ok=True)
        image_path = os.path.join(input_dir, f"{timestamp}.{file_extension}")
        with open(image_path, "wb") as image_file:
            image_file.write(image_bytes)

        update_progress(
            job_id,
            status="processing",
            stage="image_saved",
            progress=20,
            message="Image saved to analysis volume"
        )

        # Prepare Bedrock client
        bedrock_client = boto3.client(
            "bedrock-runtime",
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
            region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
        )

        update_progress(
            job_id,
            status="processing",
            stage="invoking_model",
            progress=45,
            message="Sending roof image to Bedrock model"
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
            update_progress(
                job_id,
                status="failed",
                stage="empty_response",
                progress=60,
                message="Bedrock returned an empty response",
                error="Empty response",
            )
            raise RuntimeError("Bedrock returned an empty response")

        update_progress(
            job_id,
            status="processing",
            stage="parsing_response",
            progress=65,
            message="Parsing roof analysis response"
        )

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
            update_progress(
                job_id,
                status="failed",
                stage="json_parse_error",
                progress=70,
                message="Failed to parse model response",
                error=str(exc),
            )
            raise RuntimeError(f"Failed to parse model response as JSON: {exc}")

        # Persist analysis output alongside the image
        output_dir = "/my-volume/roof-analysis-results/outputs"
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"{timestamp}.json")
        with open(output_path, "w", encoding="utf-8") as output_file:
            json.dump(parsed_response, output_file, ensure_ascii=False, indent=2)

        result_payload = {
            "model_id": MODEL_ID,
            "analysis": parsed_response,
            "artifacts": {
                "image_path": image_path,
                "analysis_path": output_path,
            },
        }

        update_progress(
            job_id,
            status="processing",
            stage="analysis_complete",
            progress=75,
            message="Roof analysis completed, preparing report",
            result=result_payload,
        )

        update_progress(
            job_id,
            status="processing",
            stage="report_generation",
            progress=85,
            message="Generating roof analysis report",
            result=result_payload,
        )

        try:
            report_path, report_timestamp = generate_roof_report(
                job_id,
                MODEL_ID,
                image_path,
                output_path,
            )
        except ReportGenerationError as exc:
            update_progress(
                job_id,
                status="failed",
                stage="report_generation_error",
                progress=90,
                message=str(exc) or "Report generation failed",
                error=exc.error or str(exc),
            )
            raise

        artifacts = result_payload.setdefault("artifacts", {})
        artifacts["report_path"] = report_path
        result_payload["report_generated_at"] = report_timestamp

        update_progress(
            job_id,
            status="completed",
            stage="finished",
            progress=100,
            message="Roof analysis report generated",
            result=result_payload,
        )

        return result_payload

    except Exception as exc:
        if job_id in progress_store:
            current = progress_store[job_id]
            if current.get("status") != "failed":
                update_progress(
                    job_id,
                    status="failed",
                    stage="error",
                    progress=current.get("progress", 0) or 0,
                    message="Roof analysis failed",
                    error=str(exc),
                )
        else:
            update_progress(
                job_id,
                status="failed",
                stage="error",
                progress=0,
                message="Roof analysis failed",
                error=str(exc),
            )
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
web_app = FastAPI(title="Roof Analysis API", version="1.0.0")

web_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"]
)


@web_app.post("/save-image")
def save_image(request: SaveImageRequest, token: str = Depends(verify_token)):
    job_id = str(uuid.uuid4())

    update_progress(
        job_id,
        status="queued",
        stage="uploaded",
        progress=5,
        message="Image uploaded, queued for processing"
    )

    process_roof_analysis.spawn(request.image_data, job_id)

    return JSONResponse(
        content={
            "job_id": job_id,
            "status": "queued",
            "message": "Image queued for roof analysis",
        }
    )


@web_app.get("/progress/{job_id}")
def get_progress(job_id: str, token: str = Depends(verify_token)):
    if job_id not in progress_store:
        raise HTTPException(status_code=404, detail="Job not found")

    return JSONResponse(progress_store[job_id])


@web_app.get("/report/{job_id}")
def download_report(job_id: str, token: str = Depends(verify_token)):
    if job_id not in progress_store:
        raise HTTPException(status_code=404, detail="Job not found")

    payload = progress_store[job_id]
    result = payload.get("result") or {}
    artifacts = result.get("artifacts") or {}
    report_path = artifacts.get("report_path")

    if not report_path or not os.path.exists(report_path):
        raise HTTPException(status_code=404, detail="Report not available")

    filename = os.path.basename(report_path) or "roof_analysis.pdf"
    return FileResponse(report_path, media_type="application/pdf", filename=filename)


# Deploy the web app
@app.function(image=image, secrets=[api_secret], volumes={"/my-volume": volume})
@modal.asgi_app()
def fastapi_app():
    return web_app
