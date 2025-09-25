import { useMemo } from "react";

const rawBaseUrl = (import.meta.env.VITE_ROOF_ANALYSIS_API_BASE_URL || "").trim();
const API_BASE_URL = rawBaseUrl.replace(/\/+$/, "");

const apiTokenCandidates = [
  import.meta.env.VITE_ROOF_ANALYSIS_API_TOKEN,
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

export interface RoofAnalysisQuality {
  overall_rating?: string;
  condition_score?: number;
  visible_issues?: string[];
  quality_indicators?: string[];
  analysis_reasoning?: string;
}

export interface RoofAnalysisAge {
  estimated_age_years?: string;
  age_category?: string;
  weathering_indicators?: string[];
  analysis_reasoning?: string;
}

export interface RoofAnalysisShape {
  primary_shape?: string;
  complexity?: string;
  roof_planes?: string | number;
  pitch_estimate?: string;
  architectural_features?: string[];
  analysis_reasoning?: string;
}

export interface RoofAnalysisCover {
  material_type?: string;
  material_confidence?: string;
  color_description?: string;
  texture_pattern?: string;
  secondary_materials?: string[];
  analysis_reasoning?: string;
}

export interface RoofOverallAssessment {
  summary?: string;
  recommendations?: string[];
  analysis_limitations?: string[];
}

export interface RoofImageMetadata {
  image_quality?: string;
  viewing_angle?: string;
  resolution_adequacy?: string;
  weather_conditions?: string;
}

export interface RoofAnalysisPayload {
  roof_analysis?: {
    quality?: RoofAnalysisQuality;
    age?: RoofAnalysisAge;
    shape?: RoofAnalysisShape;
    cover?: RoofAnalysisCover;
    overall_assessment?: RoofOverallAssessment;
    image_analysis_metadata?: RoofImageMetadata;
  };
}

export interface RoofAnalysisResult {
  model_id: string;
  analysis?: RoofAnalysisPayload;
  artifacts?: {
    image_path?: string;
    analysis_path?: string;
  };
}

export interface RoofProgressResponse {
  job_id?: string;
  status: string;
  stage?: string;
  progress?: number;
  message?: string;
  result?: RoofAnalysisResult | null;
  error?: string;
  timestamp?: number;
}

const missingBaseUrlError = new Error(
  "Roof analysis API base URL is not configured. Set VITE_ROOF_ANALYSIS_API_BASE_URL in your environment."
);

function buildHeaders(additional?: Record<string, string>): Record<string, string> {
  const headers: Record<string, string> = additional ? { ...additional } : {};
  if (API_TOKEN) {
    headers["Authorization"] = `Bearer ${API_TOKEN}`;
  }
  return headers;
}

export async function startRoofAnalysis(
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
    throw new Error(message || `Roof analysis request failed (${response.status})`);
  }

  const data = (await response.json()) as StartAnalysisResponse;
  if (!data.job_id) {
    throw new Error("Roof analysis API did not return a job ID");
  }

  return data;
}

export async function fetchRoofAnalysisProgress(
  jobId: string,
  signal?: AbortSignal
): Promise<RoofProgressResponse> {
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
    throw new Error(message || `Roof analysis progress failed (${response.status})`);
  }

  return (await response.json()) as RoofProgressResponse;
}

export function useRoofAnalysisApiConfig(): {
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
