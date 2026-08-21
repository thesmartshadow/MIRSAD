import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "@/lib/api";
import { AnalyticsPage } from "@/pages/analytics-page";
import { searchResponse } from "@/test/fixtures";
import { renderWithProviders } from "@/test/render";

describe("AnalyticsPage", () => {
  afterEach(() => vi.restoreAllMocks());

  it("defaults to persisted global scope and switches to the exact session", async () => {
    const global = {
      ...searchResponse.analytics,
      scope: "all" as const,
      total_results: 43,
      unique_results: 40,
      content_record_count: 43,
      unique_canonical_count: 40,
      search_appearance_count: 49,
      duplicate_group_count: 3,
    };
    const session = {
      ...searchResponse.analytics,
      scope: "session" as const,
      scope_session_id: searchResponse.session.id,
      scope_query: "CVE-2026-61371",
      scope_started_at: "2026-08-10T15:39:00Z",
      total_results: 0,
      unique_results: 0,
    };
    const getAnalytics = vi
      .spyOn(api, "getAnalytics")
      .mockImplementation(async (scope) =>
        scope === "session" ? session : global,
      );
    const zeroLatest = {
      ...searchResponse,
      analytics: session,
      session: {
        ...searchResponse.session,
        original_query: "CVE-2026-61371",
        result_count: 0,
        unique_count: 0,
      },
    };

    renderWithProviders(<AnalyticsPage />, { initialSearch: zeroLatest });

    expect(await screen.findByText("Content records")).toBeInTheDocument();
    expect(getAnalytics).toHaveBeenCalledWith("all", zeroLatest.session.id, expect.any(AbortSignal));
    expect(screen.getByText("43")).toBeInTheDocument();

    const user = userEvent.setup();
    await user.click(screen.getByRole("combobox", { name: "Analytics scope" }));
    await user.click(await screen.findByText("Current search session"));

    await waitFor(() =>
      expect(getAnalytics).toHaveBeenCalledWith(
        "session",
        zeroLatest.session.id,
        expect.any(AbortSignal),
      ),
    );
    expect(await screen.findByText(/Analytics for: CVE-2026-61371/)).toBeInTheDocument();
  });
});
