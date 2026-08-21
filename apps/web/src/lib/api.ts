import type {
  CompareResponse,
  Bookmark,
  AnalyticsSnapshot,
  DataActionResult,
  DataCounts,
  DuplicateGroup,
  SavedSearch,
  SearchDiagnostics,
  SearchJobStarted,
  SearchRequest,
  SearchResponse,
  SearchSummary,
  SettingValue,
  SourceStatus,
  SystemStatus,
  OutcomeEvent,
  QualitySummary,
} from "@/types/api";

const API_ROOT = import.meta.env.VITE_API_ROOT ?? "/api/v1";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_ROOT}${path}`, {
    ...options,
    headers: {
      Accept: "application/json",
      ...(options?.body ? { "Content-Type": "application/json" } : {}),
      ...options?.headers,
    },
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as {
      detail?: string;
    } | null;
    throw new ApiError(
      body?.detail ?? `Request failed (${response.status})`,
      response.status,
    );
  }
  return response.json() as Promise<T>;
}

async function emptyRequest(path: string, options: RequestInit): Promise<void> {
  const response = await fetch(`${API_ROOT}${path}`, options);
  if (!response.ok)
    throw new ApiError(`Request failed (${response.status})`, response.status);
}

export const api = {
  getAnalytics: (
    scope: "all" | "24h" | "7d" | "30d" | "session",
    sessionId?: string,
    signal?: AbortSignal,
  ) =>
    request<AnalyticsSnapshot>(
      scope === "session" && sessionId
        ? `/analytics/${encodeURIComponent(sessionId)}`
        : `/analytics?scope=${scope === "session" ? "all" : scope}`,
      { signal },
    ),
  createSearch: (payload: SearchRequest, signal?: AbortSignal) =>
    request<SearchResponse>("/searches", {
      method: "POST",
      body: JSON.stringify(payload),
      signal,
    }),
  createSearchJob: (payload: SearchRequest, signal?: AbortSignal) =>
    request<SearchJobStarted>("/search/jobs", {
      method: "POST",
      body: JSON.stringify(payload),
      signal,
    }),
  searchEventsUrl: (jobId: string) =>
    `${API_ROOT}/search/jobs/${encodeURIComponent(jobId)}/events`,
  getSearch: (id: string, signal?: AbortSignal) =>
    request<SearchResponse>(`/searches/${encodeURIComponent(id)}`, { signal }),
  getHistory: () => request<SearchSummary[]>("/searches?limit=100"),
  getDiagnostics: (id: string) =>
    request<SearchDiagnostics>(
      `/searches/${encodeURIComponent(id)}/diagnostics`,
    ),
  getSources: () => request<SourceStatus[]>("/sources"),
  refreshSources: () =>
    request<SourceStatus[]>("/sources/health", { method: "POST" }),
  updateSource: (
    key: string,
    values: {
      enabled?: boolean;
      confidence?: number;
      github_scopes?: string[];
    },
  ) =>
    request<SourceStatus>(`/sources/${encodeURIComponent(key)}`, {
      method: "PATCH",
      body: JSON.stringify(values),
    }),
  getSettings: () => request<SettingValue[]>("/settings"),
  updateSettings: (values: Record<string, unknown>) =>
    request<SettingValue[]>("/settings", {
      method: "PUT",
      body: JSON.stringify({ values }),
    }),
  resetSettings: () =>
    request<SettingValue[]>("/settings/reset", { method: "POST" }),
  getSystem: () => request<SystemStatus>("/system"),
  getQuality: () => request<QualitySummary>("/quality"),
  recordOutcome: (
    eventType:
      | "RESULT_OPENED"
      | "RESULT_MARKED_RELEVANT"
      | "RESULT_MARKED_NOT_RELEVANT"
      | "SEARCH_REFORMULATED",
    searchSessionId: string,
    contentId: string | null,
  ) =>
    request<OutcomeEvent>("/quality/events", {
      method: "POST",
      body: JSON.stringify({
        event_type: eventType,
        search_session_id: searchSessionId,
        content_id: contentId,
      }),
    }),
  compare: (left: string, right: string) =>
    request<CompareResponse>("/compare", {
      method: "POST",
      body: JSON.stringify({ left_session_id: left, right_session_id: right }),
    }),
  getSavedSearches: () => request<SavedSearch[]>("/saved-searches"),
  createSavedSearch: (name: string, configuration: SearchRequest) =>
    request<SavedSearch>("/saved-searches", {
      method: "POST",
      body: JSON.stringify({ name, configuration }),
    }),
  renameSavedSearch: (id: string, name: string) =>
    request<SavedSearch>(`/saved-searches/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify({ name }),
    }),
  duplicateSavedSearch: (id: string) =>
    request<SavedSearch>(
      `/saved-searches/${encodeURIComponent(id)}/duplicate`,
      {
        method: "POST",
      },
    ),
  runSavedSearch: (id: string) =>
    request<SearchResponse>(`/saved-searches/${encodeURIComponent(id)}/run`, {
      method: "POST",
    }),
  deleteSavedSearch: (id: string) =>
    emptyRequest(`/saved-searches/${encodeURIComponent(id)}`, {
      method: "DELETE",
    }),
  getBookmarks: () => request<Bookmark[]>("/bookmarks"),
  createBookmark: (
    contentId: string,
    searchSessionId: string | null,
    note = "",
  ) =>
    request<Bookmark>("/bookmarks", {
      method: "POST",
      body: JSON.stringify({
        content_id: contentId,
        search_session_id: searchSessionId,
        note,
      }),
    }),
  updateBookmark: (id: string, note: string) =>
    request<Bookmark>(`/bookmarks/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify({ note }),
    }),
  deleteBookmark: (id: string) =>
    emptyRequest(`/bookmarks/${encodeURIComponent(id)}`, { method: "DELETE" }),
  getDuplicateGroup: (id: string, sort: "newest" | "source" | "engagement") =>
    request<DuplicateGroup>(
      `/duplicate-groups/${encodeURIComponent(id)}?sort=${sort}`,
    ),
  exportUrl: (id: string, format: "csv" | "json") =>
    `${API_ROOT}/searches/${encodeURIComponent(id)}/export?format=${format}`,
  getDataCounts: () => request<DataCounts>("/data/counts"),
  runDataAction: (action: string) =>
    request<DataActionResult>(`/data/actions/${encodeURIComponent(action)}`, {
      method: "POST",
      body: JSON.stringify({ confirm: true }),
    }),
};
