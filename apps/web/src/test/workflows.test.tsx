import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { HistoryPage } from "@/pages/history-page";
import { SearchPage } from "@/pages/search-page";
import { SettingsPage } from "@/pages/settings-page";
import { SystemPage } from "@/pages/system-page";
import {
  searchResponse,
  settingsFixture,
  sourceFixture,
  summary,
} from "@/test/fixtures";
import { renderWithProviders } from "@/test/render";

function jsonResponse(value: unknown, status = 200) {
  return Promise.resolve(
    new Response(JSON.stringify(value), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
  );
}

describe("application workflows", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });
  afterEach(() => vi.unstubAllGlobals());

  it("runs a search and renders partial results", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) =>
        jsonResponse(
          String(input).endsWith("/sources") ? [sourceFixture] : searchResponse,
          String(input).endsWith("/sources") ? 200 : 201,
        ),
      ),
    );
    renderWithProviders(<SearchPage />);
    const user = userEvent.setup();
    await user.type(
      screen.getByLabelText(/keyword or phrase/i),
      "public policy",
    );
    const runSearch = screen.getByRole("button", { name: /run search/i });
    await waitFor(() => expect(runSearch).toBeEnabled());
    await user.click(runSearch);
    expect(
      await screen.findByText("Public policy institutional briefing"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/search completed with source warnings/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/requires a YouTube Data API key/i),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Search results workspace").parentElement).toHaveAttribute(
      "data-workspace-state",
      "results-first",
    );
    expect(screen.getByTestId("desktop-filter-rail")).toHaveClass("hidden");
    expect(screen.getByTestId("desktop-trace-rail")).toHaveClass("hidden");
    await user.click(screen.getByTestId("filters-toggle"));
    expect(await screen.findByRole("dialog", { name: "Search parameters" })).toBeInTheDocument();
    await user.keyboard("{Escape}");
    await user.click(screen.getByTestId("trace-toggle"));
    expect(await screen.findByRole("dialog", { name: "Live search" })).toBeInTheDocument();
  });

  it("records a reformulation without delaying the replacement search", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/sources")) return jsonResponse([sourceFixture]);
      if (url.endsWith("/quality/events")) {
        return jsonResponse(
          {
            id: 2,
            event_type: "SEARCH_REFORMULATED",
            search_session_id: searchResponse.session.id,
            content_id: null,
            query_class: "topic",
            rank: null,
            source: null,
            acquisition_mode: null,
            explicit_judgment: null,
            created_at: "2026-01-01T00:01:00Z",
          },
          201,
        );
      }
      return jsonResponse(searchResponse, 201);
    });
    vi.stubGlobal("fetch", fetchMock);
    renderWithProviders(<SearchPage />, { initialSearch: searchResponse });
    const user = userEvent.setup();
    const input = screen.getByLabelText(/keyword or phrase/i);
    await user.clear(input);
    await user.type(input, "public transport");
    const runSearch = screen.getByRole("button", { name: /run search/i });
    await waitFor(() => expect(runSearch).toBeEnabled());
    await user.click(runSearch);

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/quality/events"),
        expect.objectContaining({
          method: "POST",
          body: expect.stringContaining("SEARCH_REFORMULATED"),
        }),
      ),
    );
    expect(
      await screen.findByText("Public policy institutional briefing"),
    ).toBeInTheDocument();
  });

  it("restores the three-panel active state when a new streamed search starts", async () => {
    class PendingEventSource {
      static instances: PendingEventSource[] = [];
      onerror: (() => void) | null = null;
      constructor(_url: string) {
        PendingEventSource.instances.push(this);
      }
      addEventListener() {}
      close() {}
    }
    vi.stubGlobal("EventSource", PendingEventSource);
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/sources")) return jsonResponse([sourceFixture]);
        if (url.endsWith("/bookmarks")) return jsonResponse([]);
        if (url.endsWith("/quality/events")) return jsonResponse({}, 201);
        if (url.endsWith("/search/jobs")) {
          return jsonResponse(
            { job_id: "job-b", session_id: "session-b", status: "started" },
            202,
          );
        }
        return jsonResponse(searchResponse);
      }),
    );
    renderWithProviders(<SearchPage />, { initialSearch: searchResponse });
    const user = userEvent.setup();
    const input = screen.getByLabelText(/keyword or phrase/i);
    await user.clear(input);
    await user.type(input, "new streamed query");
    const runSearch = screen.getByRole("button", { name: /run search/i });
    await waitFor(() => expect(runSearch).toBeEnabled());
    await user.click(runSearch);

    const workspace = await screen.findByLabelText("Search results workspace");
    expect(workspace.parentElement).toHaveAttribute("data-workspace-state", "active");
    expect(screen.getByTestId("desktop-filter-rail")).toHaveClass(
      "search-workspace__rail--filters",
    );
    expect(screen.getByTestId("desktop-trace-rail")).toHaveClass(
      "search-workspace__rail--trace",
    );
    expect(PendingEventSource.instances).toHaveLength(1);
  });

  it("loads persisted history", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => jsonResponse([summary])),
    );
    renderWithProviders(<HistoryPage />);
    expect(await screen.findAllByText("public policy")).toHaveLength(2);
    expect(screen.getByText(/partial/i)).toBeInTheDocument();
  });

  it("loads and saves safe settings", async () => {
    const fetchMock = vi.fn((_: RequestInfo | URL, options?: RequestInit) =>
      jsonResponse(settingsFixture, options?.method === "PUT" ? 200 : 200),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderWithProviders(<SettingsPage />);
    expect(
      await screen.findByText(/these preferences are stored locally/i),
    ).toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: /save changes/i }),
    );
    await waitFor(() =>
      expect(screen.getByText("Settings saved.")).toBeInTheDocument(),
    );
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/settings"),
      expect.objectContaining({ method: "PUT" }),
    );
  });

  it("shows observed operator quality evidence without fabricated precision", async () => {
    const system = {
      api_status: "operational",
      database_status: "available",
      fts_status: "available",
      connector_status: { healthy: 2 },
      record_count: 10,
      index_count: 10,
      database_integrity: "ok",
      foreign_key_violations: 0,
      capabilities: ["fts5"],
      version: "1.2.0",
    };
    const quality = {
      search_count: 4,
      zero_result_count: 1,
      zero_result_rate: 0.25,
      explicit_relevant: 2,
      explicit_not_relevant: 1,
      query_class_distribution: { topic: 4 },
      language_distribution: { en: 4 },
      source_utility: [],
      engine_utility: [],
      average_rounds: 1.5,
      stop_reasons: { SATISFIED: 3, SOURCE_EXHAUSTION: 1 },
      uncertainty_distribution: { LOW: 3, HIGH: 1 },
      average_latency_ms: 120,
      average_request_count: 6,
      shadow_comparisons: { router: 4, stop_policy: 4 },
      configuration_snapshots: [
        {
          id: "snapshot",
          slot: "verified_production",
          reason: "Verified deterministic Phase-2 production configuration",
          created_at: "2026-01-01T00:00:00Z",
          configuration: {},
        },
      ],
    };
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) =>
        jsonResponse(String(input).endsWith("/quality") ? quality : system),
      ),
    );

    renderWithProviders(<SystemPage />);

    expect(
      await screen.findByText("Local search quality evidence"),
    ).toBeInTheDocument();
    expect(screen.getByText(/25(?:\.0)?%/)).toBeInTheDocument();
    expect(screen.queryByText(/precision@/i)).not.toBeInTheDocument();
    expect(screen.getByText("verified_production")).toBeInTheDocument();
    expect(screen.getByText("Observed query classes")).toBeInTheDocument();
    expect(screen.getByText("Production uncertainty")).toBeInTheDocument();
    expect(screen.getByText("Shadow source utility")).toBeInTheDocument();
    expect(screen.getByText(/retrieval evidence only/i)).toBeInTheDocument();
  });
});
