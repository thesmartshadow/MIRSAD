import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ResultCard } from "@/components/search/result-card";
import { searchResponse } from "@/test/fixtures";
import { renderWithProviders } from "@/test/render";

describe("ResultCard", () => {
  beforeEach(() => localStorage.clear());
  afterEach(() => vi.unstubAllGlobals());

  it("renders normalized content as text", () => {
    renderWithProviders(<ResultCard item={searchResponse.results[0]} />);
    expect(
      screen.getByText("Public policy institutional briefing"),
    ).toBeInTheDocument();
    expect(screen.getByText("Fixture analyst")).toBeInTheDocument();
    expect(screen.getByText("78.5")).toBeInTheDocument();
  });

  it("renders persisted bookmark state after a page reload", () => {
    renderWithProviders(
      <ResultCard
        item={searchResponse.results[0]}
        initiallyBookmarked
      />,
    );

    expect(screen.getByRole("button", { name: "Bookmarked" })).toBeDisabled();
  });

  it("converges to bookmarked when the backend reports an existing bookmark", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(JSON.stringify({ detail: "Bookmark already exists" }), {
            status: 409,
            headers: { "Content-Type": "application/json" },
          }),
        ),
      ),
    );
    renderWithProviders(
      <ResultCard
        item={searchResponse.results[0]}
        sessionId={searchResponse.session.id}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: "Bookmark result" }));

    expect(await screen.findByRole("button", { name: "Bookmarked" })).toBeDisabled();
    expect(screen.queryByText("Something went wrong")).not.toBeInTheDocument();
  });

  it("opens the complete deterministic score explanation", async () => {
    renderWithProviders(<ResultCard item={searchResponse.results[0]} />);
    await userEvent.click(
      screen.getByRole("button", { name: /explain score/i }),
    );
    expect(await screen.findByText("Score explanation")).toBeInTheDocument();
    expect(screen.getByText("Source Confidence")).toBeInTheDocument();
    expect(screen.getByText("Cross-Source Presence")).toBeInTheDocument();
    expect(screen.getByText(/not a truth score/i)).toBeInTheDocument();
    expect(screen.getByText("duplicate-1")).toBeInTheDocument();
  });

  it("shows authoritative hybrid relevance without recalculating it", async () => {
    const item = {
      ...searchResponse.results[0],
      explanation: {
        ...searchResponse.results[0].explanation,
        lexical_relevance: 91,
        semantic_relevance: 76,
        semantic_similarity: 0.52,
        semantic_weight: 0.75,
        secondary_quality_budget: 0.01,
        ranking_strategy: "lexical_candidate_semantic_rerank",
      },
    };
    renderWithProviders(<ResultCard item={item} />);
    await userEvent.click(
      screen.getByRole("button", { name: /explain score/i }),
    );

    expect(await screen.findByText("Lexical Relevance")).toBeInTheDocument();
    expect(screen.getByText("Semantic Relevance")).toBeInTheDocument();
    expect(screen.getByText("Phrase Match")).toBeInTheDocument();
    expect(screen.getByText("Query Coverage")).toBeInTheDocument();
  });

  it("identifies indexed web provenance without claiming direct API access", async () => {
    const item = {
      ...searchResponse.results[0],
      source: "x",
      acquisition_mode: "WEB_INDEX",
      acquisition_modes_seen: ["WEB_INDEX"],
      indexed_public_web_coverage: true,
      discovery_support: 3,
      discovery_engines: ["brave", "qwant", "startpage"],
    };
    renderWithProviders(<ResultCard item={item} />);

    expect(screen.getByText("Indexed public web")).toBeInTheDocument();
    expect(screen.getByText(/Discovery Support/)).toHaveTextContent("3");
    await userEvent.hover(screen.getByText("Indexed public web"));
    expect(
      await screen.findByText("Not direct platform API"),
    ).toBeInTheDocument();
  });

  it("records explicit relevance feedback without changing displayed ranking", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(
        new Response(
          JSON.stringify({
            id: 1,
            event_type: "RESULT_MARKED_RELEVANT",
            search_session_id: searchResponse.session.id,
            content_id: searchResponse.results[0].id,
            query_class: "topic",
            rank: 1,
            source: "mock",
            acquisition_mode: "DIRECT_API",
            explicit_judgment: "relevant",
            created_at: "2026-01-01T00:00:00Z",
          }),
          { status: 201, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderWithProviders(
      <ResultCard
        item={searchResponse.results[0]}
        sessionId={searchResponse.session.id}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: "Relevant" }));

    expect(screen.getByRole("button", { name: "Relevant" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/quality/events"),
      expect.objectContaining({ method: "POST" }),
    );
    expect(screen.getByText("78.5")).toBeInTheDocument();
  });
});
