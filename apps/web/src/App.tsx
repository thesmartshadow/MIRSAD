import { lazy, Suspense } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { AppLayout } from "@/components/layout/app-layout";
import { PageSkeleton } from "@/components/shared/page";
import { DirectionProvider } from "@/components/ui/direction";
import { TooltipProvider } from "@/components/ui/tooltip";
import { I18nProvider, useI18n } from "@/lib/i18n";
import { SearchStateProvider } from "@/lib/search-state";
import { ThemeProvider } from "@/lib/theme";

const SearchPage = lazy(() =>
  import("@/pages/search-page").then((module) => ({
    default: module.SearchPage,
  })),
);
const AnalyticsPage = lazy(() =>
  import("@/pages/analytics-page").then((module) => ({
    default: module.AnalyticsPage,
  })),
);
const ClustersPage = lazy(() =>
  import("@/pages/clusters-page").then((module) => ({
    default: module.ClustersPage,
  })),
);
const ComparePage = lazy(() =>
  import("@/pages/compare-page").then((module) => ({
    default: module.ComparePage,
  })),
);
const HistoryPage = lazy(() =>
  import("@/pages/history-page").then((module) => ({
    default: module.HistoryPage,
  })),
);
const SavedSearchesPage = lazy(() =>
  import("@/pages/saved-searches-page").then((module) => ({
    default: module.SavedSearchesPage,
  })),
);
const BookmarksPage = lazy(() =>
  import("@/pages/bookmarks-page").then((module) => ({
    default: module.BookmarksPage,
  })),
);
const ReportPage = lazy(() =>
  import("@/pages/report-page").then((module) => ({
    default: module.ReportPage,
  })),
);
const SourcesPage = lazy(() =>
  import("@/pages/sources-page").then((module) => ({
    default: module.SourcesPage,
  })),
);
const SystemPage = lazy(() =>
  import("@/pages/system-page").then((module) => ({
    default: module.SystemPage,
  })),
);
const SettingsPage = lazy(() =>
  import("@/pages/settings-page").then((module) => ({
    default: module.SettingsPage,
  })),
);

function DirectedApplication() {
  const { direction } = useI18n();
  return (
    <DirectionProvider direction={direction}>
      <TooltipProvider>
        <BrowserRouter>
          <SearchStateProvider>
            <Suspense
              fallback={
                <div className="p-6">
                  <PageSkeleton />
                </div>
              }
            >
              <Routes>
                <Route element={<AppLayout />}>
                  <Route index element={<Navigate to="/search" replace />} />
                  <Route path="/search" element={<SearchPage />} />
                  <Route path="/search/:sessionId" element={<SearchPage />} />
                  <Route path="/analytics" element={<AnalyticsPage />} />
                  <Route path="/clusters" element={<ClustersPage />} />
                  <Route path="/compare" element={<ComparePage />} />
                  <Route path="/history" element={<HistoryPage />} />
                  <Route path="/saved" element={<SavedSearchesPage />} />
                  <Route path="/bookmarks" element={<BookmarksPage />} />
                  <Route path="/report/:sessionId" element={<ReportPage />} />
                  <Route path="/sources" element={<SourcesPage />} />
                  <Route path="/system" element={<SystemPage />} />
                  <Route path="/settings" element={<SettingsPage />} />
                  <Route path="*" element={<Navigate to="/search" replace />} />
                </Route>
              </Routes>
            </Suspense>
          </SearchStateProvider>
        </BrowserRouter>
      </TooltipProvider>
    </DirectionProvider>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <I18nProvider>
        <DirectedApplication />
      </I18nProvider>
    </ThemeProvider>
  );
}
