/** Wraps the dashboard bridge endpoints in small typed browser helpers. */

import type {
  DemoStatusResponse,
  InvestigationResponse,
  PopulationSummary,
  Workspace,
} from "./types";

/** Carries an HTTP status alongside a bridge error that React can handle. */
export class ApiError extends Error {
  /** Creates an API error from the bridge's public message and response status. */
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** Sends one same-origin request and converts non-success responses into ApiError. */
async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: {
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
  });
  const payload = (await response.json()) as T & { error?: string };
  if (!response.ok) {
    throw new ApiError(payload.error || `Request failed (${response.status}).`, response.status);
  }
  return payload;
}

/** Loads available artifact collections and live-run readiness. */
export function getWorkspace(signal?: AbortSignal): Promise<Workspace> {
  return requestJson<Workspace>("/api/workspace", { signal });
}

/** Loads one household's validated report and sanitized replay trace. */
export function getInvestigation(
  collectionId: string,
  householdId: string,
  signal?: AbortSignal,
): Promise<InvestigationResponse> {
  const query = new URLSearchParams({
    collection: collectionId,
    household: householdId,
  });
  return requestJson<InvestigationResponse>(`/api/investigation?${query}`, { signal });
}

/** Loads the aggregate-only population contract for one verified collection. */
export function getPopulation(
  collectionId: string,
  signal?: AbortSignal,
): Promise<PopulationSummary> {
  const query = new URLSearchParams({ collection: collectionId });
  return requestJson<PopulationSummary>(`/api/population?${query}`, { signal });
}

/** Builds a safe download URL for the verified aggregate population export. */
export function populationExportUrl(
  collectionId: string,
  format: "json" | "csv",
): string {
  const query = new URLSearchParams({ collection: collectionId, format });
  return `/api/population/export?${query}`;
}

/** Requests a bounded live Gemini batch containing only the selected customer count. */
export function runDemo(customers: number): Promise<DemoStatusResponse> {
  return requestJson<DemoStatusResponse>("/api/demo", {
    method: "POST",
    body: JSON.stringify({ customers }),
  });
}

/** Polls a live job and requests only events after the last received cursor. */
export function getDemoStatus(
  jobId?: string | null,
  after = 0,
  signal?: AbortSignal,
): Promise<DemoStatusResponse> {
  const query = new URLSearchParams({ after: String(after) });
  if (jobId) query.set("job", jobId);
  return requestJson<DemoStatusResponse>(`/api/demo/status?${query}`, { signal });
}

/** Builds a safe bridge URL for one allow-listed human-readable artifact. */
export function artifactUrl(
  collectionId: string,
  householdId: string,
  file: "report.html" | "report.md" | "trace.html",
): string {
  const query = new URLSearchParams({ collection: collectionId, household: householdId, file });
  return `/api/artifact?${query}`;
}
