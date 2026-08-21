import { Filter, Info, Search, SlidersHorizontal } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";

import { StatusBadge } from "@/components/shared/page";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Field, FieldLabel } from "@/components/ui/field";
import {
  InputGroup,
  InputGroupAddon,
  InputGroupInput,
} from "@/components/ui/input-group";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { sourceCoverage, sourceDetail } from "@/lib/source-presentation";
import type { SearchRequest, SourceStatus } from "@/types/api";

type SourcePreset =
  | "automatic"
  | "all"
  | "social"
  | "news"
  | "developer_community"
  | "custom";
type ContentType = SearchRequest["content_types"][number];

const mockEnabled = import.meta.env.VITE_ENABLE_MOCK_CONNECTOR === "true";

export const defaultSearchRequest: SearchRequest = {
  query: "",
  sources: mockEnabled
    ? ["mock"]
    : ["bluesky", "hacker_news", "github", "gdelt", "rss"],
  time_range: "7d",
  language: "all",
  limit: 50,
  exact_phrase: false,
  sort: "best_match",
  content_types: [],
  has_media: null,
  has_links: null,
  hashtags: [],
  source_options: {},
  search_mode: "balanced",
  source_selection: "auto",
};

function canParticipate(source: SourceStatus, query: string): boolean {
  const searchable =
    source.capabilities.keyword_search !== false ||
    (query.trim().startsWith("#") &&
      source.capabilities.hashtag_search !== false);
  return (
    searchable &&
    source.enabled &&
    source.configured &&
    source.configuration_state === "configured" &&
    ![
      "unavailable",
      "rate_limited",
      "restricted",
      "access_limited",
      "quota_exhausted",
      "disabled",
      "auth_required",
    ].includes(source.status)
  );
}

export function SearchForm({
  initialQuery = "",
  initialRequest,
  loading,
  onSearch,
  sourceCatalog,
}: {
  initialQuery?: string;
  initialRequest?: SearchRequest;
  loading: boolean;
  onSearch: (request: SearchRequest) => void;
  sourceCatalog?: SourceStatus[];
}) {
  const { t } = useI18n();
  const [form, setForm] = useState<SearchRequest>({
    ...defaultSearchRequest,
    ...initialRequest,
    query: initialQuery || initialRequest?.query || "",
  });
  const [sources, setSources] = useState<SourceStatus[]>(sourceCatalog ?? []);
  const [catalogReady, setCatalogReady] = useState(sourceCatalog !== undefined);
  const [sourceError, setSourceError] = useState("");
  const [validation, setValidation] = useState("");
  const [preset, setPreset] = useState<SourcePreset>(
    initialRequest?.source_selection === "explicit" ? "custom" : "automatic",
  );

  useEffect(() => {
    if (!initialRequest) return;
    setForm({ ...defaultSearchRequest, ...initialRequest });
    setPreset(
      initialRequest.source_selection === "auto" ? "automatic" : "custom",
    );
  }, [initialRequest]);

  useEffect(() => {
    if (sourceCatalog) {
      setSources(sourceCatalog);
      setCatalogReady(true);
      return;
    }
    let active = true;
    api
      .getSources()
      .then((value) => active && setSources(Array.isArray(value) ? value : []))
      .catch((reason: Error) => active && setSourceError(reason.message))
      .finally(() => active && setCatalogReady(true));
    return () => {
      active = false;
    };
  }, [sourceCatalog]);

  useEffect(() => {
    if (!sources.length) return;
    setForm((current) => {
      const available = current.sources.filter((key) =>
        sources.some(
          (source) =>
            source.key === key && canParticipate(source, current.query),
        ),
      );
      const selected =
        available.length === 0 &&
        current.sources.length === defaultSearchRequest.sources.length &&
        current.sources.every((key) =>
          defaultSearchRequest.sources.includes(key),
        )
          ? sources
              .filter((source) => canParticipate(source, current.query))
              .map((source) => source.key)
          : available;
      return { ...current, sources: selected };
    });
  }, [sources, form.query]);

  const timeLabels = {
    "24h": t("search.day"),
    "7d": t("search.week"),
    "30d": t("search.month"),
    all: t("search.allTime"),
  };
  const languageLabels = {
    all: t("search.allLanguages"),
    ar: t("common.arabic"),
    en: t("common.english"),
  };
  const sortLabels = {
    best_match: t("search.bestMatch"),
    newest: t("search.newest"),
    most_engaged: t("search.engaged"),
    cross_platform: t("search.crossPlatform"),
  };
  const modeLabels = {
    fast: t("search.modeFast"),
    balanced: t("search.modeBalanced"),
    deep: t("search.modeDeep"),
  };
  const grouped = [
    {
      key: "social_direct",
      label: "search.group.socialDirect" as const,
      sources: sources.filter(
        (source) =>
          source.category === "social" &&
          source.active_acquisition_mode !== "WEB_INDEX",
      ),
    },
    {
      key: "social_web",
      label: "search.group.socialWeb" as const,
      sources: sources.filter(
        (source) =>
          source.category === "social" &&
          source.active_acquisition_mode === "WEB_INDEX",
      ),
    },
    {
      key: "news",
      label: "search.group.news" as const,
      sources: sources.filter((source) => source.category === "news"),
    },
    {
      key: "developer_community",
      label: "search.group.developer_community" as const,
      sources: sources.filter(
        (source) => source.category === "developer_community",
      ),
    },
  ].filter((group) => group.sources.length > 0);
  const supportedContentTypes = new Set<ContentType>();
  for (const source of sources.filter((item) =>
    form.sources.includes(item.key),
  )) {
    for (const type of source.capabilities.content_types) {
      if (
        ["posts", "videos", "channels", "threads", "issues", "news"].includes(
          type,
        )
      )
        supportedContentTypes.add(type as ContentType);
    }
  }
  const supportsHashtag = sources.some(
    (source) =>
      form.sources.includes(source.key) &&
      source.capabilities.hashtag_search !== false,
  );
  const threads = sources.find((source) => source.key === "threads");
  const threadsSelected = Boolean(threads && form.sources.includes("threads"));

  const toggleSource = (source: string, checked: boolean) => {
    setPreset("custom");
    setForm((current) => ({
      ...current,
      source_selection: "explicit",
      sources: checked
        ? [...new Set([...current.sources, source])]
        : current.sources.filter((item) => item !== source),
    }));
  };

  const selectPreset = (next: SourcePreset) => {
    setPreset(next);
    if (next === "custom") {
      setForm((current) => ({ ...current, source_selection: "explicit" }));
      return;
    }
    setForm((current) => ({
      ...current,
      source_selection: next === "automatic" ? "auto" : "explicit",
      sources: sources
        .filter(
          (source) =>
            canParticipate(source, current.query) &&
            (next === "automatic" ||
              next === "all" ||
              source.category === next),
        )
        .map((source) => source.key),
    }));
  };

  const setSourceOption = (source: string, key: string, value: unknown) =>
    setForm((current) => ({
      ...current,
      source_options: {
        ...current.source_options,
        [source]: { ...(current.source_options[source] ?? {}), [key]: value },
      },
    }));

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!form.query.trim()) {
      setValidation(t("search.validation"));
      return;
    }
    if (!form.sources.length) {
      setValidation(t("search.sourcesRequired"));
      return;
    }
    setValidation("");
    onSearch({ ...form, query: form.query.trim() });
  };

  return (
    <section className="mb-5 border-y bg-card/55 px-1 py-4 sm:px-4" data-search-instrument>
        <form
          onSubmit={submit}
          className="space-y-4"
          aria-label={t("search.title")}
          aria-busy={loading}
        >
          <Field data-invalid={Boolean(validation)}>
            <FieldLabel htmlFor="search-query">
              {t("search.keyword")}
            </FieldLabel>
            <div className="flex flex-col gap-2 sm:flex-row">
              <InputGroup className="h-12 flex-1 border-primary/35 bg-background shadow-[inset_3px_0_0_var(--primary)] focus-within:border-primary rtl:shadow-[inset_-3px_0_0_var(--primary)]">
                <InputGroupAddon>
                  <Search />
                </InputGroupAddon>
                <InputGroupInput
                  id="search-query"
                  value={form.query}
                  onChange={(event) =>
                    setForm({ ...form, query: event.target.value })
                  }
                  placeholder={t("search.placeholder")}
                  maxLength={300}
                  aria-invalid={Boolean(validation)}
                  data-search-command
                />
              </InputGroup>
              <Button
                type="submit"
                className="h-12 min-w-32"
                disabled={!catalogReady || !form.sources.length}
              >
                <Search /> {t("action.search")}
              </Button>
            </div>
          </Field>
          {(validation || sourceError) && (
            <Alert variant="destructive" className="py-2">
              <AlertDescription>{validation || sourceError}</AlertDescription>
            </Alert>
          )}

          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <StatusBadge status={preset === "automatic" ? "automatic" : "custom"} />
            <span>{timeLabels[form.time_range]}</span>
            <span>·</span>
            <span>{modeLabels[form.search_mode]}</span>
            <span>·</span>
            <span>{languageLabels[form.language]}</span>
            {form.exact_phrase && <span>· {t("search.exact")}</span>}
          </div>
          <details className="group border-t pt-3">
            <summary className="flex cursor-pointer list-none items-center gap-2 text-sm font-medium text-muted-foreground hover:text-foreground">
              <SlidersHorizontal className="size-4" />
              {t("search.advancedOptions")}
            </summary>
            <div className="grid gap-4 pt-4 lg:grid-cols-[minmax(360px,1.45fr)_minmax(280px,1fr)]">
            <Field>
              <FieldLabel>
                <Filter /> {t("search.sources")}
              </FieldLabel>
              <Select
                value={preset}
                onValueChange={(value) => selectPreset(value as SourcePreset)}
              >
                <SelectTrigger
                  className="mb-3 w-full"
                  aria-label={t("search.sourcePreset")}
                >
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="automatic">
                    {t("search.presetAutomatic")}
                  </SelectItem>
                  <SelectItem value="all">{t("search.presetAll")}</SelectItem>
                  <SelectItem value="social">
                    {t("search.presetSocial")}
                  </SelectItem>
                  <SelectItem value="news">{t("search.presetNews")}</SelectItem>
                  <SelectItem value="developer_community">
                    {t("search.presetDeveloper")}
                  </SelectItem>
                  <SelectItem value="custom">
                    {t("search.presetCustom")}
                  </SelectItem>
                </SelectContent>
              </Select>
              {preset === "automatic" && (
                <p className="mb-3 rounded-md border bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
                  <strong className="font-medium text-foreground">
                    {t("search.automaticRouting")}
                  </strong>{" "}
                  {t("search.automaticRoutingDescription")}
                </p>
              )}
              <div className="space-y-3 rounded-md border p-3">
                {grouped.map((group) => (
                  <section
                    key={group.key}
                    aria-labelledby={`source-group-${group.key}`}
                  >
                    <h3
                      id={`source-group-${group.key}`}
                      className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground"
                    >
                      {t(group.label)}
                    </h3>
                    <div className="grid gap-1 sm:grid-cols-2">
                      {group.sources.map((source) => {
                        const available = canParticipate(source, form.query);
                        return (
                          <div
                            key={source.key}
                            className="flex min-w-0 items-start gap-2 rounded-sm py-1"
                          >
                            <Checkbox
                              id={`source-${source.key}`}
                              aria-label={source.name}
                              checked={form.sources.includes(source.key)}
                              disabled={!available}
                              onCheckedChange={(checked) =>
                                toggleSource(source.key, checked === true)
                              }
                            />
                            <div
                              className={
                                available
                                  ? "min-w-0 text-sm"
                                  : "min-w-0 text-sm text-muted-foreground"
                              }
                            >
                              <span className="flex items-center gap-1.5">
                                <label
                                  htmlFor={`source-${source.key}`}
                                  className={
                                    available ? "cursor-pointer" : undefined
                                  }
                                >
                                  {source.name}
                                </label>
                                <StatusBadge status={source.status} />
                                <Tooltip>
                                  <TooltipTrigger
                                    render={
                                      <button
                                        type="button"
                                        className="rounded-sm focus-visible:outline-2 focus-visible:outline-ring"
                                        aria-label={`${source.name} ${t("sources.capabilities")}`}
                                      />
                                    }
                                  >
                                    <Info className="size-3" />
                                  </TooltipTrigger>
                                  <TooltipContent>
                                    {sourceCoverage(source, t)}
                                  </TooltipContent>
                                </Tooltip>
                              </span>
                              {!available && (
                                <span className="block truncate text-[10px]">
                                  {sourceDetail(source, t)}
                                </span>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </section>
                ))}
              </div>
            </Field>

            <div className="grid content-start gap-3 sm:grid-cols-2">
              <Field>
                <FieldLabel>{t("search.timeRange")}</FieldLabel>
                <Select
                  value={form.time_range}
                  onValueChange={(value) =>
                    setForm({
                      ...form,
                      time_range: value as SearchRequest["time_range"],
                    })
                  }
                >
                  <SelectTrigger
                    className="w-full"
                    aria-label={t("search.timeRange")}
                  >
                    <SelectValue>{timeLabels[form.time_range]}</SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="24h">{t("search.day")}</SelectItem>
                    <SelectItem value="7d">{t("search.week")}</SelectItem>
                    <SelectItem value="30d">{t("search.month")}</SelectItem>
                    <SelectItem value="all">{t("search.allTime")}</SelectItem>
                  </SelectContent>
                </Select>
              </Field>
              <Field>
                <FieldLabel>{t("search.language")}</FieldLabel>
                <Select
                  value={form.language}
                  onValueChange={(value) =>
                    setForm({
                      ...form,
                      language: value as SearchRequest["language"],
                    })
                  }
                >
                  <SelectTrigger
                    className="w-full"
                    aria-label={t("search.language")}
                  >
                    <SelectValue>{languageLabels[form.language]}</SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">
                      {t("search.allLanguages")}
                    </SelectItem>
                    <SelectItem value="en">{t("common.english")}</SelectItem>
                    <SelectItem value="ar">{t("common.arabic")}</SelectItem>
                  </SelectContent>
                </Select>
              </Field>
              <Field>
                <FieldLabel>{t("search.sort")}</FieldLabel>
                <Select
                  value={form.sort}
                  onValueChange={(value) =>
                    setForm({ ...form, sort: value as SearchRequest["sort"] })
                  }
                >
                  <SelectTrigger
                    className="w-full"
                    aria-label={t("search.sort")}
                  >
                    <SelectValue>{sortLabels[form.sort]}</SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="best_match">
                      {t("search.bestMatch")}
                    </SelectItem>
                    <SelectItem value="newest">{t("search.newest")}</SelectItem>
                    <SelectItem value="most_engaged">
                      {t("search.engaged")}
                    </SelectItem>
                    <SelectItem value="cross_platform">
                      {t("search.crossPlatform")}
                    </SelectItem>
                  </SelectContent>
                </Select>
              </Field>
              <Field>
                <FieldLabel>{t("search.resultLimit")}</FieldLabel>
                <Select
                  value={String(form.limit)}
                  onValueChange={(value) =>
                    setForm({ ...form, limit: Number(value) })
                  }
                >
                  <SelectTrigger
                    className="w-full"
                    aria-label={t("search.resultLimit")}
                  >
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {[25, 50, 100, 200].map((limit) => (
                      <SelectItem key={limit} value={String(limit)}>
                        {limit}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>
              <Field>
                <FieldLabel>{t("search.mode")}</FieldLabel>
                <Select
                  value={form.search_mode}
                  onValueChange={(value) =>
                    setForm({
                      ...form,
                      search_mode: value as SearchRequest["search_mode"],
                    })
                  }
                >
                  <SelectTrigger
                    className="w-full"
                    aria-label={t("search.mode")}
                  >
                    <SelectValue>{modeLabels[form.search_mode]}</SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="fast">{t("search.modeFast")}</SelectItem>
                    <SelectItem value="balanced">
                      {t("search.modeBalanced")}
                    </SelectItem>
                    <SelectItem value="deep">{t("search.modeDeep")}</SelectItem>
                  </SelectContent>
                </Select>
                <p className="mt-1 text-xs text-muted-foreground">
                  {t(`search.mode.${form.search_mode}`)}
                </p>
              </Field>
            </div>
          </div>

          {(supportedContentTypes.size > 0 ||
            supportsHashtag ||
            threadsSelected) && (
            <div className="space-y-3 border-t pt-4">
              <div className="flex items-center gap-2 text-sm font-medium">
                <SlidersHorizontal className="size-4" />
                {t("search.socialFilters")}
              </div>
              {supportedContentTypes.size > 0 && (
                <div className="flex flex-wrap gap-3">
                  {[...supportedContentTypes].map((type) => (
                    <label
                      key={type}
                      className="flex items-center gap-2 text-sm"
                    >
                      <Checkbox
                        checked={form.content_types.includes(type)}
                        onCheckedChange={(checked) =>
                          setForm({
                            ...form,
                            content_types:
                              checked === true
                                ? [...form.content_types, type]
                                : form.content_types.filter(
                                    (item) => item !== type,
                                  ),
                          })
                        }
                      />
                      {t(`search.content.${type}`)}
                    </label>
                  ))}
                </div>
              )}
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <Select
                  value={
                    form.has_media === null ? "any" : String(form.has_media)
                  }
                  onValueChange={(value) =>
                    setForm({
                      ...form,
                      has_media: value === "any" ? null : value === "true",
                    })
                  }
                >
                  <SelectTrigger aria-label={t("search.hasMedia")}>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="any">{t("search.mediaAny")}</SelectItem>
                    <SelectItem value="true">{t("search.hasMedia")}</SelectItem>
                    <SelectItem value="false">{t("search.noMedia")}</SelectItem>
                  </SelectContent>
                </Select>
                <Select
                  value={
                    form.has_links === null ? "any" : String(form.has_links)
                  }
                  onValueChange={(value) =>
                    setForm({
                      ...form,
                      has_links: value === "any" ? null : value === "true",
                    })
                  }
                >
                  <SelectTrigger aria-label={t("search.hasLinks")}>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="any">{t("search.linksAny")}</SelectItem>
                    <SelectItem value="true">{t("search.hasLinks")}</SelectItem>
                    <SelectItem value="false">{t("search.noLinks")}</SelectItem>
                  </SelectContent>
                </Select>
                {supportsHashtag && (
                  <InputGroup>
                    <InputGroupInput
                      aria-label={t("search.hashtags")}
                      placeholder={t("search.hashtags")}
                      value={form.hashtags.join(", ")}
                      onChange={(event) =>
                        setForm({
                          ...form,
                          hashtags: event.target.value
                            .split(",")
                            .map((value) => value.trim().replace(/^#/, ""))
                            .filter(Boolean)
                            .slice(0, 10),
                        })
                      }
                    />
                  </InputGroup>
                )}
                {threadsSelected &&
                  threads?.capabilities.search_modes.includes("topic_tag") && (
                    <Select
                      value={String(
                        form.source_options.threads?.mode ?? "keyword",
                      )}
                      onValueChange={(value) =>
                        setSourceOption("threads", "mode", value)
                      }
                    >
                      <SelectTrigger aria-label={t("search.threadsMode")}>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="keyword">
                          {t("search.keywordMode")}
                        </SelectItem>
                        <SelectItem value="topic_tag">
                          {t("search.topicTagMode")}
                        </SelectItem>
                      </SelectContent>
                    </Select>
                  )}
                {threadsSelected &&
                  threads?.capabilities.sort_modes.includes("top") && (
                    <Select
                      value={String(form.source_options.threads?.sort ?? "top")}
                      onValueChange={(value) =>
                        setSourceOption("threads", "sort", value)
                      }
                    >
                      <SelectTrigger aria-label={t("search.threadsSort")}>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="top">{t("search.top")}</SelectItem>
                        <SelectItem value="recent">
                          {t("search.recent")}
                        </SelectItem>
                      </SelectContent>
                    </Select>
                  )}
              </div>
            </div>
          )}

          <label className="flex cursor-pointer items-center gap-2 border-t pt-3 text-sm">
            <Checkbox
              checked={form.exact_phrase}
              onCheckedChange={(checked) =>
                setForm({ ...form, exact_phrase: checked === true })
              }
            />
            {t("search.exact")}
          </label>
          </details>
        </form>
    </section>
  );
}
