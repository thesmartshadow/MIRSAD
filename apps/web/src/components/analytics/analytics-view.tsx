import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  XAxis,
  YAxis,
} from "recharts";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";
import { formatDuration, formatNumber } from "@/lib/format";
import { useI18n } from "@/lib/i18n";
import type { AnalyticsSnapshot } from "@/types/api";

function MetricCard({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail?: string;
}) {
  return (
    <Card className="shadow-none">
      <CardContent className="py-3">
        <div className="text-xs text-muted-foreground">{label}</div>
        <div className="mt-1 font-heading text-2xl font-semibold tabular-nums">
          {value}
        </div>
        {detail && (
          <div className="mt-1 text-xs text-muted-foreground">{detail}</div>
        )}
      </CardContent>
    </Card>
  );
}

export function AnalyticsView({ analytics }: { analytics: AnalyticsSnapshot }) {
  const { locale, t } = useI18n();
  const globalScope = analytics.scope && analytics.scope !== "session";
  const chartConfig = {
    count: { label: t("analytics.total"), color: "var(--chart-1)" },
    value: { label: t("analytics.total"), color: "var(--chart-3)" },
  } satisfies ChartConfig;
  const timeline = analytics.mentions_over_time.map((point) => ({
    ...point,
    label: new Intl.DateTimeFormat(locale === "ar" ? "ar-IQ" : "en-GB", {
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(point.timestamp)),
  }));
  const platforms = Object.entries(analytics.platform_distribution).map(
    ([source, value]) => ({ source, value }),
  );
  const socialTimeline = (analytics.social_mentions_over_time ?? []).map(
    (point) => ({
      ...point,
      label: new Intl.DateTimeFormat(locale === "ar" ? "ar-IQ" : "en-GB", {
        hour: "2-digit",
        minute: "2-digit",
      }).format(new Date(point.timestamp)),
    }),
  );
  const socialPlatforms = Object.entries(
    analytics.social_source_distribution ?? {},
  ).map(([source, value]) => ({ source, value }));
  const categories = Object.entries(analytics.category_distribution ?? {}).map(
    ([source, value]) => ({ source, value }),
  );
  const languages = Object.entries(analytics.language_distribution).map(
    ([language, value], index) => ({
      language,
      value,
      fill: `var(--chart-${(index % 5) + 1})`,
    }),
  );
  const scores = Object.entries(analytics.score_distribution).map(
    ([range, count]) => ({ range, count }),
  );
  const publication = Object.entries(
    analytics.publication_time_distribution ?? {},
  ).map(([range, count]) => ({ range: range.replaceAll("_", " "), count }));
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
        <MetricCard
          label={globalScope ? t("analytics.contentRecords") : t("analytics.total")}
          value={formatNumber(analytics.total_results, locale)}
        />
        <MetricCard
          label={globalScope ? t("analytics.canonicalRecords") : t("analytics.unique")}
          value={formatNumber(analytics.unique_results, locale)}
        />
        {globalScope && analytics.search_appearance_count != null && (
          <MetricCard
            label={t("analytics.searchAppearances")}
            value={formatNumber(analytics.search_appearance_count, locale)}
          />
        )}
        <MetricCard
          label={t("analytics.sources")}
          value={formatNumber(analytics.source_count, locale)}
        />
        <MetricCard
          label={globalScope ? t("analytics.duplicateGroups") : t("analytics.duplicates")}
          value={formatNumber(
            globalScope
              ? (analytics.duplicate_group_count ?? 0)
              : analytics.duplicate_count,
            locale,
          )}
        />
        <MetricCard
          label={t("analytics.average")}
          value={formatNumber(analytics.average_score, locale, 1)}
        />
        <MetricCard
          label={globalScope ? t("analytics.averageDuration") : t("analytics.duration")}
          value={formatDuration(analytics.search_duration_ms, locale)}
          detail={`${analytics.trend_percent >= 0 ? "+" : ""}${formatNumber(analytics.trend_percent, locale, 1)}% ${t("analytics.trend")}`}
        />
        {(analytics.platform_diversity ?? 0) > 0 && (
          <MetricCard
            label={t("analytics.platformDiversity")}
            value={formatNumber(analytics.platform_diversity, locale)}
          />
        )}
        {analytics.average_social_reach != null && (
          <MetricCard
            label={t("analytics.socialReach")}
            value={formatNumber(analytics.average_social_reach, locale, 1)}
          />
        )}
      </div>
      <div className="grid gap-4 xl:grid-cols-3">
        <Card className="shadow-none xl:col-span-2">
          <CardHeader>
            <CardTitle>{t("analytics.mentions")}</CardTitle>
          </CardHeader>
          <CardContent>
            {timeline.some((point) => point.count > 0) ? (
              <ChartContainer
                config={chartConfig}
                className="h-64 w-full aspect-auto"
              >
                <LineChart data={timeline} margin={{ left: 4, right: 12 }}>
                  <CartesianGrid vertical={false} />
                  <XAxis
                    dataKey="label"
                    tickLine={false}
                    axisLine={false}
                    minTickGap={32}
                  />
                  <YAxis
                    allowDecimals={false}
                    tickLine={false}
                    axisLine={false}
                    width={28}
                  />
                  <ChartTooltip content={<ChartTooltipContent hideLabel />} />
                  <Line
                    type="monotone"
                    dataKey="count"
                    stroke="var(--color-count)"
                    strokeWidth={2}
                    dot={false}
                  />
                </LineChart>
              </ChartContainer>
            ) : (
              <ChartEmpty />
            )}
          </CardContent>
        </Card>
        <Card className="shadow-none">
          <CardHeader>
            <CardTitle>{t("analytics.languages")}</CardTitle>
          </CardHeader>
          <CardContent>
            {languages.length > 0 ? (
              <ChartContainer
                config={chartConfig}
                className="h-64 w-full aspect-auto"
              >
                <PieChart>
                  <ChartTooltip
                    content={<ChartTooltipContent nameKey="language" />}
                  />
                  <Pie
                    data={languages}
                    dataKey="value"
                    nameKey="language"
                    innerRadius={48}
                    outerRadius={82}
                    paddingAngle={2}
                  >
                    {languages.map((entry) => (
                      <Cell key={entry.language} fill={entry.fill} />
                    ))}
                  </Pie>
                  <ChartLegend
                    content={<ChartLegendContent nameKey="language" />}
                  />
                </PieChart>
              </ChartContainer>
            ) : (
              <ChartEmpty />
            )}
          </CardContent>
        </Card>
      </div>
      <div className="grid gap-4 xl:grid-cols-2">
        <Card className="shadow-none">
          <CardHeader>
            <CardTitle>{t("analytics.platforms")}</CardTitle>
          </CardHeader>
          <CardContent>
            {platforms.length > 0 ? (
              <ChartContainer
                config={chartConfig}
                className="h-64 w-full aspect-auto"
              >
                <BarChart
                  data={platforms}
                  layout="vertical"
                  margin={{ left: 18 }}
                >
                  <CartesianGrid horizontal={false} />
                  <XAxis type="number" allowDecimals={false} hide />
                  <YAxis
                    type="category"
                    dataKey="source"
                    tickLine={false}
                    axisLine={false}
                    width={90}
                  />
                  <ChartTooltip content={<ChartTooltipContent />} />
                  <Bar dataKey="value" fill="var(--color-value)" radius={3} />
                </BarChart>
              </ChartContainer>
            ) : (
              <ChartEmpty />
            )}
          </CardContent>
        </Card>
        <Card className="shadow-none">
          <CardHeader>
            <CardTitle>{t("analytics.scores")}</CardTitle>
          </CardHeader>
          <CardContent>
            {scores.length > 0 ? (
              <ChartContainer
                config={chartConfig}
                className="h-64 w-full aspect-auto"
              >
                <BarChart data={scores}>
                  <CartesianGrid vertical={false} />
                  <XAxis dataKey="range" tickLine={false} axisLine={false} />
                  <YAxis
                    allowDecimals={false}
                    tickLine={false}
                    axisLine={false}
                    width={28}
                  />
                  <ChartTooltip content={<ChartTooltipContent />} />
                  <Bar dataKey="count" fill="var(--color-count)" radius={3} />
                </BarChart>
              </ChartContainer>
            ) : (
              <ChartEmpty />
            )}
          </CardContent>
        </Card>
      </div>
      {(socialTimeline.length > 0 || socialPlatforms.length > 0) && (
        <div className="grid gap-4 xl:grid-cols-2">
          <Card className="shadow-none">
            <CardHeader>
              <CardTitle>{t("analytics.socialMentions")}</CardTitle>
            </CardHeader>
            <CardContent>
              {socialTimeline.some((point) => point.count > 0) ? (
                <ChartContainer
                  config={chartConfig}
                  className="h-64 w-full aspect-auto"
                >
                  <LineChart
                    data={socialTimeline}
                    margin={{ left: 4, right: 12 }}
                  >
                    <CartesianGrid vertical={false} />
                    <XAxis
                      dataKey="label"
                      tickLine={false}
                      axisLine={false}
                      minTickGap={32}
                    />
                    <YAxis
                      allowDecimals={false}
                      tickLine={false}
                      axisLine={false}
                      width={28}
                    />
                    <ChartTooltip content={<ChartTooltipContent hideLabel />} />
                    <Line
                      type="monotone"
                      dataKey="count"
                      stroke="var(--color-count)"
                      strokeWidth={2}
                      dot={false}
                    />
                  </LineChart>
                </ChartContainer>
              ) : (
                <ChartEmpty />
              )}
            </CardContent>
          </Card>
          <Card className="shadow-none">
            <CardHeader>
              <CardTitle>{t("analytics.socialPlatforms")}</CardTitle>
            </CardHeader>
            <CardContent>
              {socialPlatforms.length > 0 ? (
                <ChartContainer
                  config={chartConfig}
                  className="h-64 w-full aspect-auto"
                >
                  <BarChart
                    data={socialPlatforms}
                    layout="vertical"
                    margin={{ left: 18 }}
                  >
                    <CartesianGrid horizontal={false} />
                    <XAxis type="number" allowDecimals={false} hide />
                    <YAxis
                      type="category"
                      dataKey="source"
                      tickLine={false}
                      axisLine={false}
                      width={90}
                    />
                    <ChartTooltip content={<ChartTooltipContent />} />
                    <Bar dataKey="value" fill="var(--color-value)" radius={3} />
                  </BarChart>
                </ChartContainer>
              ) : (
                <ChartEmpty />
              )}
            </CardContent>
          </Card>
        </div>
      )}
      {(analytics.top_hashtags?.length > 0 ||
        analytics.top_mentioned_accounts?.length > 0) && (
        <div className="grid gap-4 xl:grid-cols-3">
          <Card className="shadow-none">
            <CardHeader>
              <CardTitle>{t("analytics.hashtags")}</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              {(analytics.top_hashtags ?? []).map((item) => (
                <Badge key={item.term} variant="secondary">
                  #{item.term} · {formatNumber(item.count, locale)}
                </Badge>
              ))}
            </CardContent>
          </Card>
          <Card className="shadow-none">
            <CardHeader>
              <CardTitle>{t("analytics.accounts")}</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              {(analytics.top_mentioned_accounts ?? []).map((item) => (
                <Badge key={item.term} variant="outline">
                  @{item.term} · {formatNumber(item.count, locale)}
                </Badge>
              ))}
            </CardContent>
          </Card>
          <Card className="shadow-none">
            <CardHeader>
              <CardTitle>{t("analytics.categories")}</CardTitle>
            </CardHeader>
            <CardContent>
              {categories.length > 0 ? (
                <ChartContainer
                  config={chartConfig}
                  className="h-48 w-full aspect-auto"
                >
                  <BarChart data={categories}>
                    <CartesianGrid vertical={false} />
                    <XAxis dataKey="source" tickLine={false} axisLine={false} />
                    <YAxis
                      allowDecimals={false}
                      tickLine={false}
                      axisLine={false}
                      width={28}
                    />
                    <ChartTooltip content={<ChartTooltipContent />} />
                    <Bar dataKey="value" fill="var(--color-value)" radius={3} />
                  </BarChart>
                </ChartContainer>
              ) : (
                <ChartEmpty />
              )}
            </CardContent>
          </Card>
        </div>
      )}
      <div className="grid gap-4 xl:grid-cols-2">
        <Card className="shadow-none">
          <CardHeader>
            <CardTitle>{t("analytics.terms")}</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            {analytics.top_related_terms.length === 0 ? (
              <ChartEmpty />
            ) : (
              analytics.top_related_terms.map((item, index) => (
                <span
                  key={item.term}
                  className="inline-flex items-center gap-2 rounded-md border px-2.5 py-1.5 text-sm"
                  style={{
                    fontSize: `${Math.max(0.75, 1.05 - index * 0.025)}rem`,
                  }}
                >
                  {item.term}
                  <span className="text-xs tabular-nums text-muted-foreground">
                    {formatNumber(item.count, locale)}
                  </span>
                </span>
              ))
            )}
          </CardContent>
        </Card>
        <Card className="shadow-none">
          <CardHeader>
            <CardTitle>{t("analytics.clusterDistribution")}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {Object.keys(analytics.cluster_distribution).length === 0 ? (
              <ChartEmpty />
            ) : (
              Object.entries(analytics.cluster_distribution).map(
                ([size, count]) => (
                  <div
                    key={size}
                    className="flex items-center justify-between border-b py-2 text-sm last:border-0"
                  >
                    <span>
                      {size} {t("clusters.members")}
                    </span>
                    <span className="font-medium tabular-nums">
                      {formatNumber(count, locale)}
                    </span>
                  </div>
                ),
              )
            )}
          </CardContent>
        </Card>
      </div>
      <Card className="shadow-none">
        <CardHeader>
          <CardTitle>{t("analytics.publication")}</CardTitle>
        </CardHeader>
        <CardContent>
          {publication.length > 0 ? (
            <ChartContainer
              config={chartConfig}
              className="h-56 w-full aspect-auto"
            >
              <BarChart data={publication}>
                <CartesianGrid vertical={false} />
                <XAxis dataKey="range" tickLine={false} axisLine={false} />
                <YAxis
                  allowDecimals={false}
                  tickLine={false}
                  axisLine={false}
                  width={28}
                />
                <ChartTooltip content={<ChartTooltipContent />} />
                <Bar dataKey="count" fill="var(--color-count)" radius={3} />
              </BarChart>
            </ChartContainer>
          ) : (
            <ChartEmpty />
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function ChartEmpty() {
  const { t } = useI18n();
  return (
    <div className="flex h-40 items-center justify-center text-sm text-muted-foreground">
      {t("state.noData")}
    </div>
  );
}
