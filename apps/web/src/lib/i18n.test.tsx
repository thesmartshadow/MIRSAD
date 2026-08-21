import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { I18nProvider, useI18n } from "@/lib/i18n";

function LocaleProbe() {
  const { setLocale, t } = useI18n();
  return <button onClick={() => setLocale("ar")}>{t("nav.search")}</button>;
}

describe("I18nProvider", () => {
  beforeEach(() => localStorage.clear());

  it("sets Arabic language and RTL direction at the root", async () => {
    render(
      <I18nProvider>
        <LocaleProbe />
      </I18nProvider>,
    );
    await userEvent.click(screen.getByRole("button", { name: "Search" }));
    await waitFor(() => {
      expect(document.documentElement).toHaveAttribute("lang", "ar");
      expect(document.documentElement).toHaveAttribute("dir", "rtl");
    });
    expect(screen.getByRole("button", { name: "البحث" })).toBeInTheDocument();
  });
});
