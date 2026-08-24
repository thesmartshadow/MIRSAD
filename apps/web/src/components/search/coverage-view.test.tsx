import { screen } from "@testing-library/react";

import { CoverageView } from "@/components/search/coverage-view";
import { renderWithProviders } from "@/test/render";
import type { CoverageReport } from "@/types/api";

const coverage: CoverageReport = {
  session_id: "coverage-session",
  outcome_status: "completed",
  coverage_status: "PARTIAL",
  sources: [],
  lanes: [
    {
      lane: "LIVE",
      available: true,
      executed: true,
      contributed: true,
      candidates: 12,
      final: 6,
      platforms: ["youtube"],
    },
    {
      lane: "LOCAL_MEMORY",
      available: true,
      executed: true,
      contributed: true,
      candidates: 4,
      final: 2,
      platforms: ["bluesky"],
    },
    {
      lane: "HISTORICAL",
      available: true,
      executed: true,
      contributed: false,
      candidates: 1,
      final: 0,
      platforms: [],
    },
  ],
  gaps: [
    {
      source: "x",
      reason: "WEB_DISCOVERY_DISABLED",
      detail: "Optional web discovery is disabled. <script>alert(1)</script>",
    },
  ],
  represented_platforms: ["bluesky", "youtube"],
  web_discovery: "DISABLED",
  stop_reason: "USER_LIMIT",
  stop_explanation: "Stopped because the configured result limit was satisfied.",
};

describe("CoverageView", () => {
  it("renders real lanes, typed gaps, and retrieved text as text nodes", () => {
    const { container } = renderWithProviders(<CoverageView coverage={coverage} />);
    expect(screen.getAllByText("Local memory").length).toBeGreaterThan(0);
    expect(screen.getByText("WEB DISCOVERY DISABLED")).toBeInTheDocument();
    expect(screen.getByText(/<script>alert\(1\)<\/script>/)).toBeInTheDocument();
    expect(container.querySelector("script")).toBeNull();
    expect(screen.getByRole("img", { name: /Retrieval coverage topology/ })).toBeVisible();
  });

  it("retains root RTL direction and uses no horizontal-position assumptions", () => {
    localStorage.setItem("mirsad.locale", "ar");
    renderWithProviders(<CoverageView coverage={coverage} />);
    expect(document.documentElement).toHaveAttribute("dir", "rtl");
    expect(screen.getByText("فجوات التغطية")).toBeVisible();
  });
});
