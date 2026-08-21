import type { TranslationKey } from "@/lib/i18n";
import type { SourceStatus } from "@/types/api";

type Translate = (key: TranslationKey) => string;

const coverageKeys: Record<string, TranslationKey> = {
  x: "source.coverage.x",
  threads: "source.coverage.threads",
  telegram: "source.coverage.telegram",
  reddit: "source.coverage.reddit",
  youtube: "source.coverage.youtube",
  bluesky: "source.coverage.bluesky",
  mastodon: "source.coverage.mastodon",
  instagram: "source.coverage.instagram",
  tiktok: "source.coverage.tiktok",
  facebook: "source.coverage.facebook",
  linkedin: "source.coverage.linkedin",
  gdelt: "source.coverage.gdelt",
  rss: "source.coverage.rss",
  github: "source.coverage.github",
  hacker_news: "source.coverage.hacker_news",
  mock: "source.coverage.mock",
};

const detailKeys: Record<string, TranslationKey> = {
  x: "source.detail.x",
  threads: "source.detail.threads",
  telegram: "source.detail.telegram",
  reddit: "source.detail.reddit",
  youtube: "source.detail.youtube",
  bluesky: "source.detail.bluesky",
  mastodon: "source.detail.mastodon",
  instagram: "source.detail.instagram",
  tiktok: "source.detail.tiktok",
  facebook: "source.detail.facebook",
  linkedin: "source.detail.linkedin",
  gdelt: "source.detail.gdelt",
  rss: "source.detail.rss",
  github: "source.detail.github",
  hacker_news: "source.detail.hacker_news",
  mock: "source.detail.mock",
};

const errorKeys: Record<string, TranslationKey> = {
  timeout: "status.timeout",
  dns_network: "status.dns_network",
  http_401: "status.http_401",
  http_403: "status.http_403",
  http_404: "status.http_404",
  http_error: "status.http_error",
  rate_limited: "status.rate_limited",
  quota_exhausted: "status.quota_exhausted",
  access_limited: "status.access_limited",
  invalid_credentials: "status.invalid_credentials",
  configuration_missing: "status.configuration_missing",
  unconfigured: "status.unconfigured",
  restricted_access: "status.restricted_access",
  capability_restricted: "status.capability_restricted",
  upstream_5xx: "status.upstream_5xx",
  upstream_engines_unavailable: "status.upstream_engines_unavailable",
  invalid_payload: "status.invalid_payload",
  circuit_open: "status.circuit_open",
  connector_error: "status.connector_error",
  auth_required: "status.auth_required",
  external_limit: "status.external_limit",
};

export function sourceCoverage(source: SourceStatus, t: Translate): string {
  if (source.active_acquisition_mode === "WEB_INDEX")
    return t("source.coverage.webIndexed");
  const key = coverageKeys[source.key];
  return key ? t(key) : source.coverage_label || source.name;
}

export function sourceDetail(source: SourceStatus, t: Translate): string {
  if (source.status === "web_discovery_disabled")
    return t("source.detail.webDiscoveryDisabled");
  if (source.active_acquisition_mode === "WEB_INDEX")
    return t("source.detail.webIndexed");
  const key = detailKeys[source.key];
  return key ? t(key) : source.detail || sourceCoverage(source, t);
}

export function connectorFailure(
  code: string | null | undefined,
  fallback: string | null | undefined,
  locale: "en" | "ar",
  t: Translate,
  sourceKey?: string,
): string {
  if (
    sourceKey &&
    detailKeys[sourceKey] &&
    code &&
    ["configuration_missing", "unconfigured", "restricted_access"].includes(
      code,
    )
  ) {
    return t(detailKeys[sourceKey]);
  }
  const key = code ? errorKeys[code] : undefined;
  if (key) return t(key);
  if (locale === "en" && fallback) return fallback;
  return t("sources.failureReported");
}
