export type SearchSource =
  | "x"
  | "threads"
  | "telegram"
  | "reddit"
  | "youtube"
  | "instagram"
  | "tiktok"
  | "facebook"
  | "linkedin"
  | "bluesky"
  | "mastodon"
  | "gdelt"
  | "rss"
  | "github"
  | "hacker_news"
  | "mock";

export interface SearchRequest {
  query: string;
  sources: string[];
  time_range: "24h" | "7d" | "30d" | "all";
  language: "all" | "ar" | "en";
  limit: number;
  exact_phrase: boolean;
  sort: "best_match" | "newest" | "most_engaged" | "cross_platform";
  content_types: Array<
    "posts" | "videos" | "channels" | "threads" | "issues" | "news"
  >;
  has_media: boolean | null;
  has_links: boolean | null;
  hashtags: string[];
  source_options: Record<string, Record<string, unknown>>;
  search_mode: "fast" | "balanced" | "deep";
  source_selection: "auto" | "explicit";
}

export type SearchEventName =
  | "search.started"
  | "planning.started"
  | "planning.completed"
  | "source.selected"
  | "source.started"
  | "source.progress"
  | "source.completed"
  | "source.degraded"
  | "source.failed"
  | "source.skipped"
  | "collection.progress"
  | "normalization.completed"
  | "persistence.completed"
  | "ranking.started"
  | "ranking.completed"
  | "clustering.started"
  | "clustering.completed"
  | "search.partial"
  | "search.completed"
  | "search.failed";

export interface SearchJobStarted {
  job_id: string;
  session_id: string;
  status: "started";
}

export interface SearchJobEvent {
  sequence: number;
  event: SearchEventName;
  job_id: string;
  session_id: string;
  elapsed_ms: number;
  emitted_at: string;
  data: Record<string, unknown>;
}

export interface ConnectorWarning {
  source: string;
  code: string;
  message: string;
  retryable: boolean;
  status_code: number | null;
}

export interface SearchSummary {
  id: string;
  original_query: string;
  normalized_query: string;
  detected_language: string;
  status: "running" | "completed" | "partial" | "failed";
  sources: string[];
  result_count: number;
  unique_count: number;
  duration_ms: number;
  started_at: string;
  completed_at: string | null;
  warnings: ConnectorWarning[];
  parameters: SearchRequest;
  outcome_reason?: string | null;
  outcome_context?: Record<string, unknown>;
}

export interface ScoreExplanation {
  final_score: number;
  relevance: number;
  freshness: number;
  engagement: number;
  source_confidence: number;
  cross_source_presence: number;
  novelty: number;
  spam_penalty: number;
  supporting_signal_factor: number;
  pre_penalty_score: number | null;
  weighted_components: Record<string, number>;
  lexical_relevance: number;
  semantic_relevance: number | null;
  semantic_similarity: number | null;
  semantic_weight: number;
  secondary_quality_budget: number;
  ranking_strategy: string;
  relevance_features: Record<string, number>;
  matched_terms: string[];
  source: string;
  fetched_at: string;
  published_at: string | null;
  duplicate_group_id: string | null;
}

export interface SearchResultItem {
  id: string;
  source: string;
  source_type: string;
  acquisition_mode: string;
  acquisition_modes_seen: string[];
  indexed_public_web_coverage: boolean;
  discovery_support: number | null;
  discovery_engines: string[];
  evidence_completeness: string;
  evidence_completeness_score: number | null;
  external_id: string;
  canonical_url: string;
  author: string | null;
  author_handle: string | null;
  author_verified: boolean | null;
  title: string | null;
  text: string;
  relevant_snippet: string;
  highlight_ranges: Array<{ start: number; end: number }>;
  semantic_only_match: boolean;
  published_at: string | null;
  fetched_at: string;
  language: string;
  hashtags: string[] | null;
  mentions: string[] | null;
  media_type: string | null;
  like_count: number | null;
  view_count: number | null;
  comment_count: number | null;
  share_count: number | null;
  repost_count: number | null;
  reaction_count: number | null;
  raw_metrics: Record<string, string | number | boolean | null>;
  normalized_engagement: number;
  social_reach: number | null;
  score: number;
  matched_terms: string[];
  duplicate_group_id: string | null;
  duplicate_count: number;
  related_sources: string[];
  cluster_id: string | null;
  explanation: ScoreExplanation;
}

export interface ClusterSummary {
  id: string;
  representative_title: string;
  member_count: number;
  source_distribution: Record<string, number>;
  platform_presence: Record<string, number>;
  platform_diversity: number;
  first_seen_by_mirsad: string | null;
  earliest_at: string | null;
  latest_at: string | null;
  aggregate_score: number;
  terms: string[];
  member_ids: string[];
}

export interface AnalyticsSnapshot {
  total_results: number;
  unique_results: number;
  source_count: number;
  duplicate_count: number;
  average_score: number;
  search_duration_ms: number;
  mentions_over_time: Array<{ timestamp: string; count: number }>;
  trend_percent: number;
  overall_trend_percent: number;
  social_mentions_over_time: Array<{ timestamp: string; count: number }>;
  social_trend_percent: number;
  news_mentions_over_time: Array<{ timestamp: string; count: number }>;
  news_trend_percent: number;
  platform_distribution: Record<string, number>;
  social_source_distribution: Record<string, number>;
  most_active_platforms: Array<{ source: string; count: number }>;
  most_engaged_results: Array<{
    id: string;
    source: string;
    title: string | null;
    engagement: number;
    social_reach: number | null;
  }>;
  top_hashtags: Array<{ term: string; count: number }>;
  top_mentioned_accounts: Array<{ term: string; count: number }>;
  platform_diversity: number;
  category_distribution: Record<string, number>;
  average_social_reach: number | null;
  top_related_terms: Array<{ term: string; count: number }>;
  language_distribution: Record<string, number>;
  publication_time_distribution: Record<string, number>;
  score_distribution: Record<string, number>;
  cluster_distribution: Record<string, number>;
  bucket: string;
  scope?: "all" | "session" | "24h" | "7d" | "30d";
  scope_since?: string | null;
  scope_session_id?: string;
  scope_query?: string | null;
  scope_started_at?: string;
  content_record_count?: number;
  unique_canonical_count?: number;
  search_appearance_count?: number;
  duplicate_group_count?: number;
  cluster_count?: number;
  scored_record_count?: number;
  search_session_count?: number;
}

export interface SearchResponse {
  session: SearchSummary;
  results: SearchResultItem[];
  clusters: ClusterSummary[];
  analytics: AnalyticsSnapshot;
}

export interface SourceStatus {
  key: string;
  name: string;
  kind: string;
  category: "social" | "news" | "developer_community";
  support_level:
    "supported" | "supported_with_credentials" | "restricted_access";
  coverage_label: string | null;
  capabilities: ConnectorCapabilities;
  configuration_state: "configured" | "unconfigured" | "restricted";
  active_acquisition_mode: string;
  enabled: boolean;
  configured: boolean;
  status: string;
  detail: string | null;
  confidence: number;
  last_checked_at: string | null;
  last_success_at: string | null;
  recent_failure: string | null;
  failure_category: string | null;
  http_status: number | null;
  average_latency_ms: number;
  last_latency_ms: number;
  last_result_count: number;
  last_normalized_count: number;
  last_malformed_count: number;
  request_count: number;
  failure_count: number;
  configuration: { scopes?: string[]; credential_status?: string };
}

export interface ConnectorCapabilities {
  keyword_search: boolean | "conditional";
  phrase_search: boolean | "conditional";
  hashtag_search: boolean | "conditional";
  author_search: boolean | "conditional";
  recent_search: boolean | "conditional";
  historical_search: boolean | "conditional";
  language_filter: boolean | "conditional";
  date_filter: boolean | "conditional";
  public_posts: boolean | "conditional";
  comments: boolean | "conditional";
  engagement_metrics: boolean | "conditional";
  pagination: boolean | "conditional";
  requires_credentials: boolean;
  requires_approval: boolean;
  paid_access: boolean | "conditional";
  public_timeline: boolean | "conditional";
  hashtag_timeline: boolean | "conditional";
  authenticated_fulltext_search: boolean | "conditional";
  instance_scoped: boolean | "conditional";
  content_types: string[];
  search_modes: string[];
  sort_modes: string[];
  acquisition_modes: string[];
  web_index_search: boolean | "conditional";
  official_embed: boolean | "conditional";
  historical_index: boolean | "conditional";
  full_text_search?: boolean | "conditional";
  identifier_search?: boolean | "conditional";
}

export interface SettingValue {
  key: string;
  value: unknown;
  category: string;
}

export interface SystemStatus {
  api_status: string;
  database_status: string;
  fts_status: string;
  connector_status: Record<string, number>;
  record_count: number;
  index_count: number;
  database_integrity: string;
  foreign_key_violations: number;
  capabilities: string[];
  version: string;
}

export interface OutcomeEvent {
  id: number;
  event_type: string;
  search_session_id: string | null;
  content_id: string | null;
  query_class: string;
  rank: number | null;
  source: string | null;
  acquisition_mode: string | null;
  explicit_judgment: string | null;
  created_at: string;
}

export interface QualitySummary {
  search_count: number;
  zero_result_count: number;
  zero_result_rate: number;
  explicit_relevant: number;
  explicit_not_relevant: number;
  query_class_distribution: Record<string, number>;
  language_distribution: Record<string, number>;
  source_utility: Array<{
    query_class: string;
    source: string;
    observations: number;
    explicit_judgments: number;
    adjustment: number;
    reasons: string[];
  }>;
  engine_utility: Array<Record<string, string | number | boolean>>;
  average_rounds: number;
  stop_reasons: Record<string, number>;
  uncertainty_distribution: Record<string, number>;
  average_latency_ms: number;
  average_request_count: number;
  shadow_comparisons: Record<string, number>;
  configuration_snapshots: Array<{
    id: string;
    slot: string;
    reason: string;
    created_at: string;
    configuration: Record<string, string>;
  }>;
}

export interface SearchDiagnostics {
  session_id: string;
  diagnostics: {
    query?: {
      original: string;
      normalized: string;
      variants: string[];
      variant_details?: Array<{ variant: string; reason: string }>;
      tokens: string[];
      token_sequence?: string[];
      exact_phrase: boolean;
      intent?: string;
    };
    selected_sources?: string[];
    connector_total_latency_ms?: number;
    connectors?: Array<{
      source: string;
      status: string;
      http_status: number | null;
      latency_ms: number;
      total_connector_latency_ms?: number;
      fetched_results?: number;
      schema_valid_results?: number;
      query_matching_results?: number;
      time_eligible_results?: number;
      final_matching_results?: number;
      collected_results?: number;
      candidate_admitted_results?: number;
      final_top_results?: number;
      completion_position?: number;
      raw_results: number;
      normalized_results: number;
      malformed_records: number;
      attempt_count?: number;
      attempt_latencies_ms?: number[];
      circuit_breaker_state?: string;
      error_category: string | null;
      mode?: string | null;
      instances?: string[] | null;
      instance_results?: Array<{
        instance: string;
        state: string;
        http_status: number | null;
        fetched: number;
        latency_ms: number;
        error_category: string | null;
      }> | null;
      local_query_matches?: number;
      duplicates?: number;
      acquisition_mode?: string | null;
      cache_state?: string | null;
      historical_state?: string | null;
      engine_telemetry?: Array<{
        engine: string;
        query_variant_id: string;
        target_platform: string;
        latency_ms: number | null;
        returned_result_count: number;
        target_domain_result_count: number;
        accepted_canonical_result_count: number;
        duplicate_count: number;
        timeout: boolean;
        rate_limited: boolean;
        error: string | null;
        current_state?: string;
        cooldown_remaining_seconds?: number;
        historical_performance?: Record<string, number | string>;
      }> | null;
    }>;
    connector_completion_order?: string[];
    candidate_admission?: {
      per_source_limit: number;
      matched_per_source: Record<string, number>;
      admitted_per_source: Record<string, number>;
      final_top_per_source: Record<string, number>;
      admitted_total: number;
      final_global_cap: number;
      relevance_distribution_by_source: Record<
        string,
        Record<string, number>
      >;
    };
    duplicates_detected?: number;
    final_unique_result_count?: number;
    phase_timings_ms?: Record<string, number>;
    score_component_distributions?: Record<string, Record<string, number>>;
    mafer?: {
      intent_fingerprint?: {
        labels: string[];
        evidence: Array<{
          label: string;
          confidence: number;
          reasons: string[];
        }>;
      };
      temporal_intent?: string;
      query_lattice?: {
        variants: Array<{
          variant_id: string;
          text: string;
          transformation: string;
          confidence: number;
          drift_risk: number;
          round_created: number;
          reason: string;
        }>;
      };
      resource_plan?: {
        rounds: string[][];
        resources: Array<{
          source: string;
          long_term_utility: number;
          current_availability: number;
          total: number;
          reasons: string[];
        }>;
      };
      rounds?: Array<{
        round: number;
        kind: string;
        sources?: string[];
        candidate_gain?: number;
        uncertainty?: { level: string; reasons: string[] };
        marginal_evidence_gain?: { gain: number; reasons: string[] };
        decision?: string;
      }>;
      stop_reason?: string;
      requests_used?: number;
    };
  };
}

export interface SavedSearch {
  id: string;
  name: string;
  configuration: SearchRequest;
  created_at: string;
  updated_at: string;
}

export interface Bookmark {
  id: string;
  content_id: string;
  source: string;
  source_type: string;
  author: string | null;
  title: string | null;
  published_at: string | null;
  canonical_url: string;
  search_session_id: string | null;
  discovered_query: string | null;
  note: string;
  created_at: string;
  updated_at: string;
}

export interface DuplicateMember {
  id: string;
  source: string;
  source_type: string;
  author: string | null;
  title: string | null;
  text: string;
  canonical_url: string;
  published_at: string | null;
  engagement: number;
  similarity: number;
  match_stage: string;
  representative: boolean;
}

export interface DuplicateGroup {
  id: string;
  source_count: number;
  source_names: string[];
  record_count: number;
  earliest_seen: string | null;
  latest_seen: string | null;
  representative_id: string | null;
  members: DuplicateMember[];
}

export interface DataCounts {
  search_sessions: number;
  content_items: number;
  bookmarks: number;
  saved_searches: number;
  cached_responses: number;
  indexed_records: number;
}

export interface DataActionResult {
  action: string;
  affected: number;
  counts: DataCounts;
}

export interface CompareResponse {
  left: SearchSummary;
  right: SearchSummary;
  left_analytics: AnalyticsSnapshot;
  right_analytics: AnalyticsSnapshot;
  collection_window_warning: boolean;
}
