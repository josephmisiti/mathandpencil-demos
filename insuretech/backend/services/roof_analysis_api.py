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
    text = text.replace("\n", " ")
    return text





def build_latex_report(
    *,
    job_id: str,
    model_id: str,
    analysis_data: dict,
    report_timestamp: str,
    image_filename: str,
) -> str:
    """Create a simplified LaTeX representation of the roof analysis report."""

    roof_analysis = analysis_data.get("roof_analysis", {}) if isinstance(analysis_data, dict) else {}
    quality = roof_analysis.get("quality", {}) if isinstance(roof_analysis, dict) else {}
    age = roof_analysis.get("age", {}) if isinstance(roof_analysis, dict) else {}
    shape = roof_analysis.get("shape", {}) if isinstance(roof_analysis, dict) else {}
    cover = roof_analysis.get("cover", {}) if isinstance(roof_analysis, dict) else {}
    overall = roof_analysis.get("overall_assessment", {}) if isinstance(roof_analysis, dict) else {}
    metadata = roof_analysis.get("image_analysis_metadata", {}) if isinstance(roof_analysis, dict) else {}

    def inline_value(value: object) -> str:
        if value in (None, "", [], {}):
            return r"\emph{Not provided}"
        if isinstance(value, (list, tuple)):
            items = [latex_escape(str(item)) for item in value if item]
            if not items:
                return r"\emph{Not provided}"
            return ", ".join(items)
        return latex_escape(str(value))

    def render_plain_list_lines(items: object) -> list[str]:
        if isinstance(items, str):
            normalized = [items]
        elif isinstance(items, (list, tuple)):
            normalized = [str(item) for item in items if item]
        else:
            normalized = []

        if not normalized:
            return [r"\emph{None provided}"]

        bullet_lines = [r"\begin{itemize}[leftmargin=1.3em]"]
        for entry in normalized:
            bullet_lines.append(f"    \\item {latex_escape(entry)}")
        bullet_lines.append(r"\end{itemize}")
        return bullet_lines

    def render_detail_list_lines(pairs: list[tuple[str, object]]) -> list[str]:
        items = [
            f"\\textbf{{{latex_escape(label)}:}} {inline_value(value)}"
            for label, value in pairs
        ]
        if not items:
            items = [r"\textbf{Details:} \emph{Not provided}"]

        bullet_lines = [r"\begin{itemize}[leftmargin=1.3em]"]
        for entry in items:
            bullet_lines.append(f"    \\item {entry}")
        bullet_lines.append(r"\end{itemize}")
        return bullet_lines

    def render_detail_section_lines(title: str, pairs: list[tuple[str, object]]) -> list[str]:
        return [
            f"\\subsection*{{{latex_escape(title)}}}",
            *render_detail_list_lines(pairs),
        ]

    def render_plain_list_section_lines(title: str, items: object) -> list[str]:
        return [
            f"\\subsection*{{{latex_escape(title)}}}",
            *render_plain_list_lines(items),
        ]

    def render_text_section_lines(title: str, text: object) -> list[str]:
        return [
            f"\\subsection*{{{latex_escape(title)}}}",
            inline_value(text),
        ]

    lines: list[str] = [
        r"\documentclass[11pt]{article}",
        r"\usepackage{geometry}",
        r"\usepackage{graphicx}",
        r"\usepackage{float}",
        r"\usepackage{enumitem}",
        r"\geometry{margin=1in}",
        r"\setlength{\parskip}{0.6em}",
        r"\setlength{\parindent}{0pt}",
        r"\setlist[itemize]{itemsep=0.2em, topsep=0.2em}",
        r"\begin{document}",
        "",
    ]

    lines.extend(
        [
            r"\begin{center}",
            r"{\Large\textbf{Roof Analysis Report}}\par",
            r"\vspace{0.5em}",
            f"Generated: {latex_escape(report_timestamp)}",
            r"\end{center}",
            "",
        ]
    )

    lines.append(r"\section*{Job Overview}")
    lines.extend(
        render_detail_list_lines(
            [
                ("Job ID", job_id),
                ("Model ID", model_id),
                ("Report generated", report_timestamp),
            ]
        )
    )
    lines.append("")

    lines.append(r"\section*{Inspection Image}")
    lines.extend(
        [
            r"\begin{figure}[H]",
            r"  \centering",
            f"  \\includegraphics[width=0.88\\textwidth]{{{image_filename}}}",
            r"  \caption{Roof area analyzed by the AI model.}",
            r"\end{figure}",
            "",
        ]
    )

    lines.append(r"\section*{Executive Summary}")
    lines.extend(render_text_section_lines("Overall condition", overall.get("summary")))
    lines.extend(render_plain_list_section_lines("Recommended next steps", overall.get("recommendations")))
    lines.extend(render_plain_list_section_lines("Assessment limitations", overall.get("analysis_limitations")))
    lines.append("")

    lines.append(r"\section*{Roof Condition}")
    lines.extend(
        render_detail_section_lines(
            "Quality Assessment",
            [
                ("Overall rating", quality.get("overall_rating")),
                ("Condition score", quality.get("condition_score")),
            ],
        )
    )
    lines.extend(render_plain_list_section_lines("Visible issues", quality.get("visible_issues")))
    lines.extend(render_plain_list_section_lines("Positive indicators", quality.get("quality_indicators")))
    lines.extend(render_text_section_lines("Analyst notes", quality.get("analysis_reasoning")))
    lines.extend(
        render_detail_section_lines(
            "Estimated Age",
            [
                ("Estimated age", age.get("estimated_age_years")),
                ("Age category", age.get("age_category")),
            ],
        )
    )
    lines.extend(render_plain_list_section_lines("Weathering indicators", age.get("weathering_indicators")))
    lines.extend(render_text_section_lines("Age notes", age.get("analysis_reasoning")))
    lines.extend(
        render_detail_section_lines(
            "Roof Geometry",
            [
                ("Primary shape", shape.get("primary_shape")),
                ("Complexity", shape.get("complexity")),
                ("Number of planes", shape.get("roof_planes")),
                ("Pitch estimate", shape.get("pitch_estimate")),
            ],
        )
    )
    lines.extend(render_plain_list_section_lines("Architectural features", shape.get("architectural_features")))
    lines.extend(render_text_section_lines("Geometry notes", shape.get("analysis_reasoning")))
    lines.extend(
        render_detail_section_lines(
            "Cover Material",
            [
                ("Material type", cover.get("material_type")),
                ("Confidence", cover.get("material_confidence")),
                ("Color", cover.get("color_description")),
                ("Texture", cover.get("texture_pattern")),
            ],
        )
    )
    lines.extend(render_plain_list_section_lines("Secondary materials", cover.get("secondary_materials")))
    lines.extend(render_text_section_lines("Cover notes", cover.get("analysis_reasoning")))
    lines.append("")

    lines.append(r"\section*{Image \& Analysis Metadata}")
    lines.extend(
        render_detail_list_lines(
            [
                ("Image quality", metadata.get("image_quality")),
                ("Viewing angle", metadata.get("viewing_angle")),
                ("Resolution adequacy", metadata.get("resolution_adequacy")),
                ("Weather conditions", metadata.get("weather_conditions")),
            ]
        )
    )

    lines.append(r"\end{document}")

    return "\n".join(lines)

def wait_for_path(path: str, *, timeout: float = 10.0, interval: float = 0.1) -> bool:
    """Poll until the given filesystem path exists or the timeout elapses."""
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


def _capture_latex_debug(tmpdir: str, latex_path: str, job_id: str) -> list[str]:
    """Persist LaTeX artifacts to the shared volume for post-mortem debugging."""

    debug_dir = "/my-volume/roof-analysis-results/debug"
    os.makedirs(debug_dir, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
    debug_base = f"{timestamp}_{job_id}"

    notes: list[str] = []

    latex_target = os.path.join(debug_dir, f"{debug_base}.tex")
    try:
        shutil.copy(latex_path, latex_target)
        notes.append(f"LaTeX source saved to {latex_target}")
    except Exception as exc:  # noqa: BLE001 - best effort only
        notes.append(f"Failed to copy LaTeX source: {exc}")

    log_source = os.path.join(tmpdir, "roof_analysis.log")
    if os.path.exists(log_source):
        log_target = os.path.join(debug_dir, f"{debug_base}.log")
        try:
            shutil.copy(log_source, log_target)
            notes.append(f"pdflatex log saved to {log_target}")
        except Exception as exc:  # noqa: BLE001
            notes.append(f"Failed to copy pdflatex log: {exc}")
    else:
        notes.append("pdflatex log not found")

    return notes


def _log_latex_source(job_id: str, latex_content: str, latex_path: str) -> None:
    """Log LaTeX source prior to compilation to aid debugging."""
    max_chars = 8000
    truncated = len(latex_content) > max_chars
    preview = latex_content[:max_chars]
    suffix = " [truncated]" if truncated else ""
    print(
        f"[ROOF] Job {job_id}: LaTeX source (saved at {latex_path}){suffix}\n{preview}"
    )
    if truncated:
        print(
            f"[ROOF] Job {job_id}: LaTeX source truncated to first {max_chars} characters for logging"
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

            _log_latex_source(job_id, latex_content, latex_path)

            pdflatex_command = ["pdflatex", "-interaction=nonstopmode", latex_filename]

            try:
                for _ in range(2):
                    subprocess.run(
                        pdflatex_command,
                        cwd=tmpdir,
                        check=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )
            except subprocess.CalledProcessError as exc:
                _capture_latex_debug(tmpdir, latex_path, job_id)

                error_output = ""
                if exc.stderr:
                    error_output = exc.stderr.decode("utf-8", errors="replace")
                elif exc.stdout:
                    error_output = exc.stdout.decode("utf-8", errors="replace")

                full_output = (error_output or "").strip()
                if full_output:
                    tail = full_output[-8000:]
                    prefix_note = "(truncated; showing last 8k chars)\n" if len(full_output) > 8000 else ""
                    print(
                        f"[ROOF] Job {job_id}: pdflatex output {prefix_note}{tail}"
                    )

                log_path = os.path.join(tmpdir, "roof_analysis.log")
                if os.path.exists(log_path):
                    try:
                        with open(log_path, "r", encoding="utf-8", errors="replace") as log_file:
                            log_tail = log_file.read()[-8000:]
                        print(
                            f"[ROOF] Job {job_id}: pdflatex log tail\n{log_tail}"
                        )
                    except Exception as log_exc:  # noqa: BLE001 - best effort
                        print(
                            f"[ROOF] Job {job_id}: failed to read pdflatex log ({log_exc})"
                        )

                raise ReportGenerationError(
                    "Report generation failed during LaTeX compilation",
                    error=error_output or str(exc),
                ) from exc

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
    except ReportGenerationError:
        raise
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
