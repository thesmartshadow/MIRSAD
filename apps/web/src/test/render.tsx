import { render, type RenderOptions } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";

import { I18nProvider } from "@/lib/i18n";
import { SearchStateProvider } from "@/lib/search-state";
import { ThemeProvider } from "@/lib/theme";
import type { SearchResponse } from "@/types/api";

function Providers({
  children,
  initialSearch,
}: {
  children: ReactNode;
  initialSearch?: SearchResponse;
}) {
  return (
    <ThemeProvider>
      <I18nProvider>
        <MemoryRouter>
          <SearchStateProvider initialSearch={initialSearch}>
            {children}
          </SearchStateProvider>
        </MemoryRouter>
      </I18nProvider>
    </ThemeProvider>
  );
}

export function renderWithProviders(
  ui: ReactElement,
  options?: RenderOptions & { initialSearch?: SearchResponse },
) {
  const { initialSearch, ...renderOptions } = options ?? {};
  return render(ui, {
    wrapper: ({ children }) => (
      <Providers initialSearch={initialSearch}>{children}</Providers>
    ),
    ...renderOptions,
  });
}
