import type { ReactNode } from "react";

export function HighlightedSnippet({
  text,
  ranges,
}: {
  text: string;
  ranges: Array<{ start: number; end: number }>;
}) {
  const nodes: ReactNode[] = [];
  let position = 0;
  ranges.forEach((range, index) => {
    const start = Math.max(position, Math.min(text.length, range.start));
    const end = Math.max(start, Math.min(text.length, range.end));
    if (start > position) nodes.push(text.slice(position, start));
    if (end > start) {
      nodes.push(
        <mark
          className="rounded-sm bg-amber-200/70 px-0.5 text-inherit dark:bg-amber-500/25"
          key={`${start}-${end}-${index}`}
        >
          {text.slice(start, end)}
        </mark>,
      );
    }
    position = end;
  });
  if (position < text.length) nodes.push(text.slice(position));
  return <>{nodes}</>;
}
