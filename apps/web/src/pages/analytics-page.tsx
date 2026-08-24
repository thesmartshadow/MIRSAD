import { AnalyticsView } from "@/components/analytics/analytics-view";
import { ErrorState, PageHeader, PageSkeleton } from "@/components/shared/page";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { useI18n } from "@/lib/i18n";
import { useSearchState } from "@/lib/search-state";
import type { AnalyticsSnapshot } from "@/types/api";
import { useEffect, useRef, useState } from "react";

type AnalyticsScope = "all" | "session" | "24h" | "7d" | "30d";

export function AnalyticsPage() {
  const { locale, t } = useI18n();
  const { currentSearch } = useSearchState();
  const [scope, setScope] = useState<AnalyticsScope>("all");
  const [analytics, setAnalytics] = useState<AnalyticsSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const requestGeneration = useRef(0);

  useEffect(() => {
    const controller = new AbortController();
    const generation = ++requestGeneration.current;
    setLoading(true);
    setError("");
    api
      .getAnalytics(scope, currentSearch?.session.id, controller.signal)
      .then((value) => {
        if (generation === requestGeneration.current) setAnalytics(value);
      })
      .catch((reason: Error) => {
        if (reason.name !== "AbortError" && generation === requestGeneration.current)
          setError(reason.message);
      })
      .finally(() => {
        if (generation === requestGeneration.current) setLoading(false);
      });
    return () => controller.abort();
  }, [currentSearch?.session.id, scope]);

  const scopeLabel =
    analytics?.scope === "session"
      ? `${t("analytics.scopeSessionLabel")} ${analytics.scope_query ?? ""} · ${formatDate(analytics.scope_started_at ?? null, locale)}`
      : t(`analytics.scope.${scope === "session" ? "all" : scope}`);
  return (
    <div className="instrument-page instrument-page--analytics">
      <PageHeader
        title={t("analytics.title")}
        description={t("analytics.description")}
      />
      <section className="analytics-scope-strip">
          <div>
            <Label htmlFor="analytics-scope">{t("analytics.scopeLabel")}</Label>
            <p className="mt-1 text-xs text-muted-foreground">{scopeLabel}</p>
          </div>
          <Select
            value={scope}
            onValueChange={(value) => setScope(value as AnalyticsScope)}
          >
            <SelectTrigger id="analytics-scope" className="w-full sm:w-64">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t("analytics.scope.all")}</SelectItem>
              {currentSearch && (
                <SelectItem value="session">
                  {t("analytics.scope.session")}
                </SelectItem>
              )}
              <SelectItem value="24h">{t("analytics.scope.24h")}</SelectItem>
              <SelectItem value="7d">{t("analytics.scope.7d")}</SelectItem>
              <SelectItem value="30d">{t("analytics.scope.30d")}</SelectItem>
            </SelectContent>
          </Select>
      </section>
      {loading && !analytics ? (
        <PageSkeleton rows={5} />
      ) : error ? (
        <ErrorState message={error} />
      ) : analytics ? (
        <AnalyticsView analytics={analytics} />
      ) : null}
    </div>
  );
}
