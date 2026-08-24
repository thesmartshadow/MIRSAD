import { RefreshCw } from "lucide-react";
import { Fragment, useEffect, useState } from "react";

import {
  EmptyState,
  ErrorState,
  PageHeader,
  PageSkeleton,
  StatusBadge,
} from "@/components/shared/page";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Slider } from "@/components/ui/slider";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { api } from "@/lib/api";
import { formatDate, formatNumber } from "@/lib/format";
import { useI18n } from "@/lib/i18n";
import {
  connectorFailure,
  sourceCoverage,
  sourceDetail,
} from "@/lib/source-presentation";
import type { SourceStatus } from "@/types/api";

function SourceTopology({
  sources,
  selected,
  onSelect,
}: {
  sources: SourceStatus[];
  selected: SourceStatus | null;
  onSelect: (source: SourceStatus) => void;
}) {
  const { locale, t } = useI18n();
  const visible = sources.filter((source) => source.key !== "mock").slice(0, 15);
  const modes = [...new Set(visible.map((source) => source.active_acquisition_mode))];
  const categoryRows = {
    social: { start: 66, span: 220 },
    news: { start: 346, span: 64 },
    developer_community: { start: 466, span: 48 },
  };
  const positions = new Map<string, { x: number; y: number }>();
  for (const category of ["social", "news", "developer_community"] as const) {
    const group = visible.filter((source) => source.category === category);
    group.forEach((source, index) => {
      const row = categoryRows[category];
      const column = index % 2;
      const rowIndex = Math.floor(index / 2);
      const rowCount = Math.ceil(group.length / 2);
      const y = row.start + (rowCount > 1 ? (row.span * rowIndex) / (rowCount - 1) : row.span / 2);
      positions.set(source.key, { x: 780 + column * 220, y });
    });
  }
  return (
    <section className="source-capability-space" aria-label={t("sources.topology")}>
      <div className="source-capability-space__map">
        <header><span>{t("sources.topology")}</span><strong>{formatNumber(visible.length, locale)}</strong></header>
        <svg viewBox="0 0 1200 560" role="group" aria-labelledby="source-topology-title source-topology-desc">
          <title id="source-topology-title">{t("sources.topology")}</title>
          <desc id="source-topology-desc">{t("sources.topologyDescription")}</desc>
          <path d="M40 280H1160" className="source-topology__datum" />
          {(["social", "news", "developer_community"] as const).map((category) => (
            <g key={category}>
              <path d={`M700 ${categoryRows[category].start - 30}H1160`} className="source-topology__band" />
              <text x="714" y={categoryRows[category].start - 14} className="source-topology__category">{t(`search.group.${category}`)}</text>
            </g>
          ))}
          {modes.map((mode, index) => {
            const y = 68 + index * (424 / Math.max(1, modes.length - 1));
            return (
              <g key={mode} className="source-topology__mode">
                <path d={`M116 ${y}H286 C350 ${y}, 350 280, 424 280`} />
                <circle cx="108" cy={y} r="6" />
                <text x="92" y={y + 4} textAnchor="end" direction="ltr">{mode.replaceAll("_", " ")}</text>
              </g>
            );
          })}
          <g className="source-topology__core" transform="translate(520 280)">
            <path d="M-68 0 0-56 68 0 0 56Z" />
            <circle r="18" />
            <text y="4" textAnchor="middle">MAFER</text>
          </g>
          {visible.map((source) => {
            const point = positions.get(source.key)!;
            const modeIndex = Math.max(0, modes.indexOf(source.active_acquisition_mode));
            const modeY = 68 + modeIndex * (424 / Math.max(1, modes.length - 1));
            const state = source.configuration_state === "restricted" ? "restricted" : source.status;
            const active = selected?.key === source.key;
            return (
              <g
                key={source.key}
                className="source-topology__platform"
                data-state={state}
                data-selected={active}
                role="button"
                tabIndex={0}
                aria-label={`${source.name}: ${state}`}
                onClick={() => onSelect(source)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    onSelect(source);
                  }
                }}
              >
                <path d={`M588 280 C674 280, 674 ${point.y}, ${point.x - 15} ${point.y}`} className="source-topology__path" />
                <path d={`M286 ${modeY} C350 ${modeY}, 350 280, 452 280`} className="source-topology__acquisition" />
                <circle cx={point.x} cy={point.y} r={active ? 14 : 10} className="source-topology__node" />
                <circle cx={point.x} cy={point.y} r="22" className="source-topology__hit" />
                <text x={point.x + 19} y={point.y + 4} textAnchor="start" className="source-topology__label">{source.name}</text>
              </g>
            );
          })}
        </svg>
      </div>
      <aside className="source-inspector" aria-live="polite">
        {selected ? (
          <>
            <div className="source-inspector__index" dir="ltr">{selected.key.toUpperCase()}</div>
            <div className="source-inspector__heading">
              <div><span>{t("sources.connector")}</span><h2>{selected.name}</h2></div>
              <StatusBadge status={selected.configuration_state === "restricted" ? "restricted" : selected.status} />
            </div>
            <p>{sourceCoverage(selected, t)}</p>
            <dl>
              <div><dt>{t("sources.state")}</dt><dd>{selected.configuration_state}</dd></div>
              <div><dt>{t("coverage.live")}</dt><dd dir="ltr">{selected.active_acquisition_mode}</dd></div>
              <div><dt>{t("sources.latency")}</dt><dd>{formatNumber(selected.last_latency_ms, locale, 1)} ms</dd></div>
              <div><dt>{t("sources.results")}</dt><dd>{formatNumber(selected.last_normalized_count, locale)}</dd></div>
            </dl>
            <div className="source-inspector__detail">{sourceDetail(selected, t)}</div>
          </>
        ) : (
          <p>{t("sources.topologyDescription")}</p>
        )}
      </aside>
    </section>
  );
}

export function SourcesPage() {
  const { locale, t } = useI18n();
  const [sources, setSources] = useState<SourceStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedKey, setSelectedKey] = useState<string | null>(null);

  const load = (refresh = false) => {
    setLoading(true);
    setError("");
    const request = refresh ? api.refreshSources() : api.getSources();
    request
      .then(setSources)
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setLoading(false));
  };
  useEffect(() => load(), []);

  const update = async (
    key: string,
    values: {
      enabled?: boolean;
      confidence?: number;
      github_scopes?: string[];
    },
  ) => {
    try {
      const updated = await api.updateSource(key, values);
      setSources((current) =>
        current.map((source) => (source.key === key ? updated : source)),
      );
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t("state.error"));
    }
  };

  return (
    <div className="instrument-page instrument-page--sources">
      <PageHeader
        title={t("sources.title")}
        description={t("sources.description")}
        actions={
          <Button
            variant="outline"
            size="sm"
            onClick={() => load(true)}
            disabled={loading}
          >
            <RefreshCw />
            {t("action.refresh")}
          </Button>
        }
      />
      {loading && sources.length === 0 ? (
        <PageSkeleton rows={6} />
      ) : error ? (
        <ErrorState message={error} onRetry={() => load()} />
      ) : sources.length === 0 ? (
        <EmptyState />
      ) : (
        <div className="space-y-5">
        <SourceTopology sources={sources} selected={sources.find((source) => source.key === selectedKey) ?? sources[0] ?? null} onSelect={(source) => setSelectedKey(source.key)} />
        <div className="source-configuration-rail" aria-label={t("sources.state")}>
          {sources
            .filter(
              (source) =>
                source.detail || source.configuration_state !== "configured",
            )
            .map((source) => (
              <button
                key={source.key}
                type="button"
                onClick={() => setSelectedKey(source.key)}
              >
                <span>{source.name}</span>
                <strong>{sourceDetail(source, t)}</strong>
              </button>
            ))}
        </div>
        <details className="source-register">
          <summary>{t("sources.connector")} / {t("sources.capabilities")}</summary>
        <Card className="overflow-hidden py-0 shadow-none">
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("sources.connector")}</TableHead>
                  <TableHead>{t("sources.state")}</TableHead>
                  <TableHead>{t("sources.health")}</TableHead>
                  <TableHead className="min-w-52">
                    {t("sources.confidence")}
                  </TableHead>
                  <TableHead>{t("sources.lastSuccess")}</TableHead>
                  <TableHead className="text-end">
                    {t("sources.latency")}
                  </TableHead>
                  <TableHead className="text-end">
                    {t("sources.requests")}
                  </TableHead>
                  <TableHead>{t("sources.failure")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(["social", "news", "developer_community"] as const).map(
                  (category) => (
                    <Fragment key={category}>
                      <TableRow className="bg-muted/50 hover:bg-muted/50">
                        <TableCell
                          colSpan={8}
                          className="py-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground"
                        >
                          {t(`search.group.${category}`)}
                        </TableCell>
                      </TableRow>
                      {sources
                        .filter((source) => source.category === category)
                        .map((source) => (
                          <TableRow key={source.key}>
                            <TableCell>
                              <div className="font-medium">{source.name}</div>
                              <div
                                className="text-xs text-muted-foreground"
                                dir="ltr"
                              >
                                {source.kind} · {source.key}
                              </div>
                              <div className="mt-1 max-w-64 text-xs text-muted-foreground">
                                {sourceCoverage(source, t)}
                              </div>
                              {source.key === "github" && (
                                <div className="mt-2 space-y-1">
                                  <div className="text-xs text-muted-foreground">
                                    {t("sources.scopes")}
                                  </div>
                                  {(
                                    [
                                      "repositories",
                                      "issues",
                                      "pull_requests",
                                    ] as const
                                  ).map((scope) => {
                                    const selected = source.configuration
                                      .scopes ?? ["repositories"];
                                    return (
                                      <label
                                        key={scope}
                                        className="flex items-center gap-2 text-xs"
                                      >
                                        <Checkbox
                                          checked={selected.includes(scope)}
                                          onCheckedChange={(checked) => {
                                            const next =
                                              checked === true
                                                ? [
                                                    ...new Set([
                                                      ...selected,
                                                      scope,
                                                    ]),
                                                  ]
                                                : selected.filter(
                                                    (value) => value !== scope,
                                                  );
                                            if (next.length > 0)
                                              void update(source.key, {
                                                github_scopes: next,
                                              });
                                          }}
                                        />
                                        {t(
                                          scope === "repositories"
                                            ? "sources.repositories"
                                            : scope === "issues"
                                              ? "sources.issues"
                                              : "sources.pullRequests",
                                        )}
                                      </label>
                                    );
                                  })}
                                </div>
                              )}
                            </TableCell>
                            <TableCell>
                              <label className="flex items-center gap-2 text-sm">
                                <Checkbox
                                  checked={source.enabled}
                                  onCheckedChange={(checked) =>
                                    update(source.key, {
                                      enabled: checked === true,
                                    })
                                  }
                                />
                                {source.enabled
                                  ? t("sources.enabled")
                                  : t("sources.disabled")}
                              </label>
                            </TableCell>
                            <TableCell>
                              <StatusBadge
                                status={
                                  source.configuration_state === "restricted"
                                    ? "restricted"
                                    : source.status
                                }
                              />
                              <div className="mt-1 text-xs text-muted-foreground">
                                <span dir="ltr">
                                  HTTP {source.http_status ?? "—"}
                                </span>{" "}
                                · {t("sources.results")}:{" "}
                                {formatNumber(
                                  source.last_normalized_count,
                                  locale,
                                )}{" "}
                                · {t("sources.malformed")}:{" "}
                                {formatNumber(
                                  source.last_malformed_count,
                                  locale,
                                )}
                              </div>
                            </TableCell>
                            <TableCell>
                              <div className="flex items-center gap-3">
                                <Slider
                                  aria-label={`${source.name} ${t("sources.confidence")}`}
                                  value={[source.confidence]}
                                  min={0}
                                  max={100}
                                  step={1}
                                  onValueCommitted={(value) => {
                                    const next = Array.isArray(value)
                                      ? value[0]
                                      : value;
                                    update(source.key, { confidence: next });
                                  }}
                                />
                                <span className="w-9 text-end text-xs tabular-nums">
                                  {formatNumber(source.confidence, locale)}
                                </span>
                              </div>
                            </TableCell>
                            <TableCell className="whitespace-nowrap text-xs">
                              {formatDate(source.last_success_at, locale)}
                            </TableCell>
                            <TableCell className="text-end tabular-nums">
                              {formatNumber(source.last_latency_ms, locale, 1)}{" "}
                              ms
                              <div className="text-[10px] text-muted-foreground">
                                Ø{" "}
                                {formatNumber(
                                  source.average_latency_ms,
                                  locale,
                                  1,
                                )}{" "}
                                ms
                              </div>
                            </TableCell>
                            <TableCell className="text-end tabular-nums">
                              {formatNumber(source.request_count, locale)}
                            </TableCell>
                            <TableCell className="max-w-52 text-xs text-destructive">
                              <div className="line-clamp-2">
                                {source.failure_category ? (
                                  <>
                                    <span className="font-mono" dir="ltr">
                                      {source.failure_category}
                                    </span>
                                    :{" "}
                                  </>
                                ) : null}
                                {source.recent_failure
                                  ? connectorFailure(
                                      source.failure_category,
                                      source.recent_failure,
                                      locale,
                                      t,
                                    )
                                  : "—"}
                              </div>
                            </TableCell>
                          </TableRow>
                        ))}
                    </Fragment>
                  ),
                )}
              </TableBody>
            </Table>
          </div>
        </Card>
        </details>
        </div>
      )}
    </div>
  );
}
