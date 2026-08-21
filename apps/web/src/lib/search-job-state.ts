import type { SearchJobEvent, SearchRequest } from "@/types/api";

export type SearchPhase =
  | "idle"
  | "creating"
  | "planning"
  | "collecting"
  | "normalizing"
  | "ranking"
  | "clustering"
  | "completed"
  | "partial"
  | "failed"
  | "cancelled";

export type LiveSourceState = {
  status: "selected" | "searching" | "completed" | "degraded" | "failed" | "skipped";
  fetched: number;
  matched: number;
  normalized: number;
  admitted: number;
  elapsedMs: number | null;
  errorCategory: string | null;
  acquisitionMode: string | null;
  wasSelected: boolean;
};

export type SearchJobState = {
  phase: SearchPhase;
  query: string;
  request: SearchRequest | null;
  jobId: string | null;
  sessionId: string | null;
  sources: Record<string, LiveSourceState>;
  memory: {
    status: "idle" | "searching" | "completed" | "failed";
    candidates: number;
    elapsedMs: number | null;
    platforms: Record<string, number>;
  };
  semanticPreparation: {
    status: "idle" | "preparing" | "completed" | "failed";
    eligible: number;
    completed: number;
    cacheHits: number;
    cacheMisses: number;
    wallMs: number | null;
    hiddenMs: number | null;
  };
  selectedSourceCount: number;
  completedSourceCount: number;
  fetched: number;
  matched: number;
  admitted: number;
  resultCount: number;
  uniqueCount: number;
  clusterCount: number;
  stopReason: string | null;
  serverElapsedMs: number;
  feedbackLatencyMs: number;
  jobCreatedLatencyMs: number | null;
  firstEventLatencyMs: number | null;
  firstSourceCompletionMs: number | null;
  events: SearchJobEvent[];
};

export const idleSearchJob: SearchJobState = {
  phase: "idle",
  query: "",
  request: null,
  jobId: null,
  sessionId: null,
  sources: {},
  memory: { status: "idle", candidates: 0, elapsedMs: null, platforms: {} },
  semanticPreparation: {
    status: "idle",
    eligible: 0,
    completed: 0,
    cacheHits: 0,
    cacheMisses: 0,
    wallMs: null,
    hiddenMs: null,
  },
  selectedSourceCount: 0,
  completedSourceCount: 0,
  fetched: 0,
  matched: 0,
  admitted: 0,
  resultCount: 0,
  uniqueCount: 0,
  clusterCount: 0,
  stopReason: null,
  serverElapsedMs: 0,
  feedbackLatencyMs: 0,
  jobCreatedLatencyMs: null,
  firstEventLatencyMs: null,
  firstSourceCompletionMs: null,
  events: [],
};

const numeric = (value: unknown) =>
  typeof value === "number" && Number.isFinite(value) ? value : 0;

const text = (value: unknown) => (typeof value === "string" ? value : null);

export function applySearchEvent(
  current: SearchJobState,
  message: SearchJobEvent,
  clientElapsedMs: number,
): SearchJobState {
  if (current.jobId && current.jobId !== message.job_id) return current;
  if (
    ["completed", "partial", "failed", "cancelled"].includes(current.phase) &&
    !["search.completed", "search.partial", "search.failed"].includes(message.event)
  )
    return current;
  const data = message.data;
  let phase = current.phase;
  if (message.event === "planning.started") phase = "planning";
  if (message.event === "source.started" || message.event === "collection.progress")
    phase = "collecting";
  if (message.event === "acquisition.local_memory.started") phase = "planning";
  if (message.event === "normalization.completed" || message.event === "persistence.completed")
    phase = "normalizing";
  if (message.event === "ranking.started" || message.event === "ranking.completed")
    phase = "ranking";
  if (message.event === "clustering.started" || message.event === "clustering.completed")
    phase = "clustering";
  if (message.event === "search.completed") phase = "completed";
  if (message.event === "search.partial") phase = "partial";
  if (message.event === "search.failed") phase = "failed";

  const sources = { ...current.sources };
  const source = text(data.source);
  if (source) {
    const previous = sources[source] ?? {
      status: "selected" as const,
      fetched: 0,
      matched: 0,
      normalized: 0,
      admitted: 0,
      elapsedMs: null,
      errorCategory: null,
      acquisitionMode: null,
      wasSelected: false,
    };
    const status =
      message.event === "source.started"
        ? "searching"
        : message.event === "source.completed"
          ? "completed"
          : message.event === "source.degraded"
            ? "degraded"
            : message.event === "source.failed"
              ? "failed"
              : message.event === "source.skipped"
                ? "skipped"
                : previous.status;
    sources[source] = {
      ...previous,
      status,
      fetched: numeric(data.fetched) || previous.fetched,
      matched: numeric(data.matched) || previous.matched,
      normalized: numeric(data.normalized) || previous.normalized,
      admitted: numeric(data.admitted) || previous.admitted,
      elapsedMs:
        typeof data.elapsed_ms === "number" ? data.elapsed_ms : previous.elapsedMs,
      errorCategory:
        text(data.error_category) ?? text(data.reason) ?? previous.errorCategory,
      acquisitionMode: text(data.acquisition_mode) ?? previous.acquisitionMode,
      wasSelected: previous.wasSelected || message.event === "source.selected",
    };
  }

  const memory = { ...current.memory };
  if (message.event === "acquisition.local_memory.started") {
    memory.status = "searching";
  }
  if (message.event === "acquisition.local_memory.completed") {
    memory.status = "completed";
    memory.candidates = numeric(data.candidates);
    memory.elapsedMs = numeric(data.elapsed_ms);
    memory.platforms =
      data.platforms && typeof data.platforms === "object"
        ? (data.platforms as Record<string, number>)
        : {};
  }

  const semanticPreparation = { ...current.semanticPreparation };
  if (message.event === "semantic.preparation.started") {
    semanticPreparation.status = "preparing";
    semanticPreparation.eligible =
      numeric(data.precompute_eligible_candidates) || numeric(data.eligible_candidates);
  }
  if (message.event === "semantic.preparation.completed") {
    semanticPreparation.status = data.precompute_failed ? "failed" : "completed";
    semanticPreparation.eligible = numeric(data.precompute_eligible_candidates);
    semanticPreparation.completed = numeric(data.precompute_completed);
    semanticPreparation.cacheHits = numeric(data.precompute_cache_hits);
    semanticPreparation.cacheMisses = numeric(data.precompute_cache_misses);
    semanticPreparation.wallMs = numeric(data.precompute_wall_ms);
    semanticPreparation.hiddenMs = numeric(data.semantic_work_hidden_ms);
  }

  const terminal = ["search.completed", "search.partial", "search.failed"].includes(
    message.event,
  );
  return {
    ...current,
    phase,
    sources,
    memory,
    semanticPreparation,
    selectedSourceCount:
      numeric(data.selected_sources) ||
      current.selectedSourceCount ||
      Object.values(sources).filter((item) => item.wasSelected).length,
    completedSourceCount:
      numeric(data.completed_sources) ||
      Object.values(sources).filter((item) =>
        item.wasSelected && ["completed", "degraded", "failed", "skipped"].includes(item.status),
      ).length,
    fetched: numeric(data.fetched) || current.fetched,
    matched: numeric(data.matched) || current.matched,
    admitted: numeric(data.admitted) || current.admitted,
    resultCount: terminal ? numeric(data.result_count) : current.resultCount,
    uniqueCount: terminal ? numeric(data.unique_count) : current.uniqueCount,
    clusterCount: terminal ? numeric(data.cluster_count) : current.clusterCount,
    stopReason: terminal ? text(data.stop_reason) : current.stopReason,
    serverElapsedMs: Math.max(current.serverElapsedMs, message.elapsed_ms),
    firstEventLatencyMs: current.firstEventLatencyMs ?? clientElapsedMs,
    firstSourceCompletionMs:
      current.firstSourceCompletionMs ??
      (["source.completed", "source.degraded", "source.failed"].includes(message.event)
        ? clientElapsedMs
        : null),
    events: [...current.events, message].slice(-64),
  };
}
