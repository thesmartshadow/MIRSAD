import { screen, within } from "@testing-library/react";

import { LiveSearchTrace } from "@/components/search/live-search-trace";
import { idleSearchJob } from "@/lib/search-job-state";
import { renderWithProviders } from "@/test/render";

describe("LiveSearchTrace", () => {
  beforeEach(() => window.history.replaceState({}, "", "/?webgl=off"));

  it("renders local-memory platform contributions outside connector execution", async () => {
    renderWithProviders(
      <LiveSearchTrace
        state={{
          ...idleSearchJob,
          phase: "completed",
          memory: {
            status: "completed",
            candidates: 13,
            elapsedMs: 7,
            platforms: { bluesky: 13 },
          },
          sources: {
            bluesky: {
              status: "skipped",
              fetched: 0,
              matched: 0,
              normalized: 0,
              admitted: 0,
              elapsedMs: null,
              errorCategory: "not_selected",
              acquisitionMode: "PUBLIC_API",
              wasSelected: false,
            },
            youtube: {
              status: "completed",
              fetched: 10,
              matched: 8,
              normalized: 8,
              admitted: 6,
              elapsedMs: 120,
              errorCategory: null,
              acquisitionMode: "DIRECT_API",
              wasSelected: true,
            },
          },
        }}
      />,
    );

    expect(await screen.findByTestId("webgl-fallback")).toBeInTheDocument();
    expect(screen.getByTestId("local-memory-trace")).toHaveTextContent("bluesky 13");
    const connectorList = screen.getByRole("list");
    expect(within(connectorList).getByText("bluesky")).toBeInTheDocument();
    expect(within(connectorList).getByText("Skipped")).toBeInTheDocument();
    expect(within(connectorList).getByText("youtube")).toBeInTheDocument();
    expect(within(connectorList).getByText("Complete")).toBeInTheDocument();
  });
});
