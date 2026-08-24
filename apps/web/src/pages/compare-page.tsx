import { AlertTriangle, GitCompareArrows } from "lucide-react";
import { useEffect, useState } from "react";
import { CartesianGrid, Line, LineChart, XAxis, YAxis } from "recharts";

import {
  EmptyState,
  ErrorState,
  PageHeader,
  PageSkeleton,
} from "@/components/shared/page";
import { Alert, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { api } from "@/lib/api";
import { formatDate, formatNumber } from "@/lib/format";
import { useI18n } from "@/lib/i18n";
import type { CompareResponse, SearchSummary } from "@/types/api";

const compareConfig = {
  left: { label: "First search", color: "var(--chart-1)" },
  right: { label: "Second search", color: "var(--chart-2)" },
} satisfies ChartConfig;

export function ComparePage() {
  const { locale, t } = useI18n();
  const [history, setHistory] = useState<SearchSummary[]>([]);
  const [left, setLeft] = useState("");
  const [right, setRight] = useState("");
  const [comparison, setComparison] = useState<CompareResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .getHistory()
      .then((items) => {
        setHistory(items);
        setLeft(items[0]?.id ?? "");
        setRight(items[1]?.id ?? "");
      })
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setLoading(false));
  }, []);

  const compare = async () => {
    if (!left || !right || left === right) return;
    setLoading(true);
    setError("");
    try {
      setComparison(await api.compare(left, right));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t("state.error"));
    } finally {
      setLoading(false);
    }
  };

  const timeline =
    comparison?.left_analytics.mentions_over_time.map((point, index) => ({
      timestamp: new Intl.DateTimeFormat(locale === "ar" ? "ar-IQ" : "en-GB", {
        hour: "2-digit",
        minute: "2-digit",
      }).format(new Date(point.timestamp)),
      left: point.count,
      right: comparison.right_analytics.mentions_over_time[index]?.count ?? 0,
    })) ?? [];
  const comparisonSides = comparison
    ? [
        {
          side: "left",
          summary: comparison.left,
          analytics: comparison.left_analytics,
        },
        {
          side: "right",
          summary: comparison.right,
          analytics: comparison.right_analytics,
        },
      ]
    : [];

  return (
    <div className="instrument-page instrument-page--compare">
      <PageHeader
        title={t("compare.title")}
        description={t("compare.description")}
      />
      {loading && history.length === 0 ? (
        <PageSkeleton />
      ) : error ? (
        <ErrorState message={error} />
      ) : history.length < 2 ? (
        <EmptyState description={t("compare.empty")} />
      ) : (
        <>
          <Card className="compare-control-plane mb-4 shadow-none">
            <CardContent className="flex flex-col gap-3 md:flex-row md:items-end">
              <label className="flex-1 space-y-1.5 text-sm">
                <span>{t("compare.left")}</span>
                <Select
                  value={left}
                  onValueChange={(value) => setLeft(value ?? "")}
                >
                  <SelectTrigger
                    className="w-full"
                    aria-label={t("compare.left")}
                  >
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {history.map((item) => (
                      <SelectItem key={item.id} value={item.id}>
                        {item.original_query} ·{" "}
                        {formatDate(item.started_at, locale)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </label>
              <label className="flex-1 space-y-1.5 text-sm">
                <span>{t("compare.right")}</span>
                <Select
                  value={right}
                  onValueChange={(value) => setRight(value ?? "")}
                >
                  <SelectTrigger
                    className="w-full"
                    aria-label={t("compare.right")}
                  >
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {history.map((item) => (
                      <SelectItem key={item.id} value={item.id}>
                        {item.original_query} ·{" "}
                        {formatDate(item.started_at, locale)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </label>
              <Button
                onClick={compare}
                disabled={!left || !right || left === right || loading}
              >
                <GitCompareArrows />
                {t("compare.run")}
              </Button>
            </CardContent>
          </Card>
          {!comparison && !loading && (
            <EmptyState title={t("compare.title")} description={t("compare.empty")} />
          )}
          {comparison && (
            <div className="compare-plane">
              {comparison.collection_window_warning && (
                <Alert className="border-chart-2/50 bg-chart-2/5">
                  <AlertTriangle />
                  <AlertTitle>{t("compare.windowWarning")}</AlertTitle>
                </Alert>
              )}
              <div className="compare-plane__subjects grid gap-4 lg:grid-cols-2">
                {comparisonSides.map(({ side, summary, analytics }) => (
                  <Card key={side} className="shadow-none">
                    <CardHeader>
                      <CardTitle>{summary.original_query}</CardTitle>
                      <p className="text-xs text-muted-foreground">
                        {t("clusters.window")}:{" "}
                        {formatDate(summary.started_at, locale)} –{" "}
                        {formatDate(summary.completed_at, locale)}
                      </p>
                    </CardHeader>
                    <CardContent className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                      {[
                        [t("analytics.total"), analytics.total_results],
                        [t("analytics.sources"), analytics.source_count],
                        [t("analytics.average"), analytics.average_score],
                        [
                          t("analytics.trend"),
                          `${analytics.trend_percent >= 0 ? "+" : ""}${analytics.trend_percent}%`,
                        ],
                      ].map(([label, value]) => (
                        <div key={String(label)}>
                          <div className="text-xs text-muted-foreground">
                            {label}
                          </div>
                          <div className="mt-1 text-xl font-semibold tabular-nums">
                            {typeof value === "number"
                              ? formatNumber(value, locale, 1)
                              : value}
                          </div>
                        </div>
                      ))}
                    </CardContent>
                  </Card>
                ))}
              </div>
              <Card className="compare-plane__timeline shadow-none">
                <CardHeader>
                  <CardTitle>{t("analytics.mentions")}</CardTitle>
                </CardHeader>
                <CardContent>
                  <ChartContainer
                    config={compareConfig}
                    className="h-64 w-full aspect-auto"
                  >
                    <LineChart data={timeline}>
                      <CartesianGrid vertical={false} />
                      <XAxis
                        dataKey="timestamp"
                        tickLine={false}
                        axisLine={false}
                        minTickGap={30}
                      />
                      <YAxis
                        allowDecimals={false}
                        tickLine={false}
                        axisLine={false}
                        width={28}
                      />
                      <ChartTooltip content={<ChartTooltipContent />} />
                      <Line
                        dataKey="left"
                        stroke="var(--color-left)"
                        strokeWidth={2}
                        dot={false}
                      />
                      <Line
                        dataKey="right"
                        stroke="var(--color-right)"
                        strokeWidth={2}
                        dot={false}
                      />
                    </LineChart>
                  </ChartContainer>
                </CardContent>
              </Card>
              <div className="compare-plane__distributions grid gap-4 lg:grid-cols-2">
                {[comparison.left_analytics, comparison.right_analytics].map(
                  (analytics, index) => (
                    <Card key={index} className="shadow-none">
                      <CardHeader>
                        <CardTitle>
                          {index === 0
                            ? comparison.left.original_query
                            : comparison.right.original_query}{" "}
                          · {t("analytics.platforms")}
                        </CardTitle>
                      </CardHeader>
                      <CardContent className="space-y-2">
                        {Object.entries(analytics.platform_distribution).map(
                          ([source, count]) => (
                            <div
                              className="flex justify-between border-b py-1.5 text-sm last:border-0"
                              key={source}
                            >
                              <span>{source}</span>
                              <span className="tabular-nums">{count}</span>
                            </div>
                          ),
                        )}
                        <div className="flex flex-wrap gap-1 border-t pt-3">
                          {analytics.top_related_terms
                            .slice(0, 8)
                            .map((term) => (
                              <span
                                key={term.term}
                                className="rounded-md bg-muted px-2 py-1 text-xs"
                              >
                                {term.term} · {term.count}
                              </span>
                            ))}
                        </div>
                      </CardContent>
                    </Card>
                  ),
                )}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
