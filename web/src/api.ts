import type { DemoStatusResponse, InvestigationResponse, Workspace } from "./types";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

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

export function getWorkspace(signal?: AbortSignal): Promise<Workspace> {
  return requestJson<Workspace>("/api/workspace", { signal });
}

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

export function runDemo(customers: number): Promise<DemoStatusResponse> {
  return requestJson<DemoStatusResponse>("/api/demo", {
    method: "POST",
    body: JSON.stringify({ customers }),
  });
}

export function getDemoStatus(
  jobId?: string | null,
  after = 0,
  signal?: AbortSignal,
): Promise<DemoStatusResponse> {
  const query = new URLSearchParams({ after: String(after) });
  if (jobId) query.set("job", jobId);
  return requestJson<DemoStatusResponse>(`/api/demo/status?${query}`, { signal });
}

export function artifactUrl(
  collectionId: string,
  householdId: string,
  file: "report.html" | "report.md" | "trace.html",
): string {
  const query = new URLSearchParams({ collection: collectionId, household: householdId, file });
  return `/api/artifact?${query}`;
}
