import {
  Activity,
  Database,
  FileSearch,
  RefreshCw,
  ServerCog,
  type LucideIcon,
} from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";

import {
  ErrorState,
  PageHeader,
  PageSkeleton,
  StatusBadge,
} from "@/components/shared/page";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { formatNumber } from "@/lib/format";
import { useI18n, type TranslationKey } from "@/lib/i18n";
import type { QualitySummary, SystemStatus } from "@/types/api";

const capabilityKeys: Record<string, TranslationKey> = {
  fts5: "capability.fts5",
  bm25: "capability.bm25",
  arabic_normalization: "capability.arabic_normalization",
  deduplication: "capability.deduplication",
  explainable_scoring: "capability.explainable_scoring",
  clustering: "capability.clustering",
  local_outcome_feedback: "capability.localOutcomeFeedback",
  adaptive_shadow_only: "capability.adaptiveShadow",
  evidence_graph: "capability.evidenceGraph",
};

export function SystemPage() {
  const { locale, t } = useI18n();
  const [system, setSystem] = useState<SystemStatus | null>(null);
  const [quality, setQuality] = useState<QualitySummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const load = () => {
    setLoading(true);
    setError("");
    Promise.all([api.getSystem(), api.getQuality()])
      .then(([nextSystem, nextQuality]) => {
        setSystem(nextSystem);
        setQuality(nextQuality);
      })
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setLoading(false));
  };
  useEffect(load, []);
  const metrics: Array<{
    icon: LucideIcon;
    label: string;
    value: ReactNode;
  }> = system
    ? [
        {
          icon: Activity,
          label: t("system.api"),
          value: <StatusBadge status={system.api_status} />,
        },
        {
          icon: Database,
          label: t("system.database"),
          value: <StatusBadge status={system.database_status} />,
        },
        {
          icon: FileSearch,
          label: t("system.fts"),
          value: <StatusBadge status={system.fts_status} />,
        },
        {
          icon: ServerCog,
          label: t("system.records"),
          value: formatNumber(system.record_count, locale),
        },
        {
          icon: FileSearch,
          label: t("system.indexed"),
          value: formatNumber(system.index_count, locale),
        },
      ]
    : [];
  return (
    <div className="instrument-page instrument-page--system">
      <PageHeader
        title={t("system.title")}
        description={t("system.description")}
        actions={
          <Button variant="outline" size="sm" onClick={load}>
            <RefreshCw />
            {t("action.refresh")}
          </Button>
        }
      />
      {loading && !system ? (
        <PageSkeleton />
      ) : error ? (
        <ErrorState message={error} onRetry={load} />
      ) : (
        system && (
          <div className="space-y-4">
            <div className="system-signal-band">
              {metrics.map(({ icon: MetricIcon, label, value }, index) => {
                return (
                  <section key={index} className="system-signal">
                      <MetricIcon className="mb-3 size-4 text-muted-foreground" />
                      <div className="text-xs text-muted-foreground">
                        {label}
                      </div>
                      <div className="mt-1 text-xl font-semibold">{value}</div>
                  </section>
                );
              })}
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <Card className="shadow-none">
                <CardContent className="py-3">
                  <div className="text-xs text-muted-foreground">
                    {t("system.integrity")}
                  </div>
                  <div className="mt-1 font-mono text-lg" dir="ltr">
                    {system.database_integrity}
                  </div>
                </CardContent>
              </Card>
              <Card className="shadow-none">
                <CardContent className="py-3">
                  <div className="text-xs text-muted-foreground">
                    {t("system.foreignKeys")}
                  </div>
                  <div className="mt-1 text-lg font-semibold tabular-nums">
                    {formatNumber(system.foreign_key_violations, locale)}
                  </div>
                </CardContent>
              </Card>
            </div>
            <div className="grid gap-4 lg:grid-cols-2">
              <Card className="shadow-none">
                <CardHeader>
                  <CardTitle>{t("system.connectors")}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  {Object.entries(system.connector_status).map(
                    ([status, count]) => (
                      <div
                        key={status}
                        className="flex items-center justify-between border-b py-2 last:border-0"
                      >
                        <StatusBadge status={status} />
                        <span className="font-medium tabular-nums">
                          {formatNumber(count, locale)}
                        </span>
                      </div>
                    ),
                  )}
                </CardContent>
              </Card>
              <Card className="shadow-none">
                <CardHeader>
                  <CardTitle>{t("system.capabilities")}</CardTitle>
                </CardHeader>
                <CardContent>
                  <ul className="space-y-2">
                    {system.capabilities.map((capability) => (
                      <li
                        key={capability}
                        className="flex items-start gap-2 text-sm"
                      >
                        <span className="mt-1.5 size-1.5 rounded-full bg-chart-4" />
                        {capabilityKeys[capability]
                          ? t(capabilityKeys[capability])
                          : capability}
                      </li>
                    ))}
                  </ul>
                  <div className="mt-5 border-t pt-3 text-xs text-muted-foreground">
                    {t("system.version")}: {system.version}
                  </div>
                </CardContent>
              </Card>
            </div>
            {quality && (
              <Card className="shadow-none">
                <CardHeader>
                  <CardTitle>{t("system.quality")}</CardTitle>
                  <p className="text-sm text-muted-foreground">
                    {t("system.qualityDescription")}
                  </p>
                </CardHeader>
                <CardContent className="space-y-5">
                  <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
                    {[
                      ["system.searchCount", quality.search_count],
                      ["system.zeroRate", `${formatNumber(quality.zero_result_rate * 100, locale, 1)}%`],
                      ["system.explicitRelevant", quality.explicit_relevant],
                      ["system.explicitNotRelevant", quality.explicit_not_relevant],
                      ["system.averageRounds", quality.average_rounds],
                      ["system.averageRequests", quality.average_request_count],
                    ].map(([label, value]) => (
                      <div key={label} className="rounded-md border p-3">
                        <div className="text-xs text-muted-foreground">
                          {t(label as TranslationKey)}
                        </div>
                        <div className="mt-1 text-lg font-semibold tabular-nums">
                          {typeof value === "number"
                            ? formatNumber(value, locale, 1)
                            : value}
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className="grid gap-4 lg:grid-cols-3">
                    <div>
                      <h3 className="mb-2 text-sm font-semibold">
                        {t("system.stopReasons")}
                      </h3>
                      <div className="flex flex-wrap gap-2">
                        {Object.entries(quality.stop_reasons).map(([key, value]) => (
                          <Badge key={key} variant="outline">
                            {key}: {formatNumber(value, locale)}
                          </Badge>
                        ))}
                      </div>
                    </div>
                    <div>
                      <h3 className="mb-2 text-sm font-semibold">
                        {t("system.shadowComparisons")}
                      </h3>
                      <div className="flex flex-wrap gap-2">
                        {Object.entries(quality.shadow_comparisons).map(([key, value]) => (
                          <Badge key={key} variant="secondary">
                            {key}: {formatNumber(value, locale)}
                          </Badge>
                        ))}
                      </div>
                    </div>
                    <div>
                      <h3 className="mb-2 text-sm font-semibold">
                        {t("system.productionConfig")}
                      </h3>
                      <div className="space-y-2">
                        {quality.configuration_snapshots.map((snapshot) => (
                          <div key={snapshot.id} className="rounded-md border p-2 text-xs">
                            <Badge variant="outline">{snapshot.slot}</Badge>
                            <p className="mt-2 text-muted-foreground">
                              {snapshot.slot === "verified_production"
                                ? t("system.configVerified")
                                : snapshot.slot === "experimental"
                                  ? t("system.configExperimental")
                                  : t("system.configInactive")}
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                  <div className="grid gap-4 border-t pt-5 lg:grid-cols-3">
                    {[
                      ["system.queryClasses", quality.query_class_distribution],
                      ["system.languages", quality.language_distribution],
                      ["system.uncertainty", quality.uncertainty_distribution],
                    ].map(([label, distribution]) => (
                      <div key={label as string}>
                        <h3 className="mb-2 text-sm font-semibold">
                          {t(label as TranslationKey)}
                        </h3>
                        <div className="flex flex-wrap gap-2">
                          {Object.entries(distribution as Record<string, number>).length ? (
                            Object.entries(distribution as Record<string, number>).map(
                              ([key, value]) => (
                                <Badge key={key} variant="outline">
                                  {key}: {formatNumber(value, locale)}
                                </Badge>
                              ),
                            )
                          ) : (
                            <span className="text-sm text-muted-foreground">
                              {t("system.noObservedData")}
                            </span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className="grid gap-4 border-t pt-5 lg:grid-cols-2">
                    <div>
                      <h3 className="mb-1 text-sm font-semibold">
                        {t("system.sourceUtility")}
                      </h3>
                      <p className="mb-3 text-xs text-muted-foreground">
                        {t("system.utilityNotice")}
                      </p>
                      <div className="space-y-2">
                        {quality.source_utility.length ? (
                          quality.source_utility.slice(0, 12).map((item) => (
                            <div
                              key={`${item.query_class}:${item.source}`}
                              className="flex items-center justify-between gap-3 rounded-md border p-2 text-xs"
                            >
                              <span dir="auto">
                                {item.source} / {item.query_class}
                              </span>
                              <span className="shrink-0 tabular-nums text-muted-foreground">
                                {formatNumber(item.observations, locale)} · {item.adjustment > 0 ? "+" : ""}
                                {formatNumber(item.adjustment, locale, 2)}
                              </span>
                            </div>
                          ))
                        ) : (
                          <span className="text-sm text-muted-foreground">
                            {t("system.noObservedData")}
                          </span>
                        )}
                      </div>
                    </div>
                    <div>
                      <h3 className="mb-1 text-sm font-semibold">
                        {t("system.engineUtility")}
                      </h3>
                      <p className="mb-3 text-xs text-muted-foreground">
                        {t("system.engineUtilityNotice")}
                      </p>
                      <div className="space-y-2">
                        {quality.engine_utility.length ? (
                          quality.engine_utility.slice(0, 12).map((item, index) => (
                            <div
                              key={`${String(item.engine)}:${String(item.target_platform)}:${index}`}
                              className="flex items-center justify-between gap-3 rounded-md border p-2 text-xs"
                            >
                              <span dir="auto">
                                {String(item.engine)} / {String(item.target_platform)}
                              </span>
                              <span className="shrink-0 tabular-nums text-muted-foreground">
                                {t("system.requests")}: {formatNumber(Number(item.requests), locale)} · {t("system.canonicalYield")}: {formatNumber(Number(item.canonical_yield), locale)}
                              </span>
                            </div>
                          ))
                        ) : (
                          <span className="text-sm text-muted-foreground">
                            {t("system.noObservedData")}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        )
      )}
    </div>
  );
}
