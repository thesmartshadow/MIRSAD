import { Database, RefreshCw, RotateCcw, Save, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ErrorState, PageHeader, PageSkeleton } from "@/components/shared/page";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useTheme } from "@/lib/theme";
import type { SettingValue } from "@/types/api";
import type { DataCounts } from "@/types/api";

const rankingKeys = [
  ["ranking.relevance", "score.relevance"],
  ["ranking.freshness", "score.freshness"],
  ["ranking.engagement", "score.engagement"],
  ["ranking.source_confidence", "score.confidence"],
  ["ranking.cross_source_presence", "score.presence"],
  ["ranking.novelty", "score.novelty"],
] as const;

const dataActionLabels = {
  clear_history: "settings.clearHistory",
  clear_bookmarks: "settings.clearBookmarks",
  clear_cache: "settings.clearCache",
  rebuild_fts: "settings.rebuildFts",
  reset_database: "settings.resetDatabase",
} as const;
type DataAction = keyof typeof dataActionLabels;

export function SettingsPage() {
  const { locale, setLocale, t } = useI18n();
  const { theme, setTheme } = useTheme();
  const navigate = useNavigate();
  const [settings, setSettings] = useState<Record<string, unknown>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [counts, setCounts] = useState<DataCounts | null>(null);
  const [pendingAction, setPendingAction] = useState<DataAction | null>(null);

  const apply = (items: SettingValue[]) =>
    setSettings(
      Object.fromEntries(items.map((item) => [item.key, item.value])),
    );
  const load = () => {
    setLoading(true);
    api
      .getSettings()
      .then(apply)
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setLoading(false));
  };
  useEffect(load, []);
  useEffect(() => {
    api
      .getDataCounts()
      .then(setCounts)
      .catch(() => undefined);
  }, []);
  const update = (key: string, value: unknown) =>
    setSettings((current) => ({ ...current, [key]: value }));
  const weightTotal = rankingKeys.reduce(
    (total, [key]) => total + Number(settings[key] ?? 0),
    0,
  );

  const save = async () => {
    if (Math.abs(weightTotal - 1) > 0.0001) {
      setError(t("settings.weightNotice"));
      return;
    }
    setLoading(true);
    setError("");
    try {
      apply(await api.updateSettings(settings));
      setNotice(t("settings.saved"));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t("state.error"));
    } finally {
      setLoading(false);
    }
  };
  const reset = async () => {
    setLoading(true);
    setError("");
    try {
      apply(await api.resetSettings());
      setNotice(t("settings.reset"));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t("state.error"));
    } finally {
      setLoading(false);
    }
  };

  if (loading && Object.keys(settings).length === 0)
    return (
      <>
        <PageHeader
          title={t("settings.title")}
          description={t("settings.description")}
        />
        <PageSkeleton />
      </>
    );
  return (
    <div className="instrument-page instrument-page--settings">
      <PageHeader
        title={t("settings.title")}
        description={t("settings.description")}
        actions={
          <>
            <Button
              variant="outline"
              size="sm"
              onClick={reset}
              disabled={loading}
            >
              <RotateCcw />
              {t("action.reset")}
            </Button>
            <Button
              size="sm"
              onClick={save}
              disabled={loading || Math.abs(weightTotal - 1) > 0.0001}
            >
              <Save />
              {t("action.save")}
            </Button>
          </>
        }
      />
      {error && (
        <div className="mb-4">
          <ErrorState message={error} />
        </div>
      )}
      {notice && (
        <Alert className="mb-4 border-chart-4/40 bg-chart-4/5">
          <AlertDescription>{notice}</AlertDescription>
        </Alert>
      )}
      <Tabs
        defaultValue="general"
        orientation="vertical"
        className="settings-layout"
      >
        <TabsList
          className="settings-sections"
          variant="line"
        >
          {(
            [
              "general",
              "search",
              "ranking",
              "sources",
              "language",
              "appearance",
              "data",
            ] as const
          ).map((category) => (
            <TabsTrigger key={category} value={category}>
              {t(`settings.${category}`)}
            </TabsTrigger>
          ))}
        </TabsList>
        <div className="settings-content">
          <TabsContent value="general">
            <SettingCard>
              <SettingRow label={t("settings.defaultLimit")}>
                <Select
                  value={String(settings["general.default_result_limit"] ?? 50)}
                  onValueChange={(value) =>
                    update("general.default_result_limit", Number(value))
                  }
                >
                  <SelectTrigger
                    className="w-32"
                    aria-label={t("settings.defaultLimit")}
                  >
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {[25, 50, 100, 200].map((value) => (
                      <SelectItem key={value} value={String(value)}>
                        {value}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </SettingRow>
              <p className="text-sm text-muted-foreground">
                {t("settings.localOnly")}
              </p>
            </SettingCard>
          </TabsContent>
          <TabsContent value="search">
            <SettingCard>
              <SettingRow label={t("settings.defaultTime")}>
                <Select
                  value={String(settings["search.default_time_range"] ?? "7d")}
                  onValueChange={(value) =>
                    update("search.default_time_range", value)
                  }
                >
                  <SelectTrigger
                    className="w-44"
                    aria-label={t("settings.defaultTime")}
                  >
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="24h">{t("search.day")}</SelectItem>
                    <SelectItem value="7d">{t("search.week")}</SelectItem>
                    <SelectItem value="30d">{t("search.month")}</SelectItem>
                    <SelectItem value="all">{t("search.allTime")}</SelectItem>
                  </SelectContent>
                </Select>
              </SettingRow>
            </SettingCard>
          </TabsContent>
          <TabsContent value="ranking">
            <SettingCard>
              <div className="mb-4 flex items-center justify-between border-b pb-3 text-sm">
                <span>{t("settings.weightNotice")}</span>
                <strong
                  className={
                    Math.abs(weightTotal - 1) < 0.0001
                      ? "text-chart-4"
                      : "text-destructive"
                  }
                >
                  {t("settings.weightTotal")}: {weightTotal.toFixed(2)}
                </strong>
              </div>
              {rankingKeys.map(([key, label]) => (
                <div
                  key={key}
                  className="grid grid-cols-[minmax(130px,0.7fr)_1fr_44px] items-center gap-4 border-b py-3 last:border-0"
                >
                  <span className="text-sm">{t(label)}</span>
                  <Slider
                    aria-label={t(label)}
                    value={[Number(settings[key] ?? 0) * 100]}
                    min={0}
                    max={100}
                    step={1}
                    onValueChange={(value) => {
                      const next = Array.isArray(value) ? value[0] : value;
                      update(key, next / 100);
                    }}
                  />
                  <span className="text-end text-xs tabular-nums">
                    {Number(settings[key] ?? 0).toFixed(2)}
                  </span>
                </div>
              ))}
            </SettingCard>
          </TabsContent>
          <TabsContent value="sources">
            <SettingCard>
              <p className="text-sm text-muted-foreground">
                {t("settings.sourceHelp")}
              </p>
              <Button variant="outline" onClick={() => navigate("/sources")}>
                {t("nav.sources")}
              </Button>
            </SettingCard>
          </TabsContent>
          <TabsContent value="language">
            <SettingCard>
              <SettingRow label={t("settings.language")}>
                <Select
                  value={locale}
                  onValueChange={(value) => {
                    const next = value === "ar" ? "ar" : "en";
                    setLocale(next);
                    update("language.default", next);
                  }}
                >
                  <SelectTrigger
                    className="w-40"
                    aria-label={t("settings.language")}
                  >
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="en">{t("common.english")}</SelectItem>
                    <SelectItem value="ar">{t("common.arabic")}</SelectItem>
                  </SelectContent>
                </Select>
              </SettingRow>
            </SettingCard>
          </TabsContent>
          <TabsContent value="appearance">
            <SettingCard>
              <SettingRow label={t("settings.appearance")}>
                <Select
                  value={theme}
                  onValueChange={(value) => {
                    const next =
                      value === "light" || value === "dark" ? value : "system";
                    setTheme(next);
                    update("appearance.theme", next);
                  }}
                >
                  <SelectTrigger
                    className="w-40"
                    aria-label={t("settings.appearance")}
                  >
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="light">{t("common.light")}</SelectItem>
                    <SelectItem value="dark">{t("common.dark")}</SelectItem>
                    <SelectItem value="system">{t("common.system")}</SelectItem>
                  </SelectContent>
                </Select>
              </SettingRow>
            </SettingCard>
          </TabsContent>
          <TabsContent value="data">
            <SettingCard>
              <SettingRow label={t("settings.retention")}>
                <Input
                  className="w-32"
                  type="number"
                  min={1}
                  max={3650}
                  value={Number(settings["data.retention_days"] ?? 90)}
                  onChange={(event) =>
                    update("data.retention_days", Number(event.target.value))
                  }
                />
              </SettingRow>
              <div>
                <h3 className="mb-2 text-sm font-medium">
                  {t("settings.recordCounts")}
                </h3>
                <div className="grid gap-2 sm:grid-cols-3">
                  {counts &&
                    Object.entries(counts).map(([key, value]) => (
                      <div key={key} className="rounded-md border p-2">
                        <div className="text-xs text-muted-foreground">
                          {key.replaceAll("_", " ")}
                        </div>
                        <div className="mt-1 font-semibold tabular-nums">
                          {new Intl.NumberFormat(
                            locale === "ar" ? "ar-IQ" : "en-GB",
                          ).format(value)}
                        </div>
                      </div>
                    ))}
                </div>
              </div>
              <div className="grid gap-2 sm:grid-cols-2">
                {(
                  [
                    ["clear_history", "settings.clearHistory", Trash2],
                    ["clear_bookmarks", "settings.clearBookmarks", Trash2],
                    ["clear_cache", "settings.clearCache", Trash2],
                    ["rebuild_fts", "settings.rebuildFts", RefreshCw],
                    ["reset_database", "settings.resetDatabase", Database],
                  ] as const
                ).map(([action, label, Icon]) => (
                  <Button
                    key={action}
                    variant={
                      action === "reset_database" ? "destructive" : "outline"
                    }
                    onClick={() => setPendingAction(action)}
                  >
                    <Icon />
                    {t(label)}
                  </Button>
                ))}
              </div>
            </SettingCard>
          </TabsContent>
        </div>
      </Tabs>
      <Dialog
        open={Boolean(pendingAction)}
        onOpenChange={(open) => !open && setPendingAction(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {pendingAction
                ? t(dataActionLabels[pendingAction])
                : t("settings.data")}
            </DialogTitle>
            <DialogDescription>{t("settings.confirmAction")}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPendingAction(null)}>
              {t("action.cancel")}
            </Button>
            <Button
              variant="destructive"
              onClick={async () => {
                if (!pendingAction) return;
                const result = await api.runDataAction(pendingAction);
                setCounts(result.counts);
                setPendingAction(null);
              }}
            >
              {t("action.confirm")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function SettingCard({ children }: { children: React.ReactNode }) {
  return <section className="settings-plane">{children}</section>;
}

function SettingRow({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="setting-row">
      <span className="text-sm font-medium">{label}</span>
      {children}
    </div>
  );
}
