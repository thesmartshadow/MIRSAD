import { useI18n } from "@/lib/i18n";

export function QueryField() {
  const { t } = useI18n();

  return (
    <section
      className="query-field"
      aria-labelledby="query-field-title"
    >
      <div className="query-field__copy">
        <h2 id="query-field-title">{t("search.emptyTitle")}</h2>
        <p>{t("search.emptyDescription")}</p>
      </div>
      <svg viewBox="0 0 960 260" role="img" aria-labelledby="query-field-svg-title query-field-svg-desc">
        <title id="query-field-svg-title">{t("coverage.topology")}</title>
        <desc id="query-field-svg-desc">{t("coverage.topologyDescription")}</desc>
        <path d="M70 130 C180 130 210 55 335 55 S480 130 585 130 S705 72 890 72" className="query-field__path query-field__path--live" />
        <path d="M70 130H585 C705 130 735 130 890 130" className="query-field__path query-field__path--memory" />
        <path d="M70 130 C180 130 210 205 335 205 S480 130 585 130 S705 188 890 188" className="query-field__path query-field__path--history" />
        <g className="query-field__node query-field__node--query" transform="translate(70 130)"><circle r="18" /><text y="4">Q</text></g>
        <g className="query-field__lane" transform="translate(335 55)"><circle r="6" /><text x="16" y="4">{t("coverage.live")}</text></g>
        <g className="query-field__lane" transform="translate(335 130)"><circle r="6" /><text x="16" y="4">{t("coverage.local_memory")}</text></g>
        <g className="query-field__lane" transform="translate(335 205)"><circle r="6" /><text x="16" y="4">{t("coverage.historical")}</text></g>
        <g className="query-field__node query-field__node--core" transform="translate(585 130)"><rect x="-31" y="-20" width="62" height="40" rx="4" /><text y="4">MAFER</text></g>
        <g className="query-field__node query-field__node--evidence" transform="translate(890 130)"><circle r="18" /><text x="-34" y="44">{t("coverage.evidence")}</text></g>
      </svg>
    </section>
  );
}
