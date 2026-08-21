import {
  AlertTriangle,
  CheckCircle2,
  Download,
  ListFilter,
  PanelRightOpen,
  Printer,
  Save,
  SlidersHorizontal,
} from "lucide-react";
import { startTransition, useEffect, useRef, useState } from "react";
import { NavLink, useNavigate, useParams } from "react-router-dom";

import { LiveSearchTrace } from "@/components/search/live-search-trace";
import { RetrievalFlowSvg } from "@/components/search/retrieval-flow-svg";
import { ResultCard } from "@/components/search/result-card";
import { SearchDiagnostics } from "@/components/search/search-diagnostics";
import { SearchForm } from "@/components/search/search-form";
import {
  EmptyState,
  ErrorState,
  PageHeader,
  PageSkeleton,
  StatusBadge,
} from "@/components/shared/page";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api } from "@/lib/api";
import { formatDate, formatDuration, formatNumber } from "@/lib/format";
import { useI18n } from "@/lib/i18n";
import { loadGsap, motion } from "@/lib/motion";
import {
  applySearchEvent,
  idleSearchJob,
  type SearchJobState,
} from "@/lib/search-job-state";
import { useSearchState } from "@/lib/search-state";
import { connectorFailure } from "@/lib/source-presentation";
import type { SearchJobEvent, SearchRequest } from "@/types/api";

const terminalEvents = ["search.completed", "search.partial", "search.failed"];

function FiltersPanel({
  activeRequest,
  density,
  onDensity,
}: {
  activeRequest: SearchRequest | null;
  density: "comfortable" | "compact";
  onDensity: (value: "comfortable" | "compact") => void;
}) {
  const { t } = useI18n();
  return (
    <section className="space-y-4" aria-label={t("search.filtersSummary")}>
      <h2 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
        <SlidersHorizontal className="size-4" />
        {t("search.filtersSummary")}
      </h2>
      {activeRequest ? (
        <dl className="divide-y text-xs">
          {[
            [t("search.sourcePreset"), activeRequest.source_selection === "auto" ? t("search.presetAutomatic") : t("search.presetCustom")],
            [t("search.timeRange"), activeRequest.time_range],
            [t("search.mode"), activeRequest.search_mode],
            [t("search.language"), activeRequest.language],
            [t("search.resultLimit"), activeRequest.limit],
          ].map(([label, value]) => (
            <div className="grid grid-cols-[1fr_auto] gap-3 py-2.5" key={String(label)}>
              <dt className="text-muted-foreground">{label}</dt>
              <dd className="font-medium" dir="auto">{value}</dd>
            </div>
          ))}
        </dl>
      ) : (
        <p className="text-xs text-muted-foreground">{t("search.configurePrompt")}</p>
      )}
      <div className="border-t pt-3">
        <div className="mb-2 text-xs text-muted-foreground">{t("search.density")}</div>
        <div className="grid grid-cols-2 gap-1">
          {(["comfortable", "compact"] as const).map((value) => (
            <Button key={value} variant={density === value ? "secondary" : "ghost"} size="sm" onClick={() => onDensity(value)}>
              {t(`search.density.${value}`)}
            </Button>
          ))}
        </div>
      </div>
    </section>
  );
}

export function SearchPage() {
  const { t, locale } = useI18n();
  const { currentSearch, setCurrentSearch } = useSearchState();
  const { sessionId } = useParams();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [page, setPage] = useState(1);
  const [savedName, setSavedName] = useState("");
  const [saveOpen, setSaveOpen] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [traceOpen, setTraceOpen] = useState(false);
  const [wideWorkspace, setWideWorkspace] = useState(() =>
    typeof window !== "undefined" ? window.matchMedia("(min-width: 1280px)").matches : false,
  );
  const [jobState, setJobState] = useState<SearchJobState>(idleSearchJob);
  const [density, setDensity] = useState<"comfortable" | "compact">(() =>
    localStorage.getItem("mirsad.search-density") === "compact"
      ? "compact"
      : "comfortable",
  );
  const [bookmarkedContentIds, setBookmarkedContentIds] = useState<Set<string>>(
    new Set(),
  );
  const requestGeneration = useRef(0);
  const activeSearch = useRef<AbortController | null>(null);
  const activeEvents = useRef<EventSource | null>(null);
  const workspace = useRef<HTMLDivElement>(null);
  const resultList = useRef<HTMLDivElement>(null);
  const pageSize = 20;

  const terminalWithResults = !loading && Boolean(currentSearch?.results.length);

  useEffect(() => {
    let disposed = false;
    let revert: () => void = () => undefined;
    void loadGsap().then((gsap) => {
      if (disposed || !workspace.current) return;
      const context = gsap.context(() => {
        const media = gsap.matchMedia();
        media.add("(prefers-reduced-motion: no-preference)", () => {
          gsap.fromTo(
            workspace.current,
            { opacity: 0.82, y: 5 },
            { opacity: 1, y: 0, duration: motion.standard, ease: motion.ease },
          );
          if (terminalWithResults && resultList.current) {
            gsap.fromTo(
              Array.from(resultList.current.children).slice(0, 6),
              { opacity: 0, y: 7 },
              { opacity: 1, y: 0, duration: motion.quick, stagger: 0.018, ease: motion.ease },
            );
          }
        });
        revert = () => media.revert();
      }, workspace);
      const nested = revert;
      revert = () => {
        nested();
        context.revert();
      };
    });
    return () => {
      disposed = true;
      revert();
    };
  }, [loading, terminalWithResults, currentSearch?.session.id]);

  useEffect(
    () => () => {
      requestGeneration.current += 1;
      activeSearch.current?.abort();
      activeEvents.current?.close();
    },
    [],
  );

  useEffect(() => {
    const query = window.matchMedia("(min-width: 1280px)");
    const update = () => setWideWorkspace(query.matches);
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);

  useEffect(() => {
    const focusSearch = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const editable =
        target?.matches("input, textarea, [contenteditable=true]") ?? false;
      if ((event.key === "/" && !editable) || ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k")) {
        event.preventDefault();
        document.querySelector<HTMLInputElement>("#search-query")?.focus();
      }
    };
    window.addEventListener("keydown", focusSearch);
    return () => window.removeEventListener("keydown", focusSearch);
  }, []);

  useEffect(() => {
    if (!sessionId || currentSearch?.session.id === sessionId || loading) return;
    const controller = new AbortController();
    api
      .getSearch(sessionId, controller.signal)
      .then((response) =>
        startTransition(() => {
          setCurrentSearch(response);
          setJobState({
            ...idleSearchJob,
            phase: response.session.status === "partial" ? "partial" : response.session.status === "failed" ? "failed" : "completed",
            query: response.session.original_query,
            request: response.session.parameters,
            sessionId: response.session.id,
            resultCount: response.session.result_count,
            uniqueCount: response.session.unique_count,
            clusterCount: response.clusters.length,
            serverElapsedMs: response.session.duration_ms,
          });
        }),
      )
      .catch((reason: Error) => {
        if (reason.name !== "AbortError") setError(reason.message);
      });
    return () => controller.abort();
  }, [currentSearch?.session.id, loading, sessionId, setCurrentSearch]);

  useEffect(() => {
    let active = true;
    api
      .getBookmarks()
      .then((bookmarks) => {
        if (active)
          setBookmarkedContentIds(
            new Set(bookmarks.map((bookmark) => bookmark.content_id)),
          );
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [currentSearch?.session.id]);

  const finishSearch = async (
    event: SearchJobEvent,
    generation: number,
    controller: AbortController,
  ) => {
    activeEvents.current?.close();
    if (event.event === "search.failed") {
      if (generation === requestGeneration.current) {
        setError(String(event.data.message ?? t("state.error")));
        setLoading(false);
      }
      return;
    }
    const response = await api.getSearch(event.session_id, controller.signal);
    if (generation !== requestGeneration.current) return;
    startTransition(() => setCurrentSearch(response));
    navigate(`/search/${response.session.id}`, { replace: true });
    activeSearch.current = null;
    setLoading(false);
  };

  const runSearch = async (request: SearchRequest) => {
    if (
      currentSearch &&
      request.query.trim() !== currentSearch.session.original_query.trim()
    ) {
      void api
        .recordOutcome("SEARCH_REFORMULATED", currentSearch.session.id, null)
        .catch(() => undefined);
    }
    activeSearch.current?.abort();
    activeEvents.current?.close();
    const controller = new AbortController();
    activeSearch.current = controller;
    const generation = ++requestGeneration.current;
    const interactionStarted = performance.now();
    setLoading(true);
    setFiltersOpen(false);
    setTraceOpen(false);
    setCurrentSearch(null);
    setError("");
    setPage(1);
    setJobState({
      ...idleSearchJob,
      phase: "creating",
      query: request.query,
      request,
      feedbackLatencyMs: Math.max(0, performance.now() - interactionStarted),
    });
    try {
      if (typeof EventSource === "undefined") {
        const response = await api.createSearch(request, controller.signal);
        if (generation !== requestGeneration.current) return;
        setJobState({
          ...idleSearchJob,
          phase: response.session.status === "partial" ? "partial" : "completed",
          query: request.query,
          request,
          sessionId: response.session.id,
          resultCount: response.session.result_count,
          uniqueCount: response.session.unique_count,
          clusterCount: response.clusters.length,
          serverElapsedMs: response.session.duration_ms,
        });
        startTransition(() => setCurrentSearch(response));
        navigate(`/search/${response.session.id}`, { replace: true });
        setLoading(false);
        return;
      }
      const created = await api.createSearchJob(request, controller.signal);
      if (generation !== requestGeneration.current) return;
      const jobCreatedLatencyMs = performance.now() - interactionStarted;
      setJobState((current) => ({
        ...current,
        jobId: created.job_id,
        sessionId: created.session_id,
        jobCreatedLatencyMs,
      }));
      const events = new EventSource(api.searchEventsUrl(created.job_id));
      activeEvents.current = events;
      const receive = (raw: MessageEvent<string>) => {
        if (generation !== requestGeneration.current) return;
        let message: SearchJobEvent;
        try {
          message = JSON.parse(raw.data) as SearchJobEvent;
        } catch {
          return;
        }
        if (message.job_id !== created.job_id) return;
        setJobState((current) =>
          current.jobId === created.job_id
            ? applySearchEvent(current, message, performance.now() - interactionStarted)
            : current,
        );
        if (terminalEvents.includes(message.event)) {
          void finishSearch(message, generation, controller).catch((reason: Error) => {
            if (generation === requestGeneration.current) {
              setError(reason.message);
              setLoading(false);
            }
          });
        }
      };
      for (const eventName of [
        "search.started",
        "planning.started",
        "planning.completed",
        "acquisition.local_memory.started",
        "acquisition.local_memory.completed",
        "source.selected",
        "source.started",
        "source.progress",
        "source.completed",
        "source.degraded",
        "source.failed",
        "source.skipped",
        "collection.progress",
        "normalization.completed",
        "persistence.completed",
        "semantic.preparation.started",
        "semantic.preparation.completed",
        "ranking.started",
        "ranking.completed",
        "clustering.started",
        "clustering.completed",
        "search.partial",
        "search.completed",
        "search.failed",
      ]) {
        events.addEventListener(eventName, receive as EventListener);
      }
      events.onerror = () => {
        if (generation !== requestGeneration.current) return;
        events.close();
        setError(t("search.streamInterrupted"));
        setLoading(false);
      };
    } catch (reason) {
      if (
        generation === requestGeneration.current &&
        !(reason instanceof DOMException && reason.name === "AbortError")
      ) {
        setError(reason instanceof Error ? reason.message : t("state.error"));
        setLoading(false);
      }
    }
  };

  const results = currentSearch?.results ?? [];
  const visibleResults = results.slice((page - 1) * pageSize, page * pageSize);
  const totalPages = Math.max(1, Math.ceil(results.length / pageSize));
  const unavailableCount = currentSearch?.session.warnings.length ?? 0;
  const activeRequest = jobState.request ?? currentSearch?.session.parameters ?? null;

  const saveSearch = async () => {
    if (!currentSearch || !savedName.trim()) return;
    await api.createSavedSearch(savedName.trim(), currentSearch.session.parameters);
    setSavedName("");
    setSaveOpen(false);
  };

  const resultEmptyDescription = currentSearch
    ? currentSearch.session.outcome_reason === "NO_MATCHES_IN_TIME_RANGE"
      ? t("search.zero.noMatchesInTimeRange")
      : currentSearch.session.outcome_reason === "NO_CAPABLE_SOURCE"
        ? t("search.zero.noCapableSource")
        : currentSearch.session.outcome_reason === "ALL_SELECTED_SOURCES_FAILED"
          ? currentSearch.session.outcome_context?.cause === "EXTERNAL_LIMIT"
            ? t("search.zero.externalLimit")
            : currentSearch.session.outcome_context?.cause === "SOURCE_UNAVAILABLE"
              ? t("search.zero.sourceUnavailable")
              : t("search.zero.allSourcesFailed")
          : currentSearch.session.outcome_reason === "WEB_DISCOVERY_BLOCKED"
            ? t("search.zero.webDiscoveryBlocked")
            : currentSearch.session.parameters.time_range !== "all"
              ? t("search.zero.narrowTime")
              : t("search.zero.noMatches")
    : t("search.emptyDescription");

  return (
    <div>
      <PageHeader
        title={t("search.title")}
        description={t("search.description")}
        actions={
          currentSearch && (
            <>
              <Dialog open={saveOpen} onOpenChange={setSaveOpen}>
                <DialogTrigger render={<Button variant="outline" size="sm" />}>
                  <Save /> {t("search.save")}
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>{t("search.save")}</DialogTitle>
                    <DialogDescription>{t("search.savedPrompt")}</DialogDescription>
                  </DialogHeader>
                  <div className="space-y-2">
                    <Label htmlFor="saved-search-name">{t("search.savedName")}</Label>
                    <Input id="saved-search-name" value={savedName} maxLength={120} onChange={(event) => setSavedName(event.target.value)} />
                  </div>
                  <DialogFooter>
                    <Button variant="outline" onClick={() => setSaveOpen(false)}>{t("action.cancel")}</Button>
                    <Button onClick={saveSearch} disabled={!savedName.trim()}>{t("action.save")}</Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
              <DropdownMenu>
                <DropdownMenuTrigger render={<Button variant="outline" size="sm" />}><Download />{t("action.export")}</DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem nativeButton={false} render={<a href={api.exportUrl(currentSearch.session.id, "csv")} />}>CSV</DropdownMenuItem>
                  <DropdownMenuItem nativeButton={false} render={<a href={api.exportUrl(currentSearch.session.id, "json")} />}>JSON</DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
              <Button nativeButton={false} variant="outline" size="sm" render={<NavLink to={`/report/${currentSearch.session.id}`} />}><Printer />{t("action.print")}</Button>
              <SearchDiagnostics sessionId={currentSearch.session.id} />
            </>
          )
        }
      />

      <SearchForm
        initialQuery={currentSearch?.session.original_query}
        initialRequest={currentSearch?.session.parameters}
        loading={loading}
        onSearch={runSearch}
      />

      <div className={`mb-3 flex flex-wrap items-center gap-2 ${loading ? "justify-end xl:hidden" : "justify-end"}`}>
        <Sheet open={filtersOpen} onOpenChange={setFiltersOpen}>
          <SheetTrigger render={<Button variant="outline" size="sm" data-testid="filters-toggle" />}>
            <ListFilter />{t("search.filters")}
          </SheetTrigger>
          <SheetContent side={locale === "ar" ? "right" : "left"} className="w-[min(92vw,340px)]">
            <SheetHeader><SheetTitle>{t("search.filtersSummary")}</SheetTitle><SheetDescription>{t("search.configurePrompt")}</SheetDescription></SheetHeader>
            <div className="px-4"><FiltersPanel activeRequest={activeRequest} density={density} onDensity={(value) => { setDensity(value); localStorage.setItem("mirsad.search-density", value); }} /></div>
          </SheetContent>
        </Sheet>
        <Sheet open={traceOpen} onOpenChange={setTraceOpen}>
          <SheetTrigger render={<Button variant="outline" size="sm" data-testid="trace-toggle" />}>
            <PanelRightOpen />{t("live.title")}
          </SheetTrigger>
          <SheetContent side={locale === "ar" ? "left" : "right"} className="w-[min(94vw,380px)]">
            <SheetHeader><SheetTitle>{t("live.title")}</SheetTitle><SheetDescription>{t("diagnostics.description")}</SheetDescription></SheetHeader>
            <div className="min-h-0 px-4">{traceOpen && <LiveSearchTrace state={jobState} />}</div>
          </SheetContent>
        </Sheet>
      </div>

      <div
        ref={workspace}
        data-workspace-state={loading ? "active" : terminalWithResults ? "results-first" : currentSearch ? "terminal-empty" : "idle"}
        className={`grid items-start gap-5 ${loading ? "xl:grid-cols-[minmax(220px,250px)_minmax(0,1fr)_minmax(260px,310px)]" : "grid-cols-1"}`}
      >
        <aside className={loading ? "hidden border-e pe-4 xl:block" : "hidden"} data-testid="desktop-filter-rail">
          <div className="sticky top-4">
            <FiltersPanel activeRequest={activeRequest} density={density} onDensity={(value) => { setDensity(value); localStorage.setItem("mirsad.search-density", value); }} />
          </div>
        </aside>

        <section aria-label={t("search.workspace")} className="min-w-0">
          {error && <ErrorState message={error} />}
          {loading && (
            <div className="space-y-3" aria-live="polite" aria-busy="true">
              <div className="border-b pb-3">
                <div className="text-xs font-medium uppercase tracking-wide text-primary">{t(`live.phase.${jobState.phase}`)}</div>
                <h2 className="mt-1 text-lg font-semibold" dir="auto">{jobState.query}</h2>
              </div>
              <div className="border-y bg-muted/10 px-3 py-2">
                <RetrievalFlowSvg state={jobState} />
              </div>
              <PageSkeleton rows={3} />
            </div>
          )}
          {!loading && currentSearch && (
            <>
              <section className="mb-4 border-y bg-muted/10 px-4 py-4" aria-label={t("search.sessionSummary")}>
                  <div className="mb-3 flex flex-col justify-between gap-1 border-b pb-3 sm:flex-row sm:items-end">
                    <div><div className="text-xs text-muted-foreground">{t("search.keyword")}</div><div className="mt-1 text-lg font-semibold" dir="auto">{currentSearch.session.original_query}</div></div>
                    <div className="text-xs text-muted-foreground">{formatDate(currentSearch.session.started_at, locale)}</div>
                  </div>
                  <dl className="grid grid-cols-3 gap-3 sm:grid-cols-6">
                    {[
                      [t("search.collected"), currentSearch.session.result_count],
                      [t("analytics.unique"), currentSearch.session.unique_count],
                      [t("search.searched"), currentSearch.session.sources.length],
                      [t("search.unavailable"), unavailableCount],
                      [t("search.clusterCount"), currentSearch.clusters.length],
                      [t("analytics.duration"), formatDuration(currentSearch.session.duration_ms, locale)],
                    ].map(([label, value]) => <div key={String(label)}><dt className="text-[11px] text-muted-foreground">{label}</dt><dd className="mt-1 font-semibold tabular-nums">{typeof value === "number" ? formatNumber(value, locale) : value}</dd></div>)}
                  </dl>
              </section>
              {currentSearch.session.warnings.length > 0 && (
                <Alert className="mb-4 border-amber-500/40 bg-amber-500/5">
                  <AlertTriangle /><AlertTitle className="flex items-center gap-2">{t("search.partialCoverage")}<StatusBadge status={currentSearch.session.status} /></AlertTitle>
                  <AlertDescription><p>{t("state.partial")}</p><ul className="mt-1 space-y-1">{currentSearch.session.warnings.map((warning) => <li key={`${warning.source}-${warning.code}`}><strong>{warning.source}:</strong> {connectorFailure(warning.code, warning.message, locale, t, warning.source)}</li>)}</ul></AlertDescription>
                </Alert>
              )}
              <Tabs defaultValue="results">
                <TabsList className="mb-4"><TabsTrigger value="results">{t("search.results")}</TabsTrigger><TabsTrigger value="clusters">{t("nav.clusters")}</TabsTrigger><TabsTrigger value="timeline">{t("search.timeline")}</TabsTrigger><TabsTrigger value="analysis">{t("nav.analytics")}</TabsTrigger></TabsList>
                <TabsContent value="results">
                  {results.length ? (
                    <section aria-labelledby="results-title">
                      <div className="mb-3 flex items-center justify-between"><h2 id="results-title" className="flex items-center gap-2 text-sm font-semibold"><CheckCircle2 className="size-4 text-emerald-600" />{t("search.results")}</h2><span className="text-xs text-muted-foreground">{formatNumber(results.length, locale)} {t("search.resultsMeta")}</span></div>
                      <div ref={resultList} className="divide-y border-y">{visibleResults.map((item) => <ResultCard key={item.id} item={item} density={density} sessionId={currentSearch.session.id} initiallyBookmarked={bookmarkedContentIds.has(item.id)} />)}</div>
                      {totalPages > 1 && <div className="mt-5 flex items-center justify-center gap-1">{Array.from({ length: totalPages }, (_, index) => index + 1).map((number) => <Button key={number} size="icon-sm" variant={page === number ? "default" : "ghost"} onClick={() => setPage(number)} aria-current={page === number ? "page" : undefined}>{number}</Button>)}</div>}
                    </section>
                  ) : <EmptyState title={t("search.emptyTitle")} description={resultEmptyDescription} />}
                </TabsContent>
                <TabsContent value="clusters"><div className="divide-y border-y">{currentSearch.clusters.length ? currentSearch.clusters.map((cluster) => <section key={cluster.id} className="px-1 py-4"><div className="flex justify-between gap-4"><div><h3 className="font-medium" dir="auto">{cluster.representative_title}</h3><p className="mt-1 text-xs text-muted-foreground">{Object.entries(cluster.source_distribution).map(([source, count]) => `${source} ${count}`).join(" · ")}</p></div><span className="text-sm font-semibold tabular-nums">{cluster.member_count}</span></div></section>) : <EmptyState title={t("clusters.title")} description={t("clusters.empty")} />}</div></TabsContent>
                <TabsContent value="timeline"><Card className="shadow-none"><CardContent>{currentSearch.analytics.mentions_over_time.some((item) => item.count > 0) ? <ol className="space-y-2">{currentSearch.analytics.mentions_over_time.filter((item) => item.count > 0).map((item) => <li className="flex justify-between border-b pb-2 text-sm" key={item.timestamp}><time>{formatDate(item.timestamp, locale)}</time><strong className="tabular-nums">{formatNumber(item.count, locale)}</strong></li>)}</ol> : <p className="text-sm text-muted-foreground">{t("state.noData")}</p>}</CardContent></Card></TabsContent>
                <TabsContent value="analysis"><Card className="shadow-none"><CardContent><dl className="grid gap-4 sm:grid-cols-2">{Object.entries(currentSearch.analytics.platform_distribution).map(([source, count]) => <div className="flex justify-between border-b pb-2" key={source}><dt dir="ltr">{source}</dt><dd className="font-semibold tabular-nums">{formatNumber(count, locale)}</dd></div>)}</dl></CardContent></Card></TabsContent>
              </Tabs>
            </>
          )}
          {!loading && !currentSearch && !error && <EmptyState title={t("search.emptyTitle")} description={t("search.emptyDescription")} />}
        </section>

        <aside className={loading ? "hidden border-s ps-4 xl:block" : "hidden"} data-testid="desktop-trace-rail">
          <div className="sticky top-4">{loading && wideWorkspace && <LiveSearchTrace state={jobState} />}</div>
        </aside>
      </div>
    </div>
  );
}
