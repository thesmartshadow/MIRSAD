import {
  connectorFailure,
  sourceCoverage,
  sourceDetail,
} from "@/lib/source-presentation";
import type { TranslationKey } from "@/lib/i18n";
import type { SourceStatus } from "@/types/api";

const source = {
  key: "telegram",
  name: "Telegram",
  coverage_label:
    "Public Channels only; requires a locally authorized user session",
  detail: "API ID, API hash, and session are required",
} as SourceStatus;

const arabic = (key: TranslationKey) => `AR:${key}`;

describe("connector presentation localization", () => {
  it("uses source keys rather than backend English prose", () => {
    expect(sourceCoverage(source, arabic)).toBe("AR:source.coverage.telegram");
    expect(sourceDetail(source, arabic)).toBe("AR:source.detail.telegram");
  });

  it("uses machine-readable failure categories in Arabic", () => {
    expect(
      connectorFailure(
        "http_403",
        "Source access is unavailable",
        "ar",
        arabic,
      ),
    ).toBe("AR:status.http_403");
    expect(
      connectorFailure("future_error", "English prose", "ar", arabic),
    ).toBe("AR:sources.failureReported");
  });

  it("uses acquisition metadata for indexed web coverage", () => {
    const indexed = {
      ...source,
      key: "x",
      active_acquisition_mode: "WEB_INDEX",
    } as SourceStatus;

    expect(sourceCoverage(indexed, arabic)).toBe(
      "AR:source.coverage.webIndexed",
    );
    expect(sourceDetail(indexed, arabic)).toBe("AR:source.detail.webIndexed");
  });
});
