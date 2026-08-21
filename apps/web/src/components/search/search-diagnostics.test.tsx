import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { SearchDiagnostics } from "@/components/search/search-diagnostics";
import { renderWithProviders } from "@/test/render";

describe("SearchDiagnostics", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("shows Mastodon public collection mode and stage telemetry", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(
            JSON.stringify({
              session_id: "session-1",
              diagnostics: {
                query: {
                  original: "technology",
                  normalized: "technology",
                  variants: ["technology"],
                },
                mafer: {
                  temporal_intent: "TIME_NEUTRAL",
                  stop_reason: "SATISFIED",
                  intent_fingerprint: { labels: ["TOPIC", "ENGLISH"] },
                  query_lattice: {
                    variants: [
                      {
                        variant_id: "original-1",
                        text: "technology",
                        transformation: "ORIGINAL",
                        confidence: 1,
                        round_created: 1,
                      },
                    ],
                  },
                  resource_plan: {
                    resources: [
                      {
                        source: "mastodon",
                        long_term_utility: 78,
                        current_availability: 100,
                        reasons: ["capabilities fit: keyword"],
                      },
                    ],
                  },
                  rounds: [
                    { round: 0, kind: "LOCAL_MEMORY" },
                    {
                      round: 1,
                      kind: "EXTERNAL",
                      sources: ["mastodon"],
                      uncertainty: { level: "LOW" },
                      decision: "SATISFIED",
                    },
                  ],
                },
                connectors: [
                  {
                    source: "mastodon",
                    status: "healthy",
                    http_status: 200,
                    latency_ms: 410,
                    fetched_results: 40,
                    schema_valid_results: 40,
                    query_matching_results: 3,
                    normalized_results: 3,
                    final_matching_results: 3,
                    collected_results: 3,
                    raw_results: 40,
                    malformed_records: 0,
                    attempt_count: 1,
                    circuit_breaker_state: "closed",
                    error_category: null,
                    mode: "PUBLIC_TIMELINE",
                    instances: ["https://mas.to"],
                    local_query_matches: 3,
                    duplicates: 1,
                  },
                ],
              },
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        ),
      ),
    );

    renderWithProviders(<SearchDiagnostics sessionId="session-1" />);
    await userEvent.click(
      screen.getByRole("button", { name: /search diagnostics/i }),
    );

    expect(await screen.findByText("PUBLIC TIMELINE")).toBeInTheDocument();
    expect(screen.getByText("https://mas.to")).toBeInTheDocument();
    expect(screen.getByText(/Local matches: 3/)).toBeInTheDocument();
    expect(screen.getByText(/Federated duplicates: 1/)).toBeInTheDocument();
    expect(screen.getByText("Adaptive search trace")).toBeInTheDocument();
    expect(screen.getByText("SATISFIED")).toBeInTheDocument();
    expect(screen.getByText("TIME_NEUTRAL")).toBeInTheDocument();
    expect(screen.getByText("capabilities fit: keyword")).toBeInTheDocument();
  });
});
