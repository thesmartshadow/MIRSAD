import {
  Clock3,
  Copy,
  ExternalLink,
  Gauge,
  Link2,
  Bookmark,
  BookmarkCheck,
  ThumbsDown,
  ThumbsUp,
  UserRound,
} from "lucide-react";
import { useEffect, useState } from "react";

import { HighlightedSnippet } from "@/components/search/highlighted-snippet";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { Separator } from "@/components/ui/separator";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { api, ApiError } from "@/lib/api";
import { displayText, safeExternalUrl } from "@/lib/external-content";
import { formatDate, formatNumber } from "@/lib/format";
import { useI18n, type TranslationKey } from "@/lib/i18n";
import type { DuplicateGroup, SearchResultItem } from "@/types/api";

const secondarySignals: Array<[string, TranslationKey]> = [
  ["freshness", "score.freshness"],
  ["engagement", "score.engagement"],
  ["source_confidence", "score.confidence"],
  ["cross_source_presence", "score.presence"],
  ["novelty", "score.novelty"],
];

const duplicateStageKeys: Record<string, TranslationKey> = {
  canonical: "duplicates.stage.canonical",
  url: "duplicates.stage.url",
  fingerprint: "duplicates.stage.fingerprint",
  similarity: "duplicates.stage.similarity",
};

function ScoreSheet({ item }: { item: SearchResultItem }) {
  const { direction, locale, t } = useI18n();
  const explanation = item.explanation;
  const semanticState =
    explanation.semantic_state ??
    (explanation.semantic_relevance === null ? "lexical_only" : "ready");
  const semanticReady = semanticState === "ready";
  const lexicalWeight = semanticReady ? 1 - explanation.semantic_weight : 1;
  return (
    <Sheet>
      <SheetTrigger render={<Button variant="outline" size="sm" />}>
        <Gauge /> {t("action.explain")}
      </SheetTrigger>
      <SheetContent
        side={direction === "rtl" ? "left" : "right"}
        className="sm:max-w-md"
      >
        <SheetHeader className="border-b">
          <SheetTitle>{t("score.title")}</SheetTitle>
          <SheetDescription>{t("score.description")}</SheetDescription>
        </SheetHeader>
        <ScrollArea className="min-h-0 flex-1 px-4">
          <div className="space-y-6 pb-6" data-testid="score-instrument">
            <div className="border-b py-5">
              <div className="text-xs font-semibold uppercase tracking-[0.15em] text-muted-foreground">{t("score.final")}</div>
              <div className="mt-1 font-heading text-5xl font-semibold tabular-nums">
                {formatNumber(explanation.final_score, locale, 1)}
              </div>
              <p className="mt-2 text-xs text-muted-foreground">{t("score.notProbability")}</p>
            </div>

            <section aria-labelledby={`core-score-${item.id}`}>
              <div className="mb-3 flex items-center justify-between border-b pb-2">
                <h3 id={`core-score-${item.id}`} className="text-xs font-semibold uppercase tracking-[0.14em]">{t("score.core")}</h3>
                <span className="text-[11px] text-muted-foreground">{t(semanticReady ? "score.coreArchitecture" : "score.coreLexical")}</span>
              </div>
              {semanticReady ? (
                <div className="space-y-4">
                  <svg viewBox="0 0 100 8" role="img" aria-label={t("score.composition")} className="h-2 w-full">
                    <rect width={lexicalWeight * 100} height="8" className="fill-[var(--score-lexical)]" />
                    <rect x={lexicalWeight * 100} width={explanation.semantic_weight * 100} height="8" className="fill-[var(--score-semantic)]" />
                  </svg>
                  {[
                    [t("score.lexicalRelevance"), explanation.lexical_relevance, lexicalWeight],
                    [t("score.semanticRelevance"), explanation.semantic_relevance, explanation.semantic_weight],
                  ].map(([label, value, weight]) => (
                    <div key={String(label)} className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-1">
                      <div className="text-sm font-medium">{label}</div>
                      <div className="font-semibold tabular-nums">{formatNumber(Number(value), locale, 1)}</div>
                      <div className="text-[11px] text-muted-foreground">{formatNumber(Number(weight) * 100, locale, 0)}% {t("score.modelWeight")}</div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="border-s-2 border-muted-foreground/40 ps-3">
                  <div className="flex items-baseline justify-between gap-4">
                    <span className="text-sm font-medium">{t("score.lexicalRelevance")}</span>
                    <strong className="tabular-nums">{formatNumber(explanation.lexical_relevance, locale, 1)}</strong>
                  </div>
                  <p className="mt-2 text-xs text-muted-foreground">{t(`score.semanticState.${semanticState}`)}</p>
                </div>
              )}
            </section>

            <section aria-labelledby={`secondary-score-${item.id}`} className="border-t pt-4">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h3 id={`secondary-score-${item.id}`} className="text-xs font-semibold uppercase tracking-[0.14em]">{t("score.secondary")}</h3>
                  <p className="mt-1 text-[11px] text-muted-foreground">
                    {t("score.secondaryBudget")} {formatNumber(explanation.secondary_quality_budget * 100, locale, 1)}%
                  </p>
                </div>
                <span className="h-1.5 w-12 bg-[var(--score-secondary)]" aria-hidden="true" />
              </div>
              <dl className="mt-4 grid grid-cols-[1fr_auto] gap-x-4 gap-y-2 text-xs">
                {secondarySignals.map(([key, label]) => (
                  <div key={key} className="contents">
                    <dt className="text-muted-foreground">{t(label)}</dt>
                    <dd className="text-end tabular-nums">
                      {formatNumber(Number(explanation.weighted_components[key] ?? 0), locale, 3)}
                    </dd>
                  </div>
                ))}
              </dl>
            </section>

            <section className="flex items-center justify-between border-y py-3 text-sm">
              <span className="font-medium">{t("score.penalty")}</span>
              <span className="tabular-nums text-destructive">-{formatNumber(explanation.spam_penalty, locale, 1)}</span>
            </section>
            <Separator />
            <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-3 text-sm">
              <dt className="text-muted-foreground">{t("result.source")}</dt>
              <dd>{item.source}</dd>
              <dt className="text-muted-foreground">
                {t("result.sourceType")}
              </dt>
              <dd>{item.source_type}</dd>
              <dt className="text-muted-foreground">{t("result.fetched")}</dt>
              <dd>{formatDate(item.fetched_at, locale)}</dd>
              <dt className="text-muted-foreground">{t("result.published")}</dt>
              <dd>{formatDate(item.published_at, locale)}</dd>
              <dt className="text-muted-foreground">{t("result.matches")}</dt>
              <dd className="flex flex-wrap gap-1">
                {item.matched_terms.map((term) => (
                  <Badge variant="secondary" key={term}>
                    {term}
                  </Badge>
                ))}
              </dd>
              <dt className="text-muted-foreground">
                {t("score.phraseMatch")}
              </dt>
              <dd className="tabular-nums">
                {formatNumber(
                  explanation.relevance_features.exact_full_query ?? 0,
                  locale,
                  0,
                )}
              </dd>
              <dt className="text-muted-foreground">
                {t("score.queryCoverage")}
              </dt>
              <dd className="tabular-nums">
                {formatNumber(
                  explanation.relevance_features.query_token_coverage ?? 0,
                  locale,
                  0,
                )}
              </dd>
              <dt className="text-muted-foreground">
                {t("score.rankingStrategy")}
              </dt>
              <dd>
                {t(
                  !semanticReady
                    ? "score.strategy.lexical"
                    : "score.strategy.semantic",
                )}
              </dd>
              <dt className="text-muted-foreground">{t("score.duplicate")}</dt>
              <dd className="break-all">{item.duplicate_group_id ?? "—"}</dd>
            </dl>
          </div>
        </ScrollArea>
      </SheetContent>
    </Sheet>
  );
}

function DuplicateDialog({ item }: { item: SearchResultItem }) {
  const { locale, t } = useI18n();
  const [open, setOpen] = useState(false);
  const [group, setGroup] = useState<DuplicateGroup | null>(null);
  const [sort, setSort] = useState<"newest" | "source" | "engagement">(
    "newest",
  );
  const [error, setError] = useState("");
  if (!item.duplicate_group_id || item.duplicate_count < 1) return null;
  const load = async (nextSort = sort) => {
    try {
      setGroup(await api.getDuplicateGroup(item.duplicate_group_id!, nextSort));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t("state.error"));
    }
  };
  return (
    <>
      <Button
        variant="ghost"
        size="xs"
        onClick={() => {
          setOpen(true);
          void load();
        }}
      >
        <Copy /> {item.duplicate_count + 1} {t("result.relatedCopies")}
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-4xl">
          <DialogHeader>
            <DialogTitle>{t("duplicates.title")}</DialogTitle>
            <DialogDescription>{t("duplicates.description")}</DialogDescription>
          </DialogHeader>
          {error ? (
            <p className="text-sm text-destructive">{error}</p>
          ) : (
            group && (
              <div className="space-y-4">
                <div className="flex flex-wrap items-end justify-between gap-3 rounded-md border p-3 text-sm">
                  <div>
                    <div>{group.source_names.join(" · ")}</div>
                    <div className="mt-1 text-xs text-muted-foreground">
                      {t("duplicates.firstSeen")}:{" "}
                      {formatDate(group.earliest_seen, locale)} ·{" "}
                      {t("duplicates.lastSeen")}:{" "}
                      {formatDate(group.latest_seen, locale)}
                    </div>
                  </div>
                  <div>
                    <span className="mb-1 block text-xs text-muted-foreground">
                      {t("duplicates.sort")}
                    </span>
                    <Select
                      value={sort}
                      onValueChange={(value) => {
                        const next = value as typeof sort;
                        setSort(next);
                        void load(next);
                      }}
                    >
                      <SelectTrigger
                        className="w-40"
                        aria-label={t("duplicates.sort")}
                      >
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="newest">
                          {t("common.newest")}
                        </SelectItem>
                        <SelectItem value="source">
                          {t("common.source")}
                        </SelectItem>
                        <SelectItem value="engagement">
                          {t("common.engagement")}
                        </SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div className="space-y-2">
                  {group.members.map((member) => (
                    <div key={member.id} className="rounded-md border p-3">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="mb-1 flex flex-wrap gap-1">
                            <Badge variant="outline">{member.source}</Badge>
                            <Badge variant="secondary">
                              {member.source_type}
                            </Badge>
                            {member.representative && (
                              <Badge>{t("result.representative")}</Badge>
                            )}
                          </div>
                          <div className="font-medium" dir="auto">
                            {displayText(member.title) || t("result.untitled")}
                          </div>
                          <div
                            className="mt-1 line-clamp-2 text-xs text-muted-foreground"
                            dir="auto"
                          >
                            {displayText(member.text)}
                          </div>
                        </div>
                        <span className="text-xs tabular-nums">
                          {formatNumber(member.engagement, locale, 1)}
                        </span>
                      </div>
                      <div className="mt-2 text-xs text-muted-foreground">
                        {t("result.similarity")}:{" "}
                        {duplicateStageKeys[member.match_stage]
                          ? t(duplicateStageKeys[member.match_stage])
                          : member.match_stage}{" "}
                        · {formatNumber(member.similarity * 100, locale, 0)}%
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}

export function ResultCard({
  item,
  sessionId,
  initiallyBookmarked = false,
  density = "comfortable",
}: {
  item: SearchResultItem;
  sessionId?: string;
  initiallyBookmarked?: boolean;
  density?: "comfortable" | "compact";
}) {
  const { locale, t } = useI18n();
  const [bookmarked, setBookmarked] = useState(initiallyBookmarked);
  const [bookmarking, setBookmarking] = useState(false);
  const [bookmarkError, setBookmarkError] = useState("");
  const [judgment, setJudgment] = useState<"relevant" | "not_relevant" | null>(null);
  const [judgmentPending, setJudgmentPending] = useState(false);
  useEffect(() => setBookmarked(initiallyBookmarked), [initiallyBookmarked]);
  const excerpt = displayText(item.relevant_snippet || item.text);
  const title = displayText(item.title) || t("result.untitled");
  const author = displayText(item.author) || t("result.unknownAuthor");
  const externalUrl = safeExternalUrl(item.canonical_url);
  const domain = externalUrl ? new URL(externalUrl).hostname.replace(/^www\./, "") : "";
  const acquisitionPath = item.acquisition_path || item.acquisition_mode;
  const publicMetrics = (
    [
      ["result.metric.likes", item.like_count],
      ["result.metric.views", item.view_count],
      ["result.metric.comments", item.comment_count],
      ["result.metric.shares", item.share_count],
      ["result.metric.reposts", item.repost_count],
      ["result.metric.reactions", item.reaction_count],
    ] as Array<[TranslationKey, number | null]>
  ).filter((entry): entry is [TranslationKey, number] => entry[1] !== null);
  return (
    <article
      className={`group border-s-2 border-transparent px-1 transition-colors hover:border-s-primary hover:bg-muted/20 sm:px-3 ${density === "compact" ? "space-y-2 py-3" : "space-y-3 py-5"}`}
      data-testid="evidence-record"
    >
        <div className="flex items-start gap-3">
          <div className="flex size-8 shrink-0 items-center justify-center border-b-2 border-primary/40 text-[11px] font-semibold uppercase">
            {item.source.slice(0, 2)}
          </div>
          <div className="min-w-0 flex-1">
            <div className="mb-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
              <span className="font-semibold uppercase tracking-[0.08em] text-foreground" dir="ltr">{item.source}</span>
              {item.acquisition_mode === "WEB_INDEX" && (
                <Tooltip>
                  <TooltipTrigger
                    render={<Badge variant="secondary" className="font-medium" />}
                  >
                    {t("result.webIndexed")}
                  </TooltipTrigger>
                  <TooltipContent>{t("result.notDirectApi")}</TooltipContent>
                </Tooltip>
              )}
              {item.discovery_support !== null && item.discovery_support > 1 && (
                <span>
                  {t("result.discoverySupport")}: {formatNumber(item.discovery_support, locale)}
                </span>
              )}
              <span className="flex items-center gap-1" dir="auto">
                <UserRound className="size-3" />
                {author}
                {item.author_handle && item.author_handle !== item.author && (
                  <span dir="ltr">@{item.author_handle}</span>
                )}
                {item.author_verified && (
                  <Badge variant="secondary" className="h-4 px-1 text-[9px]">
                    {t("result.verified")}
                  </Badge>
                )}
              </span>
              <span className="flex items-center gap-1">
                <Clock3 className="size-3" />
                {item.published_at
                  ? formatDate(item.published_at, locale)
                  : t("result.publishedUnavailable")}
              </span>
            </div>
            <h3
              className="line-clamp-2 text-sm font-semibold leading-snug"
              dir="auto"
            >
              {title}
            </h3>
          </div>
          <div className="shrink-0 text-end">
            <div className="font-heading text-lg font-semibold tabular-nums">
              {formatNumber(item.score, locale, 1)}
            </div>
            <div className="text-[10px] uppercase tracking-wide text-muted-foreground">
              {t("result.score")}
            </div>
          </div>
        </div>
        <p
          className={
            density === "compact"
              ? "line-clamp-2 text-xs leading-relaxed text-muted-foreground"
              : "line-clamp-3 text-sm leading-relaxed text-muted-foreground"
          }
          dir="auto"
        >
          <HighlightedSnippet text={excerpt} ranges={item.highlight_ranges} />
        </p>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-muted-foreground">
          {domain && (
            <span dir="ltr" className="max-w-56 truncate">
              {domain}
            </span>
          )}
          <span>
            {t("result.platform")}: <bdi className="font-medium text-foreground">{item.source}</bdi>
          </span>
          <span
            className={acquisitionPath === "LOCAL_MEMORY" ? "font-medium text-[var(--status-memory)]" : undefined}
            data-testid="result-acquisition-path"
          >
            {t("result.acquiredThrough")}: <bdi>{acquisitionPath.replaceAll("_", " ")}</bdi>
          </span>
          {acquisitionPath !== item.acquisition_mode && (
            <Tooltip>
              <TooltipTrigger render={<span className="cursor-help border-b border-dotted" />}>
                {t("result.originalAcquisition")}
              </TooltipTrigger>
              <TooltipContent>{item.acquisition_mode.replaceAll("_", " ")}</TooltipContent>
            </Tooltip>
          )}
          {item.cluster_id && (
            <span>
              {t("result.cluster")}: <bdi>{item.cluster_id.slice(0, 8)}</bdi>
            </span>
          )}
          {item.semantic_only_match && (
            <Badge variant="outline">{t("result.semanticMatch")}</Badge>
          )}
        </div>
        {item.matched_terms.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {item.matched_terms.map((term) => (
              <Badge key={term} variant="secondary">
                {term}
              </Badge>
            ))}
          </div>
        )}
        {(publicMetrics.length > 0 || item.hashtags?.length) && (
          <div
            className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground"
            aria-label={t("result.publicMetrics")}
          >
            {publicMetrics.map(([label, value]) => (
              <span key={label}>
                {t(label)}:{" "}
                <strong className="font-medium text-foreground">
                  {formatNumber(value, locale)}
                </strong>
              </span>
            ))}
            {item.hashtags?.map((tag) => (
              <span key={tag} dir="auto">
                #{tag}
              </span>
            ))}
          </div>
        )}
        <div className="flex flex-wrap items-center justify-between gap-2 border-t pt-3">
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
            <span>
              {t("result.engagement")}:{" "}
              <strong className="font-medium text-foreground">
                {formatNumber(item.normalized_engagement, locale, 1)}
              </strong>
            </span>
            {item.social_reach !== null && (
              <span>
                {t("result.socialReach")}:{" "}
                <strong className="font-medium text-foreground">
                  {formatNumber(item.social_reach, locale, 1)}
                </strong>
              </span>
            )}
            <DuplicateDialog item={item} />
            {item.related_sources.length > 1 && (
              <span className="flex items-center gap-1">
                <Link2 className="size-3" />
                {item.related_sources.join(", ")}
              </span>
            )}
          </div>
          <div className="flex gap-2">
            {sessionId && (
              <div
                className="flex items-center rounded-md border"
                aria-label={t("result.feedback")}
              >
                <Button
                  size="icon-sm"
                  variant={judgment === "relevant" ? "secondary" : "ghost"}
                  aria-label={t("result.relevant")}
                  aria-pressed={judgment === "relevant"}
                  disabled={judgmentPending}
                  onClick={async () => {
                    setJudgmentPending(true);
                    try {
                      await api.recordOutcome(
                        "RESULT_MARKED_RELEVANT",
                        sessionId,
                        item.id,
                      );
                      setJudgment("relevant");
                    } catch {
                      setBookmarkError(t("state.error"));
                    } finally {
                      setJudgmentPending(false);
                    }
                  }}
                >
                  <ThumbsUp />
                </Button>
                <Button
                  size="icon-sm"
                  variant={judgment === "not_relevant" ? "secondary" : "ghost"}
                  aria-label={t("result.notRelevant")}
                  aria-pressed={judgment === "not_relevant"}
                  disabled={judgmentPending}
                  onClick={async () => {
                    setJudgmentPending(true);
                    try {
                      await api.recordOutcome(
                        "RESULT_MARKED_NOT_RELEVANT",
                        sessionId,
                        item.id,
                      );
                      setJudgment("not_relevant");
                    } catch {
                      setBookmarkError(t("state.error"));
                    } finally {
                      setJudgmentPending(false);
                    }
                  }}
                >
                  <ThumbsDown />
                </Button>
              </div>
            )}
            <Button
              size="icon-sm"
              variant="ghost"
              aria-label={
                bookmarked ? t("action.bookmarked") : t("action.bookmark")
              }
              disabled={bookmarked || bookmarking}
              onClick={async () => {
                setBookmarking(true);
                setBookmarkError("");
                try {
                  await api.createBookmark(item.id, sessionId ?? null);
                  setBookmarked(true);
                } catch (reason) {
                  if (reason instanceof ApiError && reason.status === 409) {
                    setBookmarked(true);
                  } else {
                    setBookmarkError(t("state.error"));
                  }
                } finally {
                  setBookmarking(false);
                }
              }}
            >
              {bookmarked ? <BookmarkCheck /> : <Bookmark />}
            </Button>
            <ScoreSheet item={item} />
            {externalUrl ? (
              <Button
                nativeButton={false}
                variant="ghost"
                size="sm"
                render={
                  <a
                    href={externalUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    onClick={() => {
                      if (sessionId) {
                        void api
                          .recordOutcome("RESULT_OPENED", sessionId, item.id)
                          .catch(() => undefined);
                      }
                    }}
                  />
                }
              >
                <ExternalLink /> {t("result.external")}
              </Button>
            ) : (
              <span className="self-center text-xs text-muted-foreground">
                {t("result.invalidUrl")}
              </span>
            )}
          </div>
        </div>
        {bookmarkError && (
          <p role="alert" className="text-xs text-destructive">
            {bookmarkError}
          </p>
        )}
    </article>
  );
}
