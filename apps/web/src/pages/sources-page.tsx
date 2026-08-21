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

export function SourcesPage() {
  const { locale, t } = useI18n();
  const [sources, setSources] = useState<SourceStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

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
    <div>
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
                              {source.detail && (
                                <div className="mt-1 max-w-48 text-xs text-muted-foreground">
                                  {sourceDetail(source, t)}
                                </div>
                              )}
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
      )}
    </div>
  );
}
