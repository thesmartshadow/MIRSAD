import { Copy, Pencil, Play, Trash2 } from "lucide-react";
import { startTransition, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import {
  EmptyState,
  ErrorState,
  PageHeader,
  PageSkeleton,
} from "@/components/shared/page";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { useI18n } from "@/lib/i18n";
import { useSearchState } from "@/lib/search-state";
import type { SavedSearch } from "@/types/api";

export function SavedSearchesPage() {
  const { locale, t } = useI18n();
  const { setCurrentSearch } = useSearchState();
  const navigate = useNavigate();
  const [items, setItems] = useState<SavedSearch[]>([]);
  const [editing, setEditing] = useState<SavedSearch | null>(null);
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = () => {
    setLoading(true);
    api
      .getSavedSearches()
      .then(setItems)
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setLoading(false));
  };
  useEffect(load, []);

  const run = async (item: SavedSearch) => {
    setLoading(true);
    try {
      const response = await api.runSavedSearch(item.id);
      startTransition(() => setCurrentSearch(response));
      navigate(`/search/${response.session.id}`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t("state.error"));
      setLoading(false);
    }
  };
  const rename = async () => {
    if (!editing || !name.trim()) return;
    const updated = await api.renameSavedSearch(editing.id, name.trim());
    setItems((current) =>
      current.map((item) => (item.id === updated.id ? updated : item)),
    );
    setEditing(null);
  };

  return (
    <div>
      <PageHeader
        title={t("saved.title")}
        description={t("saved.description")}
      />
      {loading && items.length === 0 ? (
        <PageSkeleton />
      ) : error ? (
        <ErrorState message={error} onRetry={load} />
      ) : items.length === 0 ? (
        <EmptyState title={t("saved.title")} description={t("saved.empty")} />
      ) : (
        <Card className="overflow-hidden py-0 shadow-none">
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("saved.name")}</TableHead>
                  <TableHead>{t("search.keyword")}</TableHead>
                  <TableHead>{t("saved.configuration")}</TableHead>
                  <TableHead>{t("history.date")}</TableHead>
                  <TableHead className="text-end">{t("action.open")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell className="font-medium" dir="auto">
                      {item.name}
                    </TableCell>
                    <TableCell dir="auto">{item.configuration.query}</TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1">
                        <Badge variant="outline">
                          {item.configuration.time_range}
                        </Badge>
                        <Badge variant="outline">
                          {item.configuration.language}
                        </Badge>
                        <Badge variant="outline">
                          {item.configuration.sort}
                        </Badge>
                        {item.configuration.exact_phrase && (
                          <Badge>{t("search.exact")}</Badge>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="whitespace-nowrap text-xs">
                      {formatDate(item.updated_at, locale)}
                    </TableCell>
                    <TableCell>
                      <div className="flex justify-end gap-1">
                        <Button
                          size="icon-sm"
                          variant="ghost"
                          aria-label={t("action.runAgain")}
                          onClick={() => run(item)}
                        >
                          <Play />
                        </Button>
                        <Button
                          size="icon-sm"
                          variant="ghost"
                          aria-label={t("action.rename")}
                          onClick={() => {
                            setEditing(item);
                            setName(item.name);
                          }}
                        >
                          <Pencil />
                        </Button>
                        <Button
                          size="icon-sm"
                          variant="ghost"
                          aria-label={t("action.duplicate")}
                          onClick={async () => {
                            const duplicate = await api.duplicateSavedSearch(
                              item.id,
                            );
                            setItems((current) => [duplicate, ...current]);
                          }}
                        >
                          <Copy />
                        </Button>
                        <Button
                          size="icon-sm"
                          variant="ghost"
                          aria-label={t("action.delete")}
                          onClick={async () => {
                            await api.deleteSavedSearch(item.id);
                            setItems((current) =>
                              current.filter((value) => value.id !== item.id),
                            );
                          }}
                        >
                          <Trash2 />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </Card>
      )}
      <Dialog
        open={Boolean(editing)}
        onOpenChange={(open) => !open && setEditing(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("action.rename")}</DialogTitle>
            <DialogDescription>{t("saved.description")}</DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <Label htmlFor="saved-name">{t("saved.name")}</Label>
            <Input
              id="saved-name"
              value={name}
              maxLength={120}
              onChange={(event) => setName(event.target.value)}
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditing(null)}>
              {t("action.cancel")}
            </Button>
            <Button onClick={rename} disabled={!name.trim()}>
              {t("action.save")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
