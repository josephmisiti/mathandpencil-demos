import { useMemo } from "react";

const rawBaseUrl = (import.meta.env.VITE_CONSTRUCTION_ANALYSIS_API_BASE_URL || "").trim();
const API_BASE_URL = rawBaseUrl.replace(/\/+$/, "");

const apiTokenCandidates = [
  import.meta.env.VITE_CONSTRUCTION_ANALYSIS_API_TOKEN,
  import.meta.env.VITE_ACORD_API_TOKEN,
  import.meta.env.VITE_API_TOKEN
];

const API_TOKEN = apiTokenCandidates
  .map((value) => (value || "").trim())
  .find((value) => Boolean(value)) || "";

export interface StartAnalysisResponse {
  job_id: string;
  status?: string;
  message?: string;
}

export interface ConstructionTypeSection {
  primary_structural_system?: string;
  wall_construction?: string;
  construction_class?: string;
  air_construction_code?: string;
  construction_confidence?: string;
  structural_indicators?: string[];
  analysis_reasoning?: string;
}

export interface OccupancyAssessmentSection {
  primary_use?: string;
  secondary_uses?: string[];
  air_occupancy_code?: string;
  iso_occupancy_type?: string;
  occupancy_confidence?: string;
  use_indicators?: string[];
  analysis_reasoning?: string;
}

export interface PhysicalCharacteristicsSection {
  story_count?: string;
  estimated_height_feet?: string;
  building_width_estimate?: string;
  architectural_style?: string;
  notable_features?: string[];
  accessibility_features?: string[];
  analysis_reasoning?: string;
}

export interface ConstructionMaterialsSection {
  primary_wall_material?: string;
  secondary_materials?: string[];
  window_type?: string;
  material_quality?: string;
  visible_roof_material?: string;
  material_condition?: string;
  analysis_reasoning?: string;
}

export interface RiskFactorsSection {
  fire_risk_level?: string;
  nat_cat_vulnerabilities?: string[];
  proximity_hazards?: string[];
  security_level?: string;
  environmental_factors?: string[];
  overall_risk_profile?: string;
  analysis_reasoning?: string;
}

export interface AgeConditionSection {
  estimated_age_range?: string;
  condition_rating?: string;
  condition_score?: string | number;
  maintenance_level?: string;
  renovation_indicators?: string[];
  deterioration_signs?: string[];
  analysis_reasoning?: string;
}

export interface InsuranceClassificationsSection {
  suggested_air_construction?: string;
  suggested_air_occupancy?: string;
  iso_occupancy_type?: string;
  rms_codes?: string;
  classification_confidence?: string;
  alternative_codes?: string[];
  analysis_reasoning?: string;
}

export interface UnderwritingConsiderationsSection {
  key_strengths?: string[];
  key_concerns?: string[];
  recommended_inspections?: string[];
  coverage_considerations?: string[];
  pricing_factors?: string[];
}

export interface OverallAssessmentSection {
  property_summary?: string;
  insurability?: string;
  key_recommendations?: string[];
  analysis_limitations?: string[];
}

export interface ImageMetadataSection {
  photo_quality?: string;
  viewing_angle?: string;
  lighting_conditions?: string;
  distance_from_building?: string;
  obstructions?: string[];
}

export interface ConstructionAnalysisPayload {
  building_analysis?: {
    construction_type?: ConstructionTypeSection;
    occupancy_assessment?: OccupancyAssessmentSection;
    physical_characteristics?: PhysicalCharacteristicsSection;
    construction_materials?: ConstructionMaterialsSection;
    risk_factors?: RiskFactorsSection;
    age_condition?: AgeConditionSection;
    insurance_classifications?: InsuranceClassificationsSection;
    underwriting_considerations?: UnderwritingConsiderationsSection;
    overall_assessment?: OverallAssessmentSection;
    image_analysis_metadata?: ImageMetadataSection;
  };
}

export interface ConstructionAnalysisResult {
  model_id: string;
  analysis?: ConstructionAnalysisPayload;
  artifacts?: {
    image_path?: string;
    analysis_path?: string;
    report_path?: string;
    report_absolute_path?: string;
  };
  report_generated_at?: string;
  report_status?: "pending" | "available" | "failed" | "disabled";
  report_error?: string;
}

export interface ConstructionProgressResponse {
  job_id?: string;
  status: string;
  stage?: string;
  progress?: number;
  message?: string;
  result?: ConstructionAnalysisResult | null;
  error?: string;
  timestamp?: number;
}

const missingBaseUrlError = new Error(
  "Construction analysis API base URL is not configured. Set VITE_CONSTRUCTION_ANALYSIS_API_BASE_URL in your environment."
);

function buildHeaders(additional?: Record<string, string>): Record<string, string> {
  const headers: Record<string, string> = additional ? { ...additional } : {};
  if (API_TOKEN) {
    headers["Authorization"] = `Bearer ${API_TOKEN}`;
  }
  return headers;
}

export async function startConstructionAnalysis(
  imageData: string
): Promise<StartAnalysisResponse> {
  if (!API_BASE_URL) {
    throw missingBaseUrlError;
  }

  const response = await fetch(`${API_BASE_URL}/save-image`, {
    method: "POST",
    headers: buildHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ image_data: imageData })
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Construction analysis request failed (${response.status})`);
  }

  const data = (await response.json()) as StartAnalysisResponse;
  if (!data.job_id) {
    throw new Error("Construction analysis API did not return a job ID");
  }

  return data;
}

export async function fetchConstructionAnalysisProgress(
  jobId: string,
  signal?: AbortSignal
): Promise<ConstructionProgressResponse> {
  if (!API_BASE_URL) {
    throw missingBaseUrlError;
  }

  const response = await fetch(
    `${API_BASE_URL}/progress/${encodeURIComponent(jobId)}`,
    {
      method: "GET",
      headers: buildHeaders(),
      signal
    }
  );

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Construction analysis progress failed (${response.status})`);
  }

  return (await response.json()) as ConstructionProgressResponse;
}

const CONTENT_DISPOSITION_FILENAME = /filename\*=UTF-8''(.+)|filename="?([^";]+)"?/i;

function decodeContentDisposition(disposition: string | null): string | null {
  if (!disposition) {
    return null;
  }

  const matches = disposition.match(CONTENT_DISPOSITION_FILENAME);
  if (!matches) {
    return null;
  }

  const encoded = matches[1];
  if (encoded) {
    try {
      return decodeURIComponent(encoded);
    } catch {
      return encoded;
    }
  }

  const simple = matches[2];
  return simple ? simple.trim() : null;
}

export async function downloadConstructionAnalysisReport(
  jobId: string
): Promise<{ blob: Blob; filename: string }> {
  if (!API_BASE_URL) {
    throw missingBaseUrlError;
  }

  const response = await fetch(
    `${API_BASE_URL}/report/${encodeURIComponent(jobId)}`,
    {
      method: "GET",
      headers: buildHeaders()
    }
  );

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Construction analysis report download failed (${response.status})`);
  }

  const blob = await response.blob();
  const disposition = decodeContentDisposition(response.headers.get("Content-Disposition"));
  const filename = disposition || `${jobId}.pdf`;
  return { blob, filename };
}

export function useConstructionAnalysisApiConfig(): {
  baseUrl: string;
  hasToken: boolean;
} {
  return useMemo(
    () => ({
      baseUrl: API_BASE_URL,
      hasToken: Boolean(API_TOKEN)
    }),
    []
  );
}
