import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import {
  defaultSearchRequest,
  SearchForm,
} from "@/components/search/search-form";
import { renderWithProviders } from "@/test/render";
import type { ConnectorCapabilities, SourceStatus } from "@/types/api";

const capabilities: ConnectorCapabilities = {
  keyword_search: true,
  phrase_search: true,
  hashtag_search: false,
  author_search: false,
  recent_search: true,
  historical_search: false,
  language_filter: false,
  date_filter: false,
  public_posts: true,
  comments: false,
  engagement_metrics: true,
  pagination: true,
  requires_credentials: false,
  requires_approval: false,
  paid_access: false,
  public_timeline: false,
  hashtag_timeline: false,
  authenticated_fulltext_search: false,
  instance_scoped: false,
  content_types: ["posts"],
  search_modes: [],
  sort_modes: [],
  acquisition_modes: ["PUBLIC_API"],
  web_index_search: false,
  official_embed: false,
  historical_index: false,
};

const sourceCatalog = [
  { key: "bluesky", name: "Bluesky" },
  { key: "hacker_news", name: "Hacker News", category: "developer_community" },
].map((source) => ({
  kind: "social",
  category: "social",
  support_level: "supported",
  coverage_label: "Fixture coverage",
  capabilities,
  configuration_state: "configured",
  active_acquisition_mode: "PUBLIC_API",
  enabled: true,
  configured: true,
  status: "healthy",
  detail: null,
  confidence: 70,
  last_checked_at: null,
  last_success_at: null,
  recent_failure: null,
  failure_category: null,
  http_status: 200,
  average_latency_ms: 1,
  last_latency_ms: 1,
  last_result_count: 1,
  last_normalized_count: 1,
  last_malformed_count: 0,
  request_count: 1,
  failure_count: 0,
  configuration: {},
  ...source,
})) as SourceStatus[];

describe("SearchForm", () => {
  beforeEach(() => localStorage.clear());

  it("blocks empty searches", async () => {
    const onSearch = vi.fn();
    renderWithProviders(
      <SearchForm
        loading={false}
        onSearch={onSearch}
        sourceCatalog={sourceCatalog}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: /run search/i }));
    expect(
      screen.getByText(/enter a keyword or phrase before searching/i),
    ).toBeInTheDocument();
    expect(onSearch).not.toHaveBeenCalled();
  });

  it("submits a trimmed query and selected source filters", async () => {
    const user = userEvent.setup();
    const onSearch = vi.fn();
    renderWithProviders(
      <SearchForm
        loading={false}
        onSearch={onSearch}
        sourceCatalog={sourceCatalog}
      />,
    );
    await user.type(
      screen.getByLabelText(/keyword or phrase/i),
      "  public policy  ",
    );
    await user.click(screen.getByRole("checkbox", { name: "Bluesky" }));
    await user.click(screen.getByRole("button", { name: /run search/i }));
    expect(onSearch).toHaveBeenCalledWith(
      expect.objectContaining({
        query: "public policy",
        sources: expect.not.arrayContaining(["bluesky"]),
      }),
    );
  });

  it("restores and submits the complete historical search configuration", async () => {
    const user = userEvent.setup();
    const onSearch = vi.fn();
    const initialRequest = {
      ...defaultSearchRequest,
      query: "وزارة الصحة",
      sources: ["hacker_news"],
      time_range: "30d" as const,
      language: "ar" as const,
      limit: 100,
      exact_phrase: true,
      sort: "newest" as const,
    };

    renderWithProviders(
      <SearchForm
        initialRequest={initialRequest}
        loading={false}
        onSearch={onSearch}
        sourceCatalog={sourceCatalog}
      />,
    );

    expect(screen.getByLabelText(/keyword or phrase/i)).toHaveValue(
      "وزارة الصحة",
    );
    expect(screen.getByLabelText(/time range/i)).toHaveTextContent("30 days");
    expect(screen.getByLabelText(/content language/i)).toHaveTextContent(
      "Arabic",
    );
    expect(screen.getByLabelText(/sort mode/i)).toHaveTextContent("Newest");
    expect(screen.getByLabelText(/result limit/i)).toHaveTextContent("100");
    expect(
      screen.getByRole("checkbox", { name: "Exact phrase" }),
    ).toBeChecked();

    await user.click(screen.getByRole("button", { name: /run search/i }));
    expect(onSearch).toHaveBeenCalledWith(initialRequest);
  });

  it("derives the social preset and Threads controls from connector metadata", async () => {
    const user = userEvent.setup();
    const onSearch = vi.fn();
    const socialCatalog: SourceStatus[] = [
      {
        ...sourceCatalog[0],
        key: "x",
        name: "X",
        support_level: "supported_with_credentials",
      },
      {
        ...sourceCatalog[0],
        key: "threads",
        name: "Threads",
        support_level: "supported_with_credentials",
        capabilities: {
          ...capabilities,
          hashtag_search: true,
          search_modes: ["keyword", "topic_tag"],
          sort_modes: ["top", "recent"],
        },
      },
      {
        ...sourceCatalog[0],
        key: "mastodon",
        name: "Mastodon",
        capabilities: {
          ...capabilities,
          hashtag_search: true,
          public_timeline: true,
          hashtag_timeline: true,
          authenticated_fulltext_search: "conditional",
          instance_scoped: true,
          search_modes: ["public_timeline", "hashtag_timeline"],
        },
      },
      {
        ...sourceCatalog[0],
        key: "tiktok",
        name: "TikTok",
        configured: false,
        configuration_state: "restricted",
        status: "restricted",
        support_level: "restricted_access",
        detail: "Research API approval required",
        capabilities: {
          ...capabilities,
          requires_credentials: true,
          requires_approval: true,
        },
      },
    ];
    renderWithProviders(
      <SearchForm
        loading={false}
        onSearch={onSearch}
        sourceCatalog={socialCatalog}
      />,
    );

    await user.type(screen.getByLabelText(/keyword or phrase/i), "Baghdad");
    await user.click(
      screen.getByText("Sources and advanced options", { selector: "summary" }),
    );
    await user.click(screen.getByLabelText(/source preset/i));
    await user.click(
      await screen.findByRole("option", { name: "Social Media" }),
    );

    expect(screen.getByRole("checkbox", { name: "TikTok" })).toHaveAttribute(
      "aria-disabled",
      "true",
    );
    expect(
      screen.getByText(
        "TikTok Research API approval and credentials are required.",
      ),
    ).toBeVisible();
    expect(screen.getByLabelText("Threads search mode")).toBeVisible();
    expect(screen.getByLabelText("Threads sort")).toBeVisible();
    await user.hover(screen.getByRole("button", { name: "Mastodon capabilities" }));
    expect(
      await screen.findByText(
        "Public timeline coverage on configured Mastodon instances",
      ),
    ).toBeVisible();

    await user.click(screen.getByRole("button", { name: /run search/i }));
    expect(onSearch).toHaveBeenCalledWith(
      expect.objectContaining({ sources: ["x", "threads", "mastodon"] }),
    );
  });

  it("groups indexed social sources from acquisition capability metadata", () => {
    const webIndexed = {
      ...sourceCatalog[0],
      key: "x",
      name: "X",
      active_acquisition_mode: "WEB_INDEX" as const,
      capabilities: {
        ...capabilities,
        acquisition_modes: ["DIRECT_API", "WEB_INDEX"],
        web_index_search: "conditional" as const,
      },
    } as SourceStatus;

    renderWithProviders(
      <SearchForm
        loading={false}
        onSearch={vi.fn()}
        sourceCatalog={[...sourceCatalog, webIndexed]}
      />,
    );

    expect(screen.getByText("Social — Web indexed")).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "X" })).toBeInTheDocument();
  });

  it("submits the selected bounded search mode with automatic routing", async () => {
    const user = userEvent.setup();
    const onSearch = vi.fn();
    renderWithProviders(
      <SearchForm
        initialRequest={{
          ...defaultSearchRequest,
          query: "Baghdad",
          search_mode: "deep",
          source_selection: "auto",
        }}
        loading={false}
        onSearch={onSearch}
        sourceCatalog={sourceCatalog}
      />,
    );

    await user.click(
      screen.getByText("Sources and advanced options", { selector: "summary" }),
    );
    expect(screen.getByText("Wider multi-round discovery")).toBeVisible();
    await user.click(screen.getByRole("button", { name: /run search/i }));

    expect(onSearch).toHaveBeenCalledWith(
      expect.objectContaining({
        query: "Baghdad",
        search_mode: "deep",
        source_selection: "auto",
      }),
    );
  });
});
