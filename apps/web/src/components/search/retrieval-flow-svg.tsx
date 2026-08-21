import { useEffect, useId, useRef } from "react";

import { loadGsap, motion } from "@/lib/motion";
import type { SearchJobState } from "@/lib/search-job-state";

const activePhases = new Set(["creating", "planning", "collecting", "normalizing", "ranking", "clustering"]);

function pathState(status: string) {
  if (status === "searching") return "active";
  if (["completed", "degraded"].includes(status)) return "complete";
  if (status === "failed") return "failed";
  return "idle";
}

export function RetrievalFlowSvg({ state }: { state: SearchJobState }) {
  const scope = useRef<SVGSVGElement>(null);
  const titleId = useId();
  const descriptionId = useId();
  const sources = Object.entries(state.sources).slice(0, 6);
  const signature = [
    state.phase,
    state.memory.status,
    ...sources.map(([source, item]) => `${source}:${item.status}`),
  ].join("|");

  useEffect(() => {
    let disposed = false;
    let revert: () => void = () => undefined;
    void loadGsap().then((gsap) => {
      if (disposed || !scope.current) return;
      const element = scope.current;
      const context = gsap.context(() => {
        const media = gsap.matchMedia();
        media.add("(prefers-reduced-motion: no-preference)", () => {
          const activePaths = element.querySelectorAll("[data-flow-state='active']");
          const changedNodes = element.querySelectorAll("[data-flow-node='changed']");
          if (activePaths.length)
            gsap.fromTo(
              activePaths,
              { strokeDashoffset: 18, opacity: 0.45 },
              {
                strokeDashoffset: 0,
                opacity: 1,
                duration: motion.standard,
                ease: motion.ease,
              },
            );
          if (changedNodes.length)
            gsap.fromTo(
              changedNodes,
              { scale: 0.82, transformOrigin: "center" },
              { scale: 1, duration: motion.quick, ease: motion.ease },
            );
        });
        revert = () => media.revert();
      }, element);
      const contextRevert = revert;
      revert = () => {
        contextRevert();
        context.revert();
      };
    });
    return () => {
      disposed = true;
      revert();
    };
  }, [signature]);

  const phaseActive = activePhases.has(state.phase);
  return (
    <svg
      ref={scope}
      viewBox="0 0 760 190"
      role="img"
      aria-labelledby={`${titleId} ${descriptionId}`}
      className="h-auto w-full overflow-visible"
      data-testid="retrieval-flow-svg"
    >
      <title id={titleId}>MIRSAD retrieval flow</title>
      <desc id={descriptionId}>
        Actual connector and local-memory states flowing through MAFER, normalization, ranking, and evidence.
      </desc>
      <g className="fill-none stroke-border" strokeWidth="1.2">
        {sources.map(([source, sourceState], index) => {
          const y = 22 + index * 26;
          const stateName = pathState(sourceState.status);
          return (
            <g key={source}>
              <path
                d={`M 128 ${y} C 180 ${y}, 190 95, 250 95`}
                data-flow-state={stateName}
                className={
                  stateName === "active"
                    ? "stroke-primary [stroke-dasharray:5_4]"
                    : stateName === "complete"
                      ? "stroke-[var(--status-healthy)]"
                      : stateName === "failed"
                        ? "stroke-destructive"
                        : "stroke-border"
                }
              />
              <circle
                cx="119"
                cy={y}
                r="5"
                data-flow-node={sourceState.status === "searching" ? "changed" : "stable"}
                className={
                  sourceState.status === "searching"
                    ? "fill-primary"
                    : sourceState.status === "completed"
                      ? "fill-[var(--status-healthy)]"
                      : sourceState.status === "failed"
                        ? "fill-destructive"
                        : "fill-muted-foreground"
                }
              />
              <text x="105" y={y + 4} textAnchor="end" className="fill-muted-foreground text-[10px]" direction="ltr">
                {source}
              </text>
            </g>
          );
        })}
        {state.memory.status !== "idle" && (
          <g>
            <path
              d="M 128 176 C 190 176, 196 105, 250 105"
              data-flow-state={state.memory.status === "searching" ? "active" : "complete"}
              className="stroke-[var(--status-memory)] [stroke-dasharray:3_3]"
            />
            <circle cx="119" cy="176" r="5" className="fill-[var(--status-memory)]" />
            <text x="105" y="180" textAnchor="end" className="fill-muted-foreground text-[10px]">
              Local memory
            </text>
          </g>
        )}
        <path d="M 294 95 H 355" className={phaseActive ? "stroke-primary" : "stroke-border"} />
        <path d="M 420 95 H 481" className={state.phase === "ranking" ? "stroke-primary" : "stroke-border"} />
        <path d="M 545 95 H 614" className={["completed", "partial"].includes(state.phase) ? "stroke-[var(--status-healthy)]" : "stroke-border"} />
      </g>
      {[
        [272, "MAFER"],
        [387, "Normalize"],
        [513, "Rank"],
        [653, "Evidence"],
      ].map(([x, label]) => (
        <g key={String(label)}>
          <circle cx={Number(x)} cy="95" r="22" className="fill-background stroke-border" />
          <text x={Number(x)} y="99" textAnchor="middle" className="fill-foreground text-[10px] font-medium">
            {label}
          </text>
        </g>
      ))}
    </svg>
  );
}
