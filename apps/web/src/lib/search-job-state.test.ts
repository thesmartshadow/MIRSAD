import { applySearchEvent, idleSearchJob } from "@/lib/search-job-state";
import type { SearchJobEvent } from "@/types/api";

const message = (
  jobId: string,
  event: SearchJobEvent["event"],
  data: Record<string, unknown> = {},
): SearchJobEvent => ({
  sequence: 1,
  event,
  job_id: jobId,
  session_id: `session-${jobId}`,
  elapsed_ms: 10,
  emitted_at: "2026-08-21T00:00:00Z",
  data,
});

describe("search job state", () => {
  it("prevents a late Search A event from overwriting Search B", () => {
    const searchB = { ...idleSearchJob, phase: "collecting" as const, jobId: "b" };
    expect(
      applySearchEvent(
        searchB,
        message("a", "search.completed", { result_count: 99 }),
        20,
      ),
    ).toEqual(searchB);
  });

  it("stabilizes final results after a terminal event", () => {
    const running = { ...idleSearchJob, phase: "collecting" as const, jobId: "a" };
    const completed = applySearchEvent(
      running,
      message("a", "search.completed", {
        result_count: 8,
        unique_count: 7,
        cluster_count: 4,
      }),
      50,
    );
    const late = applySearchEvent(
      completed,
      message("a", "source.completed", { source: "rss", fetched: 20 }),
      60,
    );
    expect(late).toEqual(completed);
    expect(completed.resultCount).toBe(8);
    expect(completed.uniqueCount).toBe(7);
  });

  it("keeps local-memory acquisition separate from connector execution", () => {
    const running = { ...idleSearchJob, phase: "planning" as const, jobId: "a" };
    const withMemory = applySearchEvent(
      running,
      message("a", "acquisition.local_memory.completed", {
        candidates: 13,
        elapsed_ms: 8,
        platforms: { bluesky: 13 },
        requests: 0,
      }),
      12,
    );

    expect(withMemory.memory).toMatchObject({
      status: "completed",
      candidates: 13,
      elapsedMs: 8,
      platforms: { bluesky: 13 },
    });
    expect(withMemory.sources.bluesky).toBeUndefined();
    expect(withMemory.selectedSourceCount).toBe(0);
  });

  it("records bounded semantic preparation without changing search results", () => {
    const current = { ...idleSearchJob, phase: "collecting" as const, jobId: "a" };
    const prepared = applySearchEvent(
      current,
      message("a", "semantic.preparation.completed", {
        precompute_eligible_candidates: 20,
        precompute_completed: 20,
        precompute_cache_hits: 4,
        precompute_cache_misses: 16,
        precompute_wall_ms: 910,
        semantic_work_hidden_ms: 700,
      }),
      950,
    );

    expect(prepared.semanticPreparation).toMatchObject({
      status: "completed",
      eligible: 20,
      completed: 20,
      cacheHits: 4,
      cacheMisses: 16,
      hiddenMs: 700,
    });
    expect(prepared.resultCount).toBe(0);
  });

  it("finishes planner-selected connectors skipped by stop logic without inventing execution", () => {
    const planned = applySearchEvent(
      { ...idleSearchJob, phase: "planning", jobId: "a" },
      message("a", "source.selected", {
        source: "gdelt",
        acquisition_mode: "PUBLIC_API",
      }),
      10,
    );
    const stopped = applySearchEvent(
      { ...planned, selectedSourceCount: 1 },
      message("a", "source.skipped", {
        source: "gdelt",
        error_category: "stopped_before_execution",
      }),
      20,
    );

    expect(stopped.sources.gdelt).toMatchObject({
      status: "skipped",
      wasSelected: true,
      fetched: 0,
      errorCategory: "stopped_before_execution",
    });
    expect(stopped.selectedSourceCount).toBe(1);
    expect(stopped.completedSourceCount).toBe(1);
  });
});
