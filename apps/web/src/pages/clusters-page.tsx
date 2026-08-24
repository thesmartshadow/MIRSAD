import { CalendarRange, Layers3 } from "lucide-react";
import { useState } from "react";

import { ResultCard } from "@/components/search/result-card";
import { EmptyState, PageHeader } from "@/components/shared/page";
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

const CLUSTER_FIELD = {
  width: 1040,
  height: 470,
  axisLeft: 88,
  axisRight: 986,
  axisTop: 54,
  axisBottom: 400,
  plotLeft: 118,
  plotRight: 968,
} as const;

type ClusterLayout = {
  cluster: ClusterSummary;
  x: number;
  y: number;
  radius: number;
  extent: number;
  scoreRatio: number;
};

function clusterNodeRadius(memberCount: number) {
  const countWidth = String(memberCount).length * 6.5;
  const dataRadius = Math.min(32, 7 + Math.sqrt(memberCount) * 5);
  return Math.max(12, dataRadius, countWidth / 2 + 5);
}

function resolveClusterCollisions(layouts: ClusterLayout[]) {
  const placed: ClusterLayout[] = [];

  for (const layout of [...layouts].sort((left, right) => left.x - right.x)) {
    const minimumY = CLUSTER_FIELD.axisTop + layout.extent + 5;
    const maximumY = CLUSTER_FIELD.axisBottom - layout.extent - 8;
    const preferredY = Math.max(minimumY, Math.min(maximumY, layout.y));
    const candidates = Array.from(
      { length: Math.floor((maximumY - minimumY) / 4) + 1 },
      (_, index) => minimumY + index * 4,
    ).sort(
      (left, right) =>
        Math.abs(left - preferredY) - Math.abs(right - preferredY) ||
        left - right,
    );
    const y =
      candidates.find((candidateY) =>
        placed.every((other) => {
          const requiredDistance = layout.extent + other.extent + 6;
          return (
            Math.hypot(layout.x - other.x, candidateY - other.y) >=
            requiredDistance
          );
        }),
      ) ?? preferredY;

    placed.push({ ...layout, y });
  }

  const byId = new Map(placed.map((layout) => [layout.cluster.id, layout]));
  return layouts.map((layout) => byId.get(layout.cluster.id) ?? layout);
}

function ClusterField({
  clusters,
  onSelect,
}: {
  clusters: ClusterSummary[];
  onSelect: (cluster: ClusterSummary) => void;
}) {
  const { locale, t } = useI18n();
  const [focused, setFocused] = useState<ClusterSummary | null>(null);
  const visible = clusters.slice(0, 18);
  const scores = visible.map((cluster) => cluster.aggregate_score);
  const minScore = Math.min(...scores);
  const maxScore = Math.max(...scores);
  const chronological = [...visible].sort((left, right) => {
    const leftTime =
      Date.parse(left.earliest_at ?? left.first_seen_by_mirsad ?? "") || 0;
    const rightTime =
      Date.parse(right.earliest_at ?? right.first_seen_by_mirsad ?? "") || 0;
    return leftTime - rightTime || left.id.localeCompare(right.id);
  });
  const layouts = resolveClusterCollisions(
    visible.map((cluster) => {
      const chronologicalIndex = chronological.findIndex(
        (item) => item.id === cluster.id,
      );
      const timeRatio =
        chronologicalIndex / Math.max(1, chronological.length - 1);
      const scoreRatio =
        maxScore === minScore
          ? 0.5
          : (cluster.aggregate_score - minScore) / (maxScore - minScore);
      const radius = clusterNodeRadius(cluster.member_count);
      return {
        cluster,
        x:
          CLUSTER_FIELD.plotLeft +
          timeRatio * (CLUSTER_FIELD.plotRight - CLUSTER_FIELD.plotLeft),
        y:
          CLUSTER_FIELD.axisBottom -
          26 -
          scoreRatio * (CLUSTER_FIELD.axisBottom - CLUSTER_FIELD.axisTop - 52),
        radius,
        extent: radius + 6,
        scoreRatio,
      };
    }),
  );
  const preview = focused ?? visible[0] ?? null;
  return (
    <section className="cluster-field" aria-label={t("clusters.mapTitle")}>
      <header>
        <div>
          <strong>{t("clusters.mapTitle")}</strong>
          <span>{t("clusters.mapLegend")}</span>
        </div>
        <span>{formatNumber(visible.length, locale)} {t("clusters.members")}</span>
      </header>
      <div className="cluster-field__layout">
      <div className="cluster-field__canvas">
      <svg
        viewBox={`0 0 ${CLUSTER_FIELD.width} ${CLUSTER_FIELD.height}`}
        role="group"
        aria-labelledby="cluster-map-title cluster-map-desc"
      >
        <title id="cluster-map-title">{t("clusters.mapTitle")}</title>
        <desc id="cluster-map-desc">{t("clusters.mapDescription")}</desc>
        <path
          d={`M${CLUSTER_FIELD.axisLeft} ${CLUSTER_FIELD.axisBottom}H${CLUSTER_FIELD.axisRight}M${CLUSTER_FIELD.axisLeft} ${CLUSTER_FIELD.axisTop}V${CLUSTER_FIELD.axisBottom}`}
          className="cluster-field__axis"
        />
        {[1, 2, 3, 4, 5].map((step) => (
          <path
            key={step}
            d={`M${CLUSTER_FIELD.axisLeft} ${CLUSTER_FIELD.axisBottom - step * 58}H${CLUSTER_FIELD.axisRight}`}
            className="cluster-field__guide"
          />
        ))}
        <text x="92" y="31" className="cluster-field__axis-label">{t("score.relevance")}</text>
        <text
          x={CLUSTER_FIELD.axisRight}
          y="438"
          textAnchor="end"
          className="cluster-field__axis-label"
        >
          {t("clusters.firstSeen")}
        </text>
        {layouts.map(({ cluster, x, y, radius, scoreRatio }) => (
            <g
              key={cluster.id}
              className="cluster-field__node"
              transform={`translate(${x} ${y})`}
              role="button"
              tabIndex={0}
              aria-label={cluster.representative_title}
              data-focused={focused?.id === cluster.id}
              onMouseEnter={() => setFocused(cluster)}
              onMouseLeave={() => setFocused(null)}
              onFocus={() => setFocused(cluster)}
              onBlur={() => setFocused(null)}
              onClick={() => onSelect(cluster)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  onSelect(cluster);
                }
              }}
            >
              <circle r={radius} className="cluster-field__point" style={{ fillOpacity: 0.34 + scoreRatio * 0.46 }} />
              <text
                y="0"
                textAnchor="middle"
                dominantBaseline="central"
                className="cluster-field__count"
              >
                {cluster.member_count}
              </text>
            </g>
        ))}
      </svg>
      </div>
      <aside className="cluster-field__preview" aria-live="polite">
        {preview && <>
          <span>{t("clusters.selectedCluster")}</span>
          <h3 dir="auto">{preview.representative_title}</h3>
          <dl>
            <div><dt>{t("clusters.members")}</dt><dd>{formatNumber(preview.member_count, locale)}</dd></div>
            <div><dt>{t("score.relevance")}</dt><dd>{formatNumber(preview.aggregate_score, locale, 1)}</dd></div>
            <div><dt>{t("clusters.platformDiversity")}</dt><dd>{formatNumber(preview.platform_diversity, locale)}</dd></div>
            <div><dt>{t("clusters.firstSeen")}</dt><dd>{formatDate(preview.first_seen_by_mirsad, locale)}</dd></div>
          </dl>
          <p dir="auto">{preview.terms.slice(0, 5).join(" · ")}</p>
        </>}
      </aside>
      </div>
    </section>
  );
}

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
    <div className="instrument-page instrument-page--clusters">
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
        <div className="cluster-workspace">
          <ClusterField
            clusters={currentSearch.clusters}
            onSelect={setSelected}
          />
          <ol className="cluster-index">
            {currentSearch.clusters.map((cluster, index) => (
              <li key={cluster.id}>
                <button
                  type="button"
                  onClick={() => setSelected(cluster)}
                  aria-label={cluster.representative_title}
                >
                  <span className="cluster-index__number">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <span className="cluster-index__title" dir="auto">
                    <strong>{cluster.representative_title}</strong>
                    <small>{cluster.terms.slice(0, 5).join(" · ")}</small>
                  </span>
                  <span>
                    <Layers3 /> {formatNumber(cluster.member_count, locale)}
                  </span>
                  <span dir="ltr">
                    {Object.entries(cluster.platform_presence)
                      .map(([key, value]) => `${key} ${value}`)
                      .join(" · ")}
                  </span>
                  <span>
                    <CalendarRange />{" "}
                    {formatDate(cluster.first_seen_by_mirsad, locale)}
                  </span>
                  <strong>
                    {formatNumber(cluster.aggregate_score, locale, 1)}
                  </strong>
                </button>
              </li>
            ))}
          </ol>
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
            <div className="evidence-ledger">
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
