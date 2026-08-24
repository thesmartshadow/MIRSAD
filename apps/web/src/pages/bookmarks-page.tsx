import { ExternalLink, Save, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

import {
  EmptyState,
  ErrorState,
  PageHeader,
  PageSkeleton,
} from "@/components/shared/page";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { displayText, safeExternalUrl } from "@/lib/external-content";
import { formatDate } from "@/lib/format";
import { useI18n } from "@/lib/i18n";
import type { Bookmark } from "@/types/api";

export function BookmarksPage() {
  const { locale, t } = useI18n();
  const [items, setItems] = useState<Bookmark[]>([]);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const load = () => {
    api
      .getBookmarks()
      .then((values) => {
        setItems(values);
        setNotes(
          Object.fromEntries(values.map((item) => [item.id, item.note])),
        );
      })
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setLoading(false));
  };
  useEffect(load, []);
  return (
    <div className="instrument-page instrument-page--bookmarks">
      <PageHeader
        title={t("bookmarks.title")}
        description={t("bookmarks.description")}
      />
      {loading ? (
        <PageSkeleton />
      ) : error ? (
        <ErrorState message={error} onRetry={load} />
      ) : items.length === 0 ? (
        <EmptyState
          title={t("bookmarks.title")}
          description={t("bookmarks.empty")}
        />
      ) : (
        <ol className="collection-ledger">
          {items.map((item, index) => {
            const url = safeExternalUrl(item.canonical_url);
            return (
              <li key={item.id}>
              <Card className="collection-record shadow-none">
                <CardContent className="collection-record__body">
                  <div className="collection-record__identity">
                    <span className="collection-record__index" aria-hidden="true">{String(index + 1).padStart(2, "0")}</span>
                    <div className="min-w-0">
                      <div className="mb-1 flex flex-wrap gap-2">
                        <Badge variant="outline">{item.source}</Badge>
                        <Badge variant="secondary">{item.source_type}</Badge>
                      </div>
                      <h3 className="font-medium" dir="auto">
                        {displayText(item.title) || t("result.untitled")}
                      </h3>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {formatDate(item.published_at, locale)} ·{" "}
                        {item.discovered_query ? (
                          <span dir="auto">{item.discovered_query}</span>
                        ) : (
                          t("common.notAvailable")
                        )}
                      </p>
                    </div>
                  </div>
                  <label className="collection-record__note">
                    <span>{t("bookmarks.note")}</span>
                    <Textarea
                      aria-label={t("bookmarks.note")}
                      rows={2}
                      maxLength={1000}
                      value={notes[item.id] ?? ""}
                      onChange={(event) =>
                        setNotes((current) => ({
                          ...current,
                          [item.id]: event.target.value,
                        }))
                      }
                    />
                  </label>
                  <div className="collection-record__actions">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={async () => {
                        const updated = await api.updateBookmark(
                          item.id,
                          notes[item.id] ?? "",
                        );
                        setItems((current) =>
                          current.map((value) =>
                            value.id === updated.id ? updated : value,
                          ),
                        );
                      }}
                    >
                      <Save />
                      {t("action.save")}
                    </Button>
                    {url && (
                      <Button
                        nativeButton={false}
                        size="sm"
                        variant="ghost"
                        render={
                          <a
                            href={url}
                            target="_blank"
                            rel="noopener noreferrer"
                          />
                        }
                      >
                        <ExternalLink />
                        {t("action.open")}
                      </Button>
                    )}
                    <Button
                      size="icon-sm"
                      variant="ghost"
                      aria-label={t("action.delete")}
                      onClick={async () => {
                        await api.deleteBookmark(item.id);
                        setItems((current) =>
                          current.filter((value) => value.id !== item.id),
                        );
                      }}
                    >
                      <Trash2 />
                    </Button>
                  </div>
                </CardContent>
              </Card>
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
