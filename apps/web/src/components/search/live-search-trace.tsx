import {
  AlertTriangle,
  CheckCircle2,
  CircleDashed,
  LoaderCircle,
  MinusCircle,
} from "lucide-react";

import { Progress } from "@/components/ui/progress";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { formatDuration, formatNumber } from "@/lib/format";
import { useI18n } from "@/lib/i18n";
import type { LiveSourceState, SearchJobState } from "@/lib/search-job-state";

const iconByStatus = {
  selected: CircleDashed,
  searching: LoaderCircle,
  completed: CheckCircle2,
  degraded: AlertTriangle,
  failed: AlertTriangle,
  skipped: MinusCircle,
};

function SourceLine({ source, state }: { source: string; state: LiveSourceState }) {
  const { locale, t } = useI18n();
  const Icon = iconByStatus[state.status];
  return (
    <li className="border-b py-3 last:border-0">
      <div className="flex items-center justify-between gap-2">
        <span className="flex min-w-0 items-center gap-2 font-medium" dir="ltr">
          <Icon
            className={`size-4 shrink-0 ${state.status === "searching" ? "animate-spin text-primary" : state.status === "failed" || state.status === "degraded" ? "text-amber-600" : state.status === "completed" ? "text-emerald-600" : "text-muted-foreground"}`}
          />
          {source}
        </span>
        <span className="text-[11px] text-muted-foreground">
          {t(`live.status.${state.status}`)}
        </span>
      </div>
      {(state.fetched > 0 || state.elapsedMs !== null || state.errorCategory) && (
        <div className="mt-1.5 ps-6 text-[11px] leading-5 text-muted-foreground">
          {state.fetched > 0 && (
            <span>
              {formatNumber(state.fetched, locale)} {t("live.fetched")} · {formatNumber(state.matched, locale)} {t("live.matched")}
            </span>
          )}
          {state.admitted > 0 && (
            <span> · {formatNumber(state.admitted, locale)} {t("diagnostics.admitted")}</span>
          )}
          {state.elapsedMs !== null && <span> · {formatDuration(state.elapsedMs, locale)}</span>}
          {state.errorCategory && <div>{state.errorCategory.replaceAll("_", " ")}</div>}
        </div>
      )}
    </li>
  );
}

export function LiveSearchTrace({ state }: { state: SearchJobState }) {
  const { locale, t } = useI18n();
  const sources = Object.entries(state.sources);
  const progress = state.selectedSourceCount
    ? (state.completedSourceCount / state.selectedSourceCount) * 100
    : state.phase === "completed" || state.phase === "partial"
      ? 100
      : 0;
  return (
    <section aria-label={t("live.title")} className="flex min-h-0 flex-col">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
          {t("live.title")}
        </h2>
        <span className="text-xs font-medium">{t(`live.phase.${state.phase}`)}</span>
      </div>
      <Progress
        value={progress}
        aria-label={t("live.progress")}
        className="mb-3 h-1.5"
      />
      <div className="grid grid-cols-3 gap-2 text-center">
        {[
          [t("live.sources"), `${state.completedSourceCount}/${state.selectedSourceCount}`],
          [t("live.candidates"), formatNumber(state.admitted || state.fetched, locale)],
          [t("live.matched"), formatNumber(state.matched, locale)],
        ].map(([label, value]) => (
          <div className="border-e last:border-0" key={label}>
            <div className="font-semibold tabular-nums">{value}</div>
            <div className="text-[10px] text-muted-foreground">{label}</div>
          </div>
        ))}
      </div>
      <Separator className="my-3" />
      <ScrollArea className="h-[min(45vh,28rem)] min-h-24 overflow-hidden">
        {sources.length ? (
          <ul>{sources.map(([source, sourceState]) => <SourceLine key={source} source={source} state={sourceState} />)}</ul>
        ) : (
          <p className="py-6 text-center text-xs text-muted-foreground">{t("live.waiting")}</p>
        )}
      </ScrollArea>
      <Separator className="my-3" />
      <dl className="grid grid-cols-2 gap-x-3 gap-y-2 text-xs">
        <dt className="text-muted-foreground">{t("live.elapsed")}</dt>
        <dd className="text-end tabular-nums">{formatDuration(state.serverElapsedMs, locale)}</dd>
        <dt className="text-muted-foreground">{t("live.feedback")}</dt>
        <dd className="text-end tabular-nums">{formatDuration(state.feedbackLatencyMs, locale)}</dd>
        <dt className="text-muted-foreground">{t("live.firstEvent")}</dt>
        <dd className="text-end tabular-nums">{state.firstEventLatencyMs === null ? "—" : formatDuration(state.firstEventLatencyMs, locale)}</dd>
        {state.stopReason && (
          <>
            <dt className="text-muted-foreground">{t("diagnostics.stopReason")}</dt>
            <dd className="text-end text-[11px]">{state.stopReason}</dd>
          </>
        )}
      </dl>
    </section>
  );
}
