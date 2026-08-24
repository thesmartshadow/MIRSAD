import {
  Archive,
  CircleAlert,
  Database,
  RadioTower,
  Route,
} from "lucide-react";

import { StatusBadge } from "@/components/shared/page";
import { useI18n } from "@/lib/i18n";
import type { CoverageLane, CoverageReport } from "@/types/api";

const laneIcons = {
  LIVE: RadioTower,
  LOCAL_MEMORY: Database,
  HISTORICAL: Archive,
};

function CoverageTopology({ coverage }: { coverage: CoverageReport }) {
  const { t } = useI18n();
  const active = coverage.lanes.filter((lane) => lane.executed || lane.available);
  const width = 720;
  const step = width / Math.max(1, active.length + 1);
  return (
    <svg
      viewBox={`0 0 ${width} 168`}
      className="h-auto w-full"
      role="img"
      aria-labelledby="coverage-topology-title coverage-topology-description"
    >
      <title id="coverage-topology-title">{t("coverage.topology")}</title>
      <desc id="coverage-topology-description">{t("coverage.topologyDescription")}</desc>
      <path d="M 44 126 H 676" className="coverage-axis" />
      {active.map((lane, index) => {
        const x = step * (index + 1);
        return (
          <g key={lane.lane} transform={`translate(${x} 0)`}>
            <path d="M 0 48 V 126" className="coverage-path" data-contributed={lane.contributed} />
            <circle cy="44" r="8" className="coverage-node" data-contributed={lane.contributed} />
            <text y="22" textAnchor="middle" className="coverage-label">
              {t(`coverage.${lane.lane.toLowerCase()}` as never)}
            </text>
            <text y="153" textAnchor="middle" className="coverage-value">
              {lane.final} / {lane.candidates}
            </text>
          </g>
        );
      })}
      <circle cx="676" cy="126" r="10" className="coverage-evidence" />
      <text x="676" y="153" textAnchor="middle" className="coverage-label">
        {t("coverage.evidence")}
      </text>
    </svg>
  );
}

function LaneRow({ lane }: { lane: CoverageLane }) {
  const { locale, t } = useI18n();
  const Icon = laneIcons[lane.lane];
  return (
    <section className="coverage-lane">
      <div className="coverage-lane__identity">
        <Icon className="size-4" />
        <div>
          <h3>{t(`coverage.${lane.lane.toLowerCase()}` as never)}</h3>
          <p>{lane.platforms.length ? lane.platforms.join(" · ") : t("coverage.noContribution")}</p>
        </div>
      </div>
      <dl>
        <div><dt>{t("coverage.candidates")}</dt><dd>{lane.candidates.toLocaleString(locale)}</dd></div>
        <div><dt>{t("coverage.final")}</dt><dd>{lane.final.toLocaleString(locale)}</dd></div>
      </dl>
      <StatusBadge status={lane.contributed ? "completed" : lane.executed ? "available" : "unavailable"} />
    </section>
  );
}

export function CoverageView({ coverage }: { coverage: CoverageReport }) {
  const { t } = useI18n();
  return (
    <div className="coverage-view">
      <header className="coverage-view__header">
        <div>
          <span>{t("coverage.label")}</span>
          <h2>{t("coverage.title")}</h2>
        </div>
        <StatusBadge status={coverage.coverage_status === "PARTIAL" ? "partial" : coverage.coverage_status === "LIMITED" ? "degraded" : "completed"} />
      </header>
      <div className="coverage-topology-plane"><CoverageTopology coverage={coverage} /></div>
      <div className="coverage-lanes">
        {coverage.lanes.map((lane) => <LaneRow key={lane.lane} lane={lane} />)}
      </div>
      <section className="coverage-sources" aria-labelledby="coverage-sources-title">
        <div className="coverage-gaps__heading">
          <Route className="size-4" />
          <h3 id="coverage-sources-title">{t("coverage.sources")}</h3>
        </div>
        <ol>
          {coverage.sources.map((source) => (
            <li key={source.source}>
              <div><bdi>{source.source}</bdi><small>{source.acquisition_mode ?? "—"}</small></div>
              <StatusBadge status={source.status.toLowerCase()} />
              <dl>
                <div><dt>{t("coverage.fetched")}</dt><dd>{source.fetched}</dd></div>
                <div><dt>{t("coverage.matched")}</dt><dd>{source.matched}</dd></div>
                <div><dt>{t("coverage.final")}</dt><dd>{source.final}</dd></div>
              </dl>
              <p>{source.planning_reasons[0] ?? source.detail ?? t("coverage.noReason")}</p>
            </li>
          ))}
        </ol>
      </section>
      <section className="coverage-gaps" aria-labelledby="coverage-gaps-title">
        <div className="coverage-gaps__heading">
          <CircleAlert className="size-4" />
          <h3 id="coverage-gaps-title">{t("coverage.gaps")}</h3>
          <span>{coverage.gaps.length}</span>
        </div>
        {coverage.gaps.length ? (
          <ol>
            {coverage.gaps.map((gap) => (
              <li key={`${gap.source}-${gap.reason}`}>
                <bdi>{gap.source}</bdi>
                <strong>{gap.reason.replaceAll("_", " ")}</strong>
                <p>{gap.detail}</p>
              </li>
            ))}
          </ol>
        ) : <p className="coverage-empty">{t("coverage.noGaps")}</p>}
      </section>
      {coverage.stop_explanation && (
        <footer className="coverage-stop"><Route className="size-4" /><span>{coverage.stop_explanation}</span></footer>
      )}
    </div>
  );
}
