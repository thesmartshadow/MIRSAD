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
});
