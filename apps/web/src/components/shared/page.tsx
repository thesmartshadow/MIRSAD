import { AlertCircle, Inbox, LoaderCircle } from "lucide-react";
import type { ReactNode } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";
import { useI18n, type TranslationKey } from "@/lib/i18n";

const statusKeys: Record<string, TranslationKey> = {
  running: "status.running",
  completed: "status.completed",
  partial: "status.partial",
  failed: "status.failed",
  available: "status.available",
  operational: "status.operational",
  unavailable: "status.unavailable",
  degraded: "status.degraded",
  unconfigured: "status.unconfigured",
  disabled: "status.disabled",
  unknown: "status.unknown",
  healthy: "status.healthy",
  rate_limited: "status.rate_limited",
  restricted: "status.restricted",
  access_limited: "status.access_limited",
  quota_exhausted: "status.quota_exhausted",
  external_limit: "status.external_limit",
  web_discovery_disabled: "status.web_discovery_disabled",
  timeout: "status.timeout",
  invalid_credentials: "status.invalid_credentials",
  configuration_missing: "status.configuration_missing",
  http_401: "status.http_401",
  http_403: "status.http_403",
  http_404: "status.http_404",
  dns_network: "status.dns_network",
  upstream_5xx: "status.upstream_5xx",
  auth_required: "status.auth_required",
};

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description: string;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-5 flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
      <div>
        <h2 className="font-heading text-xl font-semibold tracking-tight">
          {title}
        </h2>
        <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
          {description}
        </p>
      </div>
      {actions && (
        <div className="flex shrink-0 flex-wrap justify-end gap-2">
          {actions}
        </div>
      )}
    </div>
  );
}

export function PageSkeleton({ rows = 4 }: { rows?: number }) {
  const { t } = useI18n();
  return (
    <div className="space-y-3" aria-label={t("state.loading")} role="status">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }, (_, index) => (
          <Skeleton key={index} className="h-24" />
        ))}
      </div>
      {Array.from({ length: rows }, (_, index) => (
        <Skeleton key={index} className="h-20" />
      ))}
    </div>
  );
}

export function ErrorState({
  message,
  onRetry,
}: {
  message?: string;
  onRetry?: () => void;
}) {
  const { t } = useI18n();
  return (
    <Alert variant="destructive">
      <AlertCircle />
      <AlertTitle>{t("state.error")}</AlertTitle>
      <AlertDescription className="flex items-center justify-between gap-4">
        <span>{message ?? t("state.error")}</span>
        {onRetry && (
          <Button variant="outline" size="sm" onClick={onRetry}>
            <LoaderCircle /> {t("action.retry")}
          </Button>
        )}
      </AlertDescription>
    </Alert>
  );
}

export function EmptyState({
  title,
  description,
}: {
  title?: string;
  description?: string;
}) {
  const { t } = useI18n();
  return (
    <Empty className="min-h-64 border">
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <Inbox />
        </EmptyMedia>
        <EmptyTitle>{title ?? t("state.noData")}</EmptyTitle>
        <EmptyDescription>{description ?? t("state.noData")}</EmptyDescription>
      </EmptyHeader>
    </Empty>
  );
}

export function StatusBadge({ status }: { status: string }) {
  const { t } = useI18n();
  const normalized = status.toLowerCase();
  const className =
    normalized === "completed" ||
    normalized === "available" ||
    normalized === "operational" ||
    normalized === "healthy"
      ? "border-chart-4/40 bg-chart-4/10 text-foreground"
      : normalized === "partial" ||
          normalized === "degraded" ||
          normalized === "rate_limited" ||
          normalized === "access_limited" ||
          normalized === "auth_required" ||
          normalized === "quota_exhausted" ||
          normalized === "external_limit"
        ? "border-chart-2/40 bg-chart-2/10 text-foreground"
        : normalized === "failed" ||
            normalized === "unavailable" ||
            normalized === "restricted"
          ? "border-destructive/50 bg-destructive/10 text-foreground"
          : "";
  return (
    <Badge variant="outline" className={className}>
      {statusKeys[normalized] ? t(statusKeys[normalized]) : status}
    </Badge>
  );
}
