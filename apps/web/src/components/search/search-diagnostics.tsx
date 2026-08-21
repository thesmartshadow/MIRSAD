import { Activity } from "lucide-react";
import { useState } from "react";

import {
  ErrorState,
  PageSkeleton,
  StatusBadge,
} from "@/components/shared/page";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { api } from "@/lib/api";
import { formatDuration, formatNumber } from "@/lib/format";
import { useI18n } from "@/lib/i18n";
import type { SearchDiagnostics as SearchDiagnosticsType } from "@/types/api";

export function SearchDiagnostics({ sessionId }: { sessionId: string }) {
  const { locale, t } = useI18n();
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<SearchDiagnosticsType | null>(null);
  const [error, setError] = useState("");
  const load = (nextOpen: boolean) => {
    setOpen(nextOpen);
    if (nextOpen && !data)
      api
        .getDiagnostics(sessionId)
        .then(setData)
        .catch((reason: Error) => setError(reason.message));
  };
  const diagnostics = data?.diagnostics;
  return (
    <Dialog open={open} onOpenChange={load}>
      <DialogTrigger render={<Button variant="outline" size="sm" />}>
        <Activity />
        {t("action.diagnostics")}
      </DialogTrigger>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-5xl">
        <DialogHeader>
          <DialogTitle>{t("diagnostics.title")}</DialogTitle>
          <DialogDescription>{t("diagnostics.description")}</DialogDescription>
        </DialogHeader>
        {error ? (
          <ErrorState message={error} />
        ) : !diagnostics ? (
          <PageSkeleton />
        ) : (
          <div className="space-y-4">
            <Card className="shadow-none">
              <CardContent className="grid gap-3 text-sm sm:grid-cols-3">
                <div>
                  <span className="text-muted-foreground">
                    {t("diagnostics.original")}
                  </span>
                  <div className="mt-1 font-medium" dir="auto">
                    {diagnostics.query?.original}
                  </div>
                </div>
                <div>
                  <span className="text-muted-foreground">
                    {t("diagnostics.completion")}
                  </span>
                  <div className="mt-1 font-medium" dir="ltr">
                    {diagnostics.connector_completion_order?.join(" → ") ?? "—"}
                  </div>
                </div>
                <div>
                  <span className="text-muted-foreground">
                    {t("diagnostics.normalized")}
                  </span>
                  <div className="mt-1 font-medium" dir="auto">
                    {diagnostics.query?.normalized}
                  </div>
                </div>
                <div>
                  <span className="text-muted-foreground">
                    {t("diagnostics.variants")}
                  </span>
                  <div className="mt-1" dir="auto">
                    {diagnostics.query?.variants.join(" · ")}
                  </div>
                </div>
              </CardContent>
            </Card>
            {diagnostics.mafer && (
              <Card className="shadow-none">
                <CardHeader>
                  <CardTitle>{t("diagnostics.planning")}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4 text-sm">
                  <div className="grid gap-3 sm:grid-cols-3">
                    <div>
                      <div className="text-xs text-muted-foreground">
                        {t("diagnostics.intent")}
                      </div>
                      <div className="mt-1 flex flex-wrap gap-1">
                        {diagnostics.mafer.intent_fingerprint?.labels.map(
                          (label) => (
                            <StatusBadge key={label} status={label} />
                          ),
                        )}
                      </div>
                    </div>
                    <div>
                      <div className="text-xs text-muted-foreground">
                        {t("diagnostics.temporalIntent")}
                      </div>
                      <div className="mt-1 font-mono text-xs" dir="ltr">
                        {diagnostics.mafer.temporal_intent ?? "—"}
                      </div>
                    </div>
                    <div>
                      <div className="text-xs text-muted-foreground">
                        {t("diagnostics.stopReason")}
                      </div>
                      <div className="mt-1 font-mono text-xs" dir="ltr">
                        {diagnostics.mafer.stop_reason ?? "—"}
                      </div>
                    </div>
                  </div>
                  {diagnostics.mafer.resource_plan?.resources.length ? (
                    <div>
                      <div className="mb-2 text-xs font-medium text-muted-foreground">
                        {t("diagnostics.resourceUtility")}
                      </div>
                      <div className="grid gap-2 sm:grid-cols-2">
                        {diagnostics.mafer.resource_plan.resources.map(
                          (resource) => (
                            <div
                              key={resource.source}
                              className="rounded-sm border px-2 py-1.5"
                            >
                              <div className="flex items-center justify-between gap-2">
                                <span className="font-medium">
                                  {resource.source}
                                </span>
                                <span className="tabular-nums text-xs text-muted-foreground">
                                  {t("diagnostics.longTermUtility")}{" "}
                                  {resource.long_term_utility}
                                  {" · "}
                                  {t("diagnostics.currentAvailability")}{" "}
                                  {resource.current_availability}
                                </span>
                              </div>
                              <div
                                className="mt-1 text-xs text-muted-foreground"
                                dir="auto"
                              >
                                {resource.reasons.join(" · ")}
                              </div>
                            </div>
                          ),
                        )}
                      </div>
                    </div>
                  ) : null}
                  <div>
                    <div className="mb-2 text-xs font-medium text-muted-foreground">
                      {t("diagnostics.variants")}
                    </div>
                    <div className="space-y-1">
                      {diagnostics.mafer.query_lattice?.variants.map(
                        (variant) => (
                          <div
                            key={variant.variant_id}
                            className="grid gap-1 rounded-sm border px-2 py-1.5 sm:grid-cols-[8rem_1fr_auto]"
                          >
                            <span className="font-mono text-[10px]" dir="ltr">
                              {variant.transformation}
                            </span>
                            <span dir="auto">{variant.text}</span>
                            <span className="tabular-nums text-muted-foreground">
                              {Math.round(variant.confidence * 100)}% · R
                              {variant.round_created}
                            </span>
                          </div>
                        ),
                      )}
                    </div>
                  </div>
                  <div>
                    <div className="mb-2 text-xs font-medium text-muted-foreground">
                      {t("diagnostics.searchRounds")}
                    </div>
                    <div className="space-y-1">
                      {diagnostics.mafer.rounds?.map((round) => (
                        <div
                          key={`${round.round}-${round.kind}`}
                          className="flex flex-wrap items-center justify-between gap-2 border-b py-1.5 last:border-0"
                        >
                          <span>
                            R{round.round} · {round.kind.replaceAll("_", " ")}
                          </span>
                          <span className="text-xs text-muted-foreground">
                            {round.sources?.join(", ") ??
                              t("diagnostics.localMemory")}
                            {round.uncertainty
                              ? ` · ${round.uncertainty.level}`
                              : ""}
                            {round.decision ? ` · ${round.decision}` : ""}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}
            <Card className="overflow-x-auto py-0 shadow-none">
              <Table aria-label={t("diagnostics.sourceFunnel")}>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t("result.source")}</TableHead>
                    <TableHead>{t("diagnostics.modeInstance")}</TableHead>
                    <TableHead>{t("history.status")}</TableHead>
                    <TableHead>HTTP</TableHead>
                    <TableHead className="text-end">
                      {t("sources.latency")}
                    </TableHead>
                    <TableHead className="text-end">
                      {t("diagnostics.fetched")}
                    </TableHead>
                    <TableHead className="text-end">
                      {t("diagnostics.valid")}
                    </TableHead>
                    <TableHead className="text-end">
                      {t("diagnostics.matching")}
                    </TableHead>
                    <TableHead className="text-end">
                      {t("diagnostics.normalizedResults")}
                    </TableHead>
                    <TableHead className="text-end">
                      {t("diagnostics.eligible")}
                    </TableHead>
                    <TableHead className="text-end">
                      {t("diagnostics.admitted")}
                    </TableHead>
                    <TableHead className="text-end">
                      {t("diagnostics.finalTop")}
                    </TableHead>
                    <TableHead className="text-end">
                      {t("diagnostics.malformed")}
                    </TableHead>
                    <TableHead className="text-end">
                      {t("diagnostics.attempts")}
                    </TableHead>
                    <TableHead>{t("diagnostics.circuit")}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {diagnostics.connectors?.map((connector, index) => (
                    <TableRow key={`${connector.source}-${index}`}>
                      <TableCell>{connector.source}</TableCell>
                      <TableCell className="min-w-48 text-xs">
                        <div className="font-medium">
                          {connector.mode?.replaceAll("_", " ") ?? "—"}
                        </div>
                        {connector.acquisition_mode && (
                          <div className="text-muted-foreground">
                            {t("result.acquisition")}:{" "}
                            {connector.acquisition_mode}
                            {connector.cache_state
                              ? ` · ${t("diagnostics.cache")}: ${connector.cache_state}`
                              : ""}
                          </div>
                        )}
                        {connector.instances?.map((instance) => (
                          <div
                            key={instance}
                            className="truncate font-mono text-[10px] text-muted-foreground"
                            dir="ltr"
                          >
                            {instance}
                          </div>
                        ))}
                        {connector.local_query_matches !== undefined && (
                          <div className="text-muted-foreground">
                            {t("diagnostics.localMatches")}:{" "}
                            {formatNumber(
                              connector.local_query_matches,
                              locale,
                            )}
                            {connector.duplicates
                              ? ` · ${t("diagnostics.duplicates")}: ${formatNumber(connector.duplicates, locale)}`
                              : ""}
                          </div>
                        )}
                        {connector.engine_telemetry?.map((engine) => (
                          <div
                            key={`${engine.engine}-${engine.query_variant_id}`}
                            className="mt-1 border-t pt-1 text-[10px] text-muted-foreground"
                          >
                            <span className="font-mono" dir="ltr">
                              {engine.engine}
                            </span>{" "}
                            · {engine.returned_result_count} /{" "}
                            {engine.accepted_canonical_result_count}
                            {engine.current_state
                              ? ` · ${engine.current_state}`
                              : ""}
                            {engine.error ? ` · ${engine.error}` : ""}
                          </div>
                        ))}
                      </TableCell>
                      <TableCell>
                        <StatusBadge status={connector.status} />
                      </TableCell>
                      <TableCell className="font-mono" dir="ltr">
                        {connector.http_status ?? "—"}
                      </TableCell>
                      <TableCell className="text-end tabular-nums">
                        {formatDuration(connector.latency_ms, locale)}
                      </TableCell>
                      <TableCell className="text-end tabular-nums">
                        {formatNumber(
                          connector.fetched_results ?? connector.raw_results,
                          locale,
                        )}
                      </TableCell>
                      <TableCell className="text-end tabular-nums">
                        {formatNumber(
                          connector.schema_valid_results ?? 0,
                          locale,
                        )}
                      </TableCell>
                      <TableCell className="text-end tabular-nums">
                        {formatNumber(
                          connector.query_matching_results ?? 0,
                          locale,
                        )}
                      </TableCell>
                      <TableCell className="text-end tabular-nums">
                        {formatNumber(connector.normalized_results, locale)}
                      </TableCell>
                      <TableCell className="text-end tabular-nums">
                        {formatNumber(
                          connector.final_matching_results ?? 0,
                          locale,
                        )}
                      </TableCell>
                      <TableCell className="text-end tabular-nums">
                        {formatNumber(
                          connector.candidate_admitted_results ??
                            connector.collected_results ??
                            0,
                          locale,
                        )}
                      </TableCell>
                      <TableCell className="text-end tabular-nums">
                        {formatNumber(connector.final_top_results ?? 0, locale)}
                      </TableCell>
                      <TableCell className="text-end tabular-nums">
                        {formatNumber(connector.malformed_records, locale)}
                      </TableCell>
                      <TableCell className="text-end tabular-nums">
                        {formatNumber(connector.attempt_count ?? 0, locale)}
                      </TableCell>
                      <TableCell>
                        {connector.circuit_breaker_state ?? "closed"}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Card>
            {diagnostics.acquisition_funnel?.length ? (
              <Card className="overflow-x-auto py-0 shadow-none">
                <CardHeader>
                  <CardTitle>{t("diagnostics.acquisitionFunnel")}</CardTitle>
                </CardHeader>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t("result.platform")}</TableHead>
                      <TableHead>{t("result.acquiredThrough")}</TableHead>
                      <TableHead>{t("diagnostics.connectorExecuted")}</TableHead>
                      <TableHead className="text-end">{t("diagnostics.attempts")}</TableHead>
                      <TableHead className="text-end">{t("diagnostics.fetched")}</TableHead>
                      <TableHead className="text-end">{t("diagnostics.matching")}</TableHead>
                      <TableHead className="text-end">{t("diagnostics.admitted")}</TableHead>
                      <TableHead className="text-end">{t("diagnostics.finalTop")}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {diagnostics.acquisition_funnel.map((row) => (
                      <TableRow key={`${row.platform}-${row.acquisition_path}`}>
                        <TableCell dir="ltr">{row.platform}</TableCell>
                        <TableCell className={row.acquisition_path === "LOCAL_MEMORY" ? "font-medium text-[var(--status-memory)]" : undefined}>
                          {row.acquisition_path.replaceAll("_", " ")}
                        </TableCell>
                        <TableCell>{row.connector_executed ? t("common.yes") : t("common.no")}</TableCell>
                        <TableCell className="text-end tabular-nums">{formatNumber(row.network_requests, locale)}</TableCell>
                        <TableCell className="text-end tabular-nums">{formatNumber(row.retrieved, locale)}</TableCell>
                        <TableCell className="text-end tabular-nums">{formatNumber(row.matched, locale)}</TableCell>
                        <TableCell className="text-end tabular-nums">{formatNumber(row.admitted, locale)}</TableCell>
                        <TableCell className="text-end tabular-nums">{formatNumber(row.final_top_k, locale)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </Card>
            ) : null}
            <div className="grid gap-4 lg:grid-cols-2">
              <Card className="shadow-none">
                <CardHeader>
                  <CardTitle>{t("diagnostics.phase")}</CardTitle>
                </CardHeader>
                <CardContent>
                  {Object.entries(diagnostics.phase_timings_ms ?? {}).map(
                    ([phase, value]) => (
                      <div
                        key={phase}
                        className="flex justify-between border-b py-2 text-sm last:border-0"
                      >
                        <span>{phase.replaceAll("_", " ")}</span>
                        <span className="tabular-nums">
                          {formatDuration(value, locale)}
                        </span>
                      </div>
                    ),
                  )}
                </CardContent>
              </Card>
              <Card className="shadow-none">
                <CardHeader>
                  <CardTitle>{t("diagnostics.scores")}</CardTitle>
                </CardHeader>
                <CardContent>
                  {Object.entries(
                    diagnostics.score_component_distributions ?? {},
                  ).map(([signal, values]) => (
                    <div
                      key={signal}
                      className="border-b py-2 text-sm last:border-0"
                    >
                      <div className="mb-1 font-medium">
                        {signal.replaceAll("_", " ")}
                      </div>
                      <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                        {Object.entries(values).map(([bucket, count]) => (
                          <span key={bucket}>
                            {bucket}: {formatNumber(count, locale)}
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
                </CardContent>
              </Card>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
