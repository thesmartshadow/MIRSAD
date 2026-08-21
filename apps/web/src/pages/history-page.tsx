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
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
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
    <div>
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
        <Card className="overflow-hidden py-0 shadow-none">
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("history.query")}</TableHead>
                  <TableHead>{t("history.normalized")}</TableHead>
                  <TableHead>{t("history.date")}</TableHead>
                  <TableHead>{t("history.status")}</TableHead>
                  <TableHead>{t("history.sources")}</TableHead>
                  <TableHead className="text-end">
                    {t("history.results")}
                  </TableHead>
                  <TableHead className="text-end">
                    {t("history.unique")}
                  </TableHead>
                  <TableHead className="text-end">
                    {t("history.duration")}
                  </TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {history.map((session) => (
                  <TableRow key={session.id}>
                    <TableCell className="max-w-56 font-medium">
                      <div className="truncate">{session.original_query}</div>
                    </TableCell>
                    <TableCell className="max-w-56 text-muted-foreground">
                      <div className="truncate">{session.normalized_query}</div>
                    </TableCell>
                    <TableCell className="whitespace-nowrap text-xs">
                      {formatDate(session.started_at, locale)}
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={session.status} />
                    </TableCell>
                    <TableCell>
                      <div className="flex max-w-56 flex-wrap gap-1">
                        {session.sources.map((source) => (
                          <Badge variant="outline" key={source}>
                            {source}
                          </Badge>
                        ))}
                      </div>
                    </TableCell>
                    <TableCell className="text-end tabular-nums">
                      {formatNumber(session.result_count, locale)}
                    </TableCell>
                    <TableCell className="text-end tabular-nums">
                      {formatNumber(session.unique_count, locale)}
                    </TableCell>
                    <TableCell className="whitespace-nowrap text-end text-xs">
                      {formatDuration(session.duration_ms, locale)}
                    </TableCell>
                    <TableCell>
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        aria-label={t("action.open")}
                        onClick={() => navigate(`/search/${session.id}`)}
                      >
                        <ExternalLink />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </Card>
      )}
    </div>
  );
}
