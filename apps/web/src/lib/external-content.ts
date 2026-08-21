const HTML_TAGS = /<[^>]*>/g;

function removeUnsafeControls(value: string): string {
  return [...value]
    .filter((character) => {
      const code = character.codePointAt(0) ?? 0;
      return !(
        code <= 8 ||
        code === 11 ||
        code === 12 ||
        (code >= 14 && code <= 31) ||
        code === 127 ||
        (code >= 0x202a && code <= 0x202e) ||
        (code >= 0x2066 && code <= 0x2069)
      );
    })
    .join("");
}

export function displayText(value: string | null | undefined): string {
  return removeUnsafeControls(value ?? "")
    .normalize("NFKC")
    .replace(HTML_TAGS, " ")
    .replace(/\s+/g, " ")
    .trim();
}

export function safeExternalUrl(value: string): string | null {
  try {
    const parsed = new URL(value);
    return parsed.protocol === "http:" || parsed.protocol === "https:"
      ? parsed.href
      : null;
  } catch {
    return null;
  }
}
