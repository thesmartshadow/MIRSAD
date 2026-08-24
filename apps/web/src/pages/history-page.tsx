import { ExternalLink, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import {
  EmptyState,
  ErrorState,
  PageHeader,
  PageSkeleton,
  StatusBadge,
} from "@/components/shared/page";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { formatDate, formatDuration, formatNumber } from "@/lib/format";
import { useI18n } from "@/lib/i18n";
import type { SearchSummary } from "@/types/api";

export function HistoryPage() {
  const { locale, t } = useI18n();
  const navigate = useNavigate();
  const [history, setHistory] = useState<SearchSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = () => {
    setLoading(true);
    setError("");
    api
      .getHistory()
      .then(setHistory)
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setLoading(false));
  };
  useEffect(load, []);

  return (
    <div className="instrument-page instrument-page--history">
      <PageHeader
        title={t("history.title")}
        description={t("history.description")}
        actions={
          <Button variant="outline" size="sm" onClick={load}>
            <RefreshCw />
            {t("action.refresh")}
          </Button>
        }
      />
      {loading ? (
        <PageSkeleton rows={6} />
      ) : error ? (
        <ErrorState message={error} onRetry={load} />
      ) : history.length === 0 ? (
        <EmptyState />
      ) : (
        <ol className="history-ledger">
          {history.map((session, index) => (
            <li key={session.id} className="history-ledger__row">
              <div className="history-ledger__index" aria-hidden="true">
                {String(index + 1).padStart(2, "0")}
              </div>
              <div className="history-ledger__query">
                <strong dir="auto">{session.original_query}</strong>
                <span dir="auto">{session.normalized_query}</span>
              </div>
              <time>{formatDate(session.started_at, locale)}</time>
              <div className="history-ledger__sources" dir="ltr">
                {session.sources.join(" · ")}
              </div>
              <StatusBadge status={session.status} />
              <dl>
                <div><dt>{t("history.results")}</dt><dd>{formatNumber(session.result_count, locale)}</dd></div>
                <div><dt>{t("history.unique")}</dt><dd>{formatNumber(session.unique_count, locale)}</dd></div>
                <div><dt>{t("history.duration")}</dt><dd>{formatDuration(session.duration_ms, locale)}</dd></div>
              </dl>
              <Button
                variant="ghost"
                size="icon-sm"
                aria-label={t("action.open")}
                onClick={() => navigate(`/search/${session.id}`)}
              >
                <ExternalLink />
              </Button>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
