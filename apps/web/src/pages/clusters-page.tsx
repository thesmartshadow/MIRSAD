import { Boxes, CalendarRange, Layers3 } from "lucide-react";
import { useState } from "react";

import { ResultCard } from "@/components/search/result-card";
import { EmptyState, PageHeader } from "@/components/shared/page";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { formatDate, formatNumber } from "@/lib/format";
import { useI18n } from "@/lib/i18n";
import { useSearchState } from "@/lib/search-state";
import type { ClusterSummary } from "@/types/api";

export function ClustersPage() {
  const { currentSearch } = useSearchState();
  const { locale, t } = useI18n();
  const [selected, setSelected] = useState<ClusterSummary | null>(null);
  const members = selected
    ? (currentSearch?.results.filter((item) =>
        selected.member_ids.includes(item.id),
      ) ?? [])
    : [];
  return (
    <div>
      <PageHeader
        title={t("clusters.title")}
        description={t("clusters.description")}
      />
      {!currentSearch || currentSearch.clusters.length === 0 ? (
        <EmptyState
          title={t("clusters.title")}
          description={t("clusters.empty")}
        />
      ) : (
        <div className="grid gap-3 lg:grid-cols-2 2xl:grid-cols-3">
          {currentSearch.clusters.map((cluster) => (
            <Card
              key={cluster.id}
              role="button"
              tabIndex={0}
              aria-label={cluster.representative_title}
              className="cursor-pointer shadow-none hover:border-primary/40 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
              onClick={() => setSelected(cluster)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  setSelected(cluster);
                }
              }}
            >
              <CardContent className="space-y-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex size-9 shrink-0 items-center justify-center rounded-md bg-muted">
                    <Boxes className="size-4" />
                  </div>
                  <div className="font-heading text-2xl font-semibold tabular-nums">
                    {formatNumber(cluster.aggregate_score, locale, 1)}
                  </div>
                </div>
                <h3 className="line-clamp-2 text-sm font-semibold">
                  {cluster.representative_title}
                </h3>
                <div className="flex flex-wrap gap-1">
                  {cluster.terms.slice(0, 5).map((term) => (
                    <Badge key={term} variant="secondary">
                      {term}
                    </Badge>
                  ))}
                </div>
                <div className="grid grid-cols-2 gap-2 border-t pt-3 text-xs text-muted-foreground">
                  <span className="flex items-center gap-1">
                    <Layers3 className="size-3" />
                    {cluster.member_count} {t("clusters.members")}
                  </span>
                  <span className="truncate text-end">
                    {Object.entries(cluster.platform_presence)
                      .map(([key, value]) => `${key} ${value}`)
                      .join(" · ")}
                  </span>
                  <span className="col-span-2 flex items-center gap-1">
                    <CalendarRange className="size-3" />
                    {t("clusters.firstSeen")}:{" "}
                    {formatDate(cluster.first_seen_by_mirsad, locale)} ·{" "}
                    {t("clusters.platformDiversity")}:{" "}
                    {formatNumber(cluster.platform_diversity, locale)}
                  </span>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
      <Dialog
        open={Boolean(selected)}
        onOpenChange={(open) => !open && setSelected(null)}
      >
        <DialogContent className="max-h-[90vh] sm:max-w-4xl">
          <DialogHeader>
            <DialogTitle>{selected?.representative_title}</DialogTitle>
            <DialogDescription>
              {selected?.member_count} {t("clusters.members")} ·{" "}
              {t("clusters.firstSeen")}:{" "}
              {formatDate(selected?.first_seen_by_mirsad ?? null, locale)} ·{" "}
              {t("clusters.platformDiversity")}:{" "}
              {formatNumber(selected?.platform_diversity ?? 0, locale)}
            </DialogDescription>
          </DialogHeader>
          <ScrollArea className="max-h-[70vh] pe-3">
            <div className="space-y-3">
              {members.map((item) => (
                <ResultCard key={item.id} item={item} />
              ))}
            </div>
          </ScrollArea>
        </DialogContent>
      </Dialog>
    </div>
  );
}
