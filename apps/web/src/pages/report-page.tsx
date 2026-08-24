import { Printer } from "lucide-react";
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { ErrorState, PageSkeleton } from "@/components/shared/page";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { api } from "@/lib/api";
import { displayText } from "@/lib/external-content";
import { formatDate, formatDuration, formatNumber } from "@/lib/format";
import { useI18n } from "@/lib/i18n";
import type { SearchResponse } from "@/types/api";

export function ReportPage() {
  const { sessionId = "" } = useParams();
  const { locale, t } = useI18n();
  const [data, setData] = useState<SearchResponse | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    api
      .getSearch(sessionId)
      .then(setData)
      .catch((reason: Error) => setError(reason.message));
  }, [sessionId]);
  if (error) return <ErrorState message={error} />;
  if (!data) return <PageSkeleton />;
  return (
    <article className="instrument-page instrument-page--report print-report mx-auto max-w-5xl bg-background">
      <div className="print-hidden mb-4 flex justify-end">
        <Button onClick={() => window.print()}>
          <Printer />
          {t("action.print")}
        </Button>
      </div>
      <header className="border-b pb-5">
        <div className="text-xs font-semibold tracking-[0.18em]">MIRSAD</div>
        <h2 className="mt-2 text-2xl font-semibold" dir="auto">
          {data.session.original_query}
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          {formatDate(data.session.completed_at, locale)} ·{" "}
          {formatDuration(data.session.duration_ms, locale)}
        </p>
      </header>
      <section className="grid grid-cols-2 gap-3 border-b py-5 md:grid-cols-4">
        <ReportMetric
          label={t("analytics.total")}
          value={formatNumber(data.session.result_count, locale)}
        />
        <ReportMetric
          label={t("analytics.unique")}
          value={formatNumber(data.session.unique_count, locale)}
        />
        <ReportMetric
          label={t("analytics.sources")}
          value={formatNumber(data.analytics.source_count, locale)}
        />
        <ReportMetric
          label={t("analytics.duplicates")}
          value={formatNumber(data.analytics.duplicate_count, locale)}
        />
      </section>
      <section className="py-5">
        <h3 className="mb-3 text-sm font-semibold">
          {t("saved.configuration")}
        </h3>
        <div className="grid gap-2 text-sm sm:grid-cols-2">
          <div>
            {t("search.sources")}: {data.session.sources.join(", ")}
          </div>
          <div>
            {t("history.status")}: {data.session.status}
          </div>
          <div>
            {t("search.timestamp")}:{" "}
            {formatDate(data.session.started_at, locale)}
          </div>
          <div>
            {t("analytics.average")}:{" "}
            {formatNumber(data.analytics.average_score, locale, 1)}
          </div>
        </div>
      </section>
      <Separator />
      <section className="grid gap-6 py-5 md:grid-cols-2">
        <div>
          <h3 className="mb-3 text-sm font-semibold">
            {t("analytics.platforms")}
          </h3>
          {Object.entries(data.analytics.platform_distribution).map(
            ([source, count]) => (
              <div
                key={source}
                className="flex justify-between border-b py-1.5 text-sm"
              >
                <span>{source}</span>
                <span>{formatNumber(count, locale)}</span>
              </div>
            ),
          )}
        </div>
        <div>
          <h3 className="mb-3 text-sm font-semibold">
            {t("analytics.mentions")}
          </h3>
          {data.analytics.mentions_over_time
            .filter((point) => point.count > 0)
            .map((point) => (
              <div
                key={point.timestamp}
                className="flex justify-between border-b py-1.5 text-xs"
              >
                <span>{formatDate(point.timestamp, locale)}</span>
                <span>{formatNumber(point.count, locale)}</span>
              </div>
            ))}
        </div>
      </section>
      <Separator />
      <section className="py-5">
        <h3 className="mb-3 text-sm font-semibold">{t("search.results")}</h3>
        <ol className="space-y-3">
          {data.results.slice(0, 20).map((item, index) => (
            <li key={item.id} className="break-inside-avoid border-b pb-3">
              <div className="flex justify-between gap-4">
                <strong className="text-sm" dir="auto">
                  {index + 1}. {displayText(item.title) || t("result.untitled")}
                </strong>
                <span className="tabular-nums">
                  {formatNumber(item.score, locale, 1)}
                </span>
              </div>
              <p
                className="mt-1 line-clamp-3 text-xs text-muted-foreground"
                dir="auto"
              >
                {displayText(item.text)}
              </p>
              <div className="mt-1 text-[11px]">
                {item.source} · {formatDate(item.published_at, locale)}
              </div>
            </li>
          ))}
        </ol>
      </section>
      <footer className="border-t pt-3 text-xs text-muted-foreground">
        {new Date().toLocaleString(locale === "ar" ? "ar-IQ" : "en-GB")}
      </footer>
    </article>
  );
}

function ReportMetric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-1 text-xl font-semibold tabular-nums">{value}</div>
    </div>
  );
}
