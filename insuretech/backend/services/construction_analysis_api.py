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
app = modal.App("construction-analysis-api")

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
progress_store = modal.Dict.from_name("construction-analysis-progress-store")

MODEL_ID = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"

BUILDING_ANALYSIS_PROMPT = """
You are an expert building analyst specializing in property risk assessment for Excess & Surplus (E&S) lines insurance. Analyze the uploaded front-facing building photograph and provide a comprehensive assessment suitable for underwriting commercial property risks.

ANALYSIS REQUIREMENTS:

1. **Construction Type Classification**: Evaluate structural system based on:
   - Frame type (steel frame, concrete frame, masonry bearing wall, wood frame)
   - Wall construction materials (brick, concrete, steel, wood, composite)
   - Foundation indicators visible at grade level
   - Structural integrity visual indicators
   - Fire-resistive characteristics of materials observed

2. **Occupancy Assessment**: Determine likely building use based on:
   - Architectural style and design elements
   - Window patterns and commercial/industrial features
   - Signage, loading docks, or use-specific elements
   - Ground floor characteristics (retail, office, industrial, etc.)
   - Mixed-use indicators if present

3. **Physical Characteristics**: Document building attributes including:
   - Number of stories/floors visible
   - Building height estimation
   - Facade condition and maintenance level
   - Architectural features (balconies, overhangs, decorative elements)
   - Accessibility features (ramps, wide entrances)

4. **Construction Materials Analysis**: Identify exterior materials:
   - Primary wall materials (brick, concrete, metal siding, glass, etc.)
   - Window types (single/double pane, commercial grade, residential style)
   - Roofing material visible from front view
   - Trim and accent materials
   - Material quality and condition assessment

5. **Risk Factors Identification**: Assess potential hazards:
   - Fire spread potential based on materials and design
   - Natural catastrophe vulnerabilities (earthquake, wind, flood indicators)
   - Security features or lack thereof
   - Proximity hazards from adjacent structures
   - Environmental factors (trees, power lines, topography)

6. **Age and Condition Assessment**: Evaluate building vintage and maintenance:
   - Estimated construction era based on architectural style
   - Visible wear, weathering, or deterioration
   - Recent renovations or updates evident
   - Deferred maintenance indicators
   - Code compliance vintage indicators

7. **AIR/RMS Classification Compatibility**: Provide standard industry codes:
   - Likely AIR Construction Class Code (100-series)
   - Likely AIR Occupancy Class Code (300-series)
   - ISO Occupancy Type (0-9 classification)
   - RMS Industrial codes if applicable

RESPONSE FORMAT:
Provide your analysis as a valid JSON object with this exact structure:

{
  "building_analysis": {
    "construction_type": {
      "primary_structural_system": "steel_frame|concrete_frame|masonry_bearing|wood_frame|mixed",
      "wall_construction": "brick|concrete|steel|wood|composite|mixed",
      "construction_class": "fire_resistive|non_combustible|ordinary|heavy_timber|wood_frame",
      "air_construction_code": "estimated 3-digit AIR code",
      "construction_confidence": "high|medium|low",
      "structural_indicators": ["visible", "structural", "elements"],
      "analysis_reasoning": "detailed explanation of construction type determination"
    },
    "occupancy_assessment": {
      "primary_use": "office|retail|industrial|warehouse|mixed_use|residential|institutional|other",
      "secondary_uses": ["additional", "uses", "if", "mixed"],
      "air_occupancy_code": "estimated 3-digit AIR code",
      "iso_occupancy_type": "0-9 classification",
      "occupancy_confidence": "high|medium|low",
      "use_indicators": ["signs", "architectural", "features", "supporting", "determination"],
      "analysis_reasoning": "explanation of occupancy classification"
    },
    "physical_characteristics": {
      "story_count": "number of floors visible",
      "estimated_height_feet": "building height estimate",
      "building_width_estimate": "approximate facade width",
      "architectural_style": "modern|traditional|industrial|mid_century|contemporary|other",
      "notable_features": ["distinctive", "architectural", "elements"],
      "accessibility_features": ["ramps", "wide_doors", "etc"],
      "analysis_reasoning": "description of physical assessment methodology"
    },
    "construction_materials": {
      "primary_wall_material": "brick|concrete|metal|wood|glass|composite",
      "secondary_materials": ["other", "materials", "present"],
      "window_type": "commercial|residential|industrial|mixed",
      "material_quality": "high_grade|standard|basic|deteriorated",
      "visible_roof_material": "material visible from front angle",
      "material_condition": "excellent|good|fair|poor",
      "analysis_reasoning": "explanation of material identification and assessment"
    },
    "risk_factors": {
      "fire_risk_level": "low|moderate|high|very_high",
      "nat_cat_vulnerabilities": ["earthquake", "wind", "flood", "wildfire", "other"],
      "proximity_hazards": ["adjacent", "risk", "sources"],
      "security_level": "high|moderate|basic|poor",
      "environmental_factors": ["trees", "power_lines", "topography", "other"],
      "overall_risk_profile": "low|moderate|high|very_high",
      "analysis_reasoning": "detailed risk factor assessment"
    },
    "age_condition": {
      "estimated_age_range": "construction era (e.g., '1980-1990')",
      "condition_rating": "excellent|good|fair|poor",
      "condition_score": "1-10 scale",
      "maintenance_level": "well_maintained|adequately_maintained|deferred_maintenance|poor_maintenance",
      "renovation_indicators": ["visible", "updates", "or", "modifications"],
      "deterioration_signs": ["weathering", "damage", "wear", "indicators"],
      "analysis_reasoning": "explanation of age and condition assessment"
    },
    "insurance_classifications": {
      "suggested_air_construction": "3-digit code with description",
      "suggested_air_occupancy": "3-digit code with description",
      "iso_occupancy_type": "code with description",
      "rms_codes": "if applicable for industrial properties",
      "classification_confidence": "high|medium|low",
      "alternative_codes": ["other", "possible", "classifications"],
      "analysis_reasoning": "explanation of code selection methodology"
    },
    "underwriting_considerations": {
      "key_strengths": ["positive", "risk", "factors"],
      "key_concerns": ["areas", "of", "elevated", "risk"],
      "recommended_inspections": ["suggested", "detailed", "assessments"],
      "coverage_considerations": ["specific", "coverage", "needs", "or", "exclusions"],
      "pricing_factors": ["elements", "affecting", "premium", "calculation"]
    },
    "overall_assessment": {
      "property_summary": "concise overall building description",
      "insurability": "standard|preferred|substandard|declined",
      "key_recommendations": ["primary", "underwriting", "recommendations"],
      "analysis_limitations": ["factors", "limiting", "assessment", "from", "single", "photo"]
    },
    "image_analysis_metadata": {
      "photo_quality": "excellent|good|fair|poor",
      "viewing_angle": "straight_on|slight_angle|oblique|unclear",
      "lighting_conditions": "good|adequate|poor|shadows",
      "distance_from_building": "close|medium|far|unclear",
      "obstructions": ["trees", "signs", "other", "blocking", "elements"]
    }
  }
}

IMPORTANT GUIDELINES:
- Base all assessments solely on what is visible in the front-facing photograph
- Use insurance industry standard terminology and classifications
- Be conservative with risk assessments when details are unclear
- Provide specific reasoning for each major classification decision
- Reference AIR, RMS, and ISO standards where applicable
- Note limitations when building sides/rear are not visible
- Consider E&S market appetite for the identified risk profile
- Ensure JSON formatting is valid and complete
- If any category cannot be assessed from the single view, explain why
- Focus on observable features that impact insurance risk and pricing
- Consider both primary and catastrophic perils in risk assessment
- Ensure the JSON is properly formatted and complete
- If any category cannot be assessed from the single view, explain why
- Focus on observable features that impact insurance risk and pricing
- Consider both primary and catastrophic perils in risk assessment
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
    """Create the LaTeX representation of the building analysis report."""

    building_analysis = analysis_data.get("building_analysis", {}) if isinstance(analysis_data, dict) else {}
    construction = building_analysis.get("construction_type", {}) if isinstance(building_analysis, dict) else {}
    occupancy = building_analysis.get("occupancy_assessment", {}) if isinstance(building_analysis, dict) else {}
    physical = building_analysis.get("physical_characteristics", {}) if isinstance(building_analysis, dict) else {}
    materials = building_analysis.get("construction_materials", {}) if isinstance(building_analysis, dict) else {}
    risk = building_analysis.get("risk_factors", {}) if isinstance(building_analysis, dict) else {}
    age_condition = building_analysis.get("age_condition", {}) if isinstance(building_analysis, dict) else {}
    classifications = building_analysis.get("insurance_classifications", {}) if isinstance(building_analysis, dict) else {}
    underwriting = building_analysis.get("underwriting_considerations", {}) if isinstance(building_analysis, dict) else {}
    overall = building_analysis.get("overall_assessment", {}) if isinstance(building_analysis, dict) else {}
    metadata = building_analysis.get("image_analysis_metadata", {}) if isinstance(building_analysis, dict) else {}

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
            bullet_lines.append(f"    \item {latex_escape(entry)}")
        bullet_lines.append(r"\end{itemize}")
        return bullet_lines

    def render_detail_list_lines(pairs: list[tuple[str, object]]) -> list[str]:
        items = [
            f"\textbf{{{latex_escape(label)}:}} {inline_value(value)}"
            for label, value in pairs
        ]
        if not items:
            items = [r"\textbf{Details:} \emph{Not provided}"]

        bullet_lines = [r"\begin{itemize}[leftmargin=1.3em]"]
        for entry in items:
            bullet_lines.append(f"    \item {entry}")
        bullet_lines.append(r"\end{itemize}")
        return bullet_lines

    def render_detail_section_lines(title: str, pairs: list[tuple[str, object]]) -> list[str]:
        return [
            f"\subsection*{{{latex_escape(title)}}}",
            *render_detail_list_lines(pairs),
        ]

    def render_plain_list_section_lines(title: str, items: object) -> list[str]:
        return [
            f"\subsection*{{{latex_escape(title)}}}",
            *render_plain_list_lines(items),
        ]

    def render_text_section_lines(title: str, text: object) -> list[str]:
        return [
            f"\subsection*{{{latex_escape(title)}}}",
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
            r"{\Large\textbf{Building Analysis Report}}\par",
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
            f"  \includegraphics[width=0.88\textwidth]{{{image_filename}}}",
            r"  \caption{Building frontage analyzed by the AI model.}",
            r"\end{figure}",
            "",
        ]
    )

    lines.append(r"\section*{Construction Type}")
    lines.extend(
        render_detail_section_lines(
            "Structural Overview",
            [
                ("Primary structural system", construction.get("primary_structural_system")),
                ("Wall construction", construction.get("wall_construction")),
                ("Construction class", construction.get("construction_class")),
                ("AIR construction code", construction.get("air_construction_code")),
                ("Confidence", construction.get("construction_confidence")),
            ],
        )
    )
    lines.extend(render_plain_list_section_lines("Structural indicators", construction.get("structural_indicators")))
    lines.extend(render_text_section_lines("Analyst reasoning", construction.get("analysis_reasoning")))
    lines.append("")

    lines.append(r"\section*{Occupancy Assessment}")
    lines.extend(
        render_detail_section_lines(
            "Use Classification",
            [
                ("Primary use", occupancy.get("primary_use")),
                ("AIR occupancy code", occupancy.get("air_occupancy_code")),
                ("ISO occupancy type", occupancy.get("iso_occupancy_type")),
                ("Confidence", occupancy.get("occupancy_confidence")),
            ],
        )
    )
    lines.extend(render_plain_list_section_lines("Secondary uses", occupancy.get("secondary_uses")))
    lines.extend(render_plain_list_section_lines("Use indicators", occupancy.get("use_indicators")))
    lines.extend(render_text_section_lines("Analyst reasoning", occupancy.get("analysis_reasoning")))
    lines.append("")

    lines.append(r"\section*{Physical Characteristics}")
    lines.extend(
        render_detail_section_lines(
            "Building Profile",
            [
                ("Story count", physical.get("story_count")),
                ("Estimated height (ft)", physical.get("estimated_height_feet")),
                ("Facade width estimate", physical.get("building_width_estimate")),
                ("Architectural style", physical.get("architectural_style")),
            ],
        )
    )
    lines.extend(render_plain_list_section_lines("Notable features", physical.get("notable_features")))
    lines.extend(render_plain_list_section_lines("Accessibility features", physical.get("accessibility_features")))
    lines.extend(render_text_section_lines("Analyst reasoning", physical.get("analysis_reasoning")))
    lines.append("")

    lines.append(r"\section*{Construction Materials}")
    lines.extend(
        render_detail_section_lines(
            "Materials Overview",
            [
                ("Primary wall material", materials.get("primary_wall_material")),
                ("Window type", materials.get("window_type")),
                ("Material quality", materials.get("material_quality")),
                ("Visible roof material", materials.get("visible_roof_material")),
                ("Material condition", materials.get("material_condition")),
            ],
        )
    )
    lines.extend(render_plain_list_section_lines("Secondary materials", materials.get("secondary_materials")))
    lines.extend(render_text_section_lines("Analyst reasoning", materials.get("analysis_reasoning")))
    lines.append("")

    lines.append(r"\section*{Risk Factors}")
    lines.extend(
        render_detail_section_lines(
            "Risk Profile",
            [
                ("Fire risk level", risk.get("fire_risk_level")),
                ("Security level", risk.get("security_level")),
                ("Overall risk profile", risk.get("overall_risk_profile")),
            ],
        )
    )
    lines.extend(render_plain_list_section_lines("Nat cat vulnerabilities", risk.get("nat_cat_vulnerabilities")))
    lines.extend(render_plain_list_section_lines("Proximity hazards", risk.get("proximity_hazards")))
    lines.extend(render_plain_list_section_lines("Environmental factors", risk.get("environmental_factors")))
    lines.extend(render_text_section_lines("Analyst reasoning", risk.get("analysis_reasoning")))
    lines.append("")

    lines.append(r"\section*{Age and Condition}")
    lines.extend(
        render_detail_section_lines(
            "Condition Overview",
            [
                ("Estimated age range", age_condition.get("estimated_age_range")),
                ("Condition rating", age_condition.get("condition_rating")),
                ("Condition score", age_condition.get("condition_score")),
                ("Maintenance level", age_condition.get("maintenance_level")),
            ],
        )
    )
    lines.extend(render_plain_list_section_lines("Renovation indicators", age_condition.get("renovation_indicators")))
    lines.extend(render_plain_list_section_lines("Deterioration signs", age_condition.get("deterioration_signs")))
    lines.extend(render_text_section_lines("Analyst reasoning", age_condition.get("analysis_reasoning")))
    lines.append("")

    lines.append(r"\section*{Insurance Classifications}")
    lines.extend(
        render_detail_section_lines(
            "Suggested Codes",
            [
                ("Suggested AIR construction", classifications.get("suggested_air_construction")),
                ("Suggested AIR occupancy", classifications.get("suggested_air_occupancy")),
                ("ISO occupancy type", classifications.get("iso_occupancy_type")),
                ("RMS codes", classifications.get("rms_codes")),
                ("Classification confidence", classifications.get("classification_confidence")),
            ],
        )
    )
    lines.extend(render_plain_list_section_lines("Alternative codes", classifications.get("alternative_codes")))
    lines.extend(render_text_section_lines("Analyst reasoning", classifications.get("analysis_reasoning")))
    lines.append("")

    lines.append(r"\section*{Underwriting Considerations}")
    lines.extend(render_plain_list_section_lines("Key strengths", underwriting.get("key_strengths")))
    lines.extend(render_plain_list_section_lines("Key concerns", underwriting.get("key_concerns")))
    lines.extend(render_plain_list_section_lines("Recommended inspections", underwriting.get("recommended_inspections")))
    lines.extend(render_plain_list_section_lines("Coverage considerations", underwriting.get("coverage_considerations")))
    lines.extend(render_plain_list_section_lines("Pricing factors", underwriting.get("pricing_factors")))
    lines.append("")

    lines.append(r"\section*{Overall Assessment}")
    lines.extend(render_text_section_lines("Property summary", overall.get("property_summary")))
    lines.extend(
        render_detail_section_lines(
            "Insurability",
            [("Insurability", overall.get("insurability"))],
        )
    )
    lines.extend(render_plain_list_section_lines("Key recommendations", overall.get("key_recommendations")))
    lines.extend(render_plain_list_section_lines("Assessment limitations", overall.get("analysis_limitations")))
    lines.append("")

    lines.append(r"\section*{Image & Analysis Metadata}")
    lines.extend(
        render_detail_list_lines(
            [
                ("Photo quality", metadata.get("photo_quality")),
                ("Viewing angle", metadata.get("viewing_angle")),
                ("Lighting conditions", metadata.get("lighting_conditions")),
                ("Distance from building", metadata.get("distance_from_building")),
            ]
        )
    )
    lines.extend(render_plain_list_section_lines("Obstructions", metadata.get("obstructions")))

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
        f"[BUILD] Job {job_id}: status={status} stage={stage} progress={progress} message='{message}'"
    )


def _capture_latex_debug(tmpdir: str, latex_path: str, job_id: str) -> list[str]:
    """Persist LaTeX artifacts to the shared volume for post-mortem debugging."""

    debug_dir = "/my-volume/construction-analysis-results/debug"
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

    log_source = os.path.join(tmpdir, "building_analysis.log")
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
        f"[BUILD] Job {job_id}: LaTeX source (saved at {latex_path}){suffix}\n{preview}"
    )
    if truncated:
        print(
            f"[BUILD] Job {job_id}: LaTeX source truncated to first {max_chars} characters for logging"
        )


def generate_building_report(
    job_id: str,
    model_id: str,
    image_path: str,
    analysis_path: str,
) -> tuple[str, str]:
    """Compile the LaTeX report and return the PDF path and timestamp."""

    if not wait_for_path(image_path):
        raise ReportGenerationError(f"Building image not found at {image_path}")
    if not wait_for_path(analysis_path):
        raise ReportGenerationError(f"Analysis JSON not found at {analysis_path}")

    with open(analysis_path, "r", encoding="utf-8") as analysis_file:
        analysis_data = json.load(analysis_file)

    report_timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            _, image_ext = os.path.splitext(image_path)
            local_image_name = f"building_image{image_ext or '.png'}"
            local_image_path = os.path.join(tmpdir, local_image_name)
            shutil.copy(image_path, local_image_path)

            latex_content = build_latex_report(
                job_id=job_id,
                model_id=model_id,
                analysis_data=analysis_data,
                report_timestamp=report_timestamp,
                image_filename=local_image_name,
            )

            latex_filename = "building_analysis.tex"
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
                        f"[BUILD] Job {job_id}: pdflatex output {prefix_note}{tail}"
                    )

                log_path = os.path.join(tmpdir, "building_analysis.log")
                if os.path.exists(log_path):
                    try:
                        with open(log_path, "r", encoding="utf-8", errors="replace") as log_file:
                            log_tail = log_file.read()[-8000:]
                        print(
                            f"[BUILD] Job {job_id}: pdflatex log tail\n{log_tail}"
                        )
                    except Exception as log_exc:  # noqa: BLE001 - best effort
                        print(
                            f"[BUILD] Job {job_id}: failed to read pdflatex log ({log_exc})"
                        )

                raise ReportGenerationError(
                    "Report generation failed during LaTeX compilation",
                    error=error_output or str(exc),
                ) from exc

            pdf_source = os.path.join(tmpdir, "building_analysis.pdf")
            if not os.path.exists(pdf_source):
                raise ReportGenerationError("Expected PDF artifact not produced by pdflatex")

            reports_dir = "/my-volume/construction-analysis-results/reports"
            os.makedirs(reports_dir, exist_ok=True)
            report_filename = f"{job_id}.pdf"
            report_path = os.path.join(reports_dir, report_filename)
            if os.path.exists(report_path):
                os.remove(report_path)
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
def process_building_analysis(image_data: str, job_id: str):
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
        input_dir = "/my-volume/construction-analysis-results/inputs"
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
            message="Sending building image to Bedrock model"
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
                            "text": BUILDING_ANALYSIS_PROMPT,
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
            message="Parsing building analysis response"
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
        output_dir = "/my-volume/construction-analysis-results/outputs"
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
            message="Building analysis completed, preparing report",
            result=result_payload,
        )

        update_progress(
            job_id,
            status="processing",
            stage="report_generation",
            progress=85,
            message="Generating building analysis report",
            result=result_payload,
        )

        try:
            report_path, report_timestamp = generate_building_report(
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

        reports_dir = "/my-volume/construction-analysis-results/reports"
        relative_report = report_path
        if report_path.startswith(reports_dir):
            relative_report = os.path.relpath(report_path, reports_dir)

        artifacts["report_path"] = relative_report
        artifacts["report_absolute_path"] = report_path
        result_payload["report_generated_at"] = report_timestamp

        update_progress(
            job_id,
            status="completed",
            stage="finished",
            progress=100,
            message="Building analysis report generated",
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
                    message="Building analysis failed",
                    error=str(exc),
                )
        else:
            update_progress(
                job_id,
                status="failed",
                stage="error",
                progress=0,
                message="Building analysis failed",
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
web_app = FastAPI(title="Building Analysis API", version="1.0.0")

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

    process_building_analysis.spawn(request.image_data, job_id)

    return JSONResponse(
        content={
            "job_id": job_id,
            "status": "queued",
            "message": "Image queued for building analysis",
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
    report_path = artifacts.get("report_absolute_path") or artifacts.get("report_path")

    if not report_path:
        raise HTTPException(status_code=404, detail="Report not available")

    reports_dir = "/my-volume/construction-analysis-results/reports"
    expected_path = os.path.join(reports_dir, f"{job_id}.pdf")

    candidate_paths: list[str] = []
    for candidate in [expected_path, report_path, artifacts.get("report_path"), artifacts.get("report_absolute_path")]:
        if candidate and candidate not in candidate_paths:
            candidate_paths.append(candidate)

    for candidate in candidate_paths:
        resolved_path = candidate
        if not os.path.isabs(resolved_path):
            resolved_path = os.path.join(reports_dir, resolved_path)

        if os.path.exists(resolved_path):
            filename = os.path.basename(resolved_path) or f"{job_id}.pdf"
            print(f"[BUILD] Job {job_id}: serving report from {resolved_path}")
            return FileResponse(resolved_path, media_type="application/pdf", filename=filename)

    print(f"[BUILD] Job {job_id}: report not found after checking {candidate_paths}")
    raise HTTPException(status_code=404, detail="Report not available")


# Deploy the web app
@app.function(image=image, secrets=[api_secret], volumes={"/my-volume": volume})
@modal.asgi_app()
def fastapi_app():
    return web_app
