import { createContext, use, useState, type ReactNode } from "react";

import type { SearchResponse } from "@/types/api";

interface SearchStateValue {
  currentSearch: SearchResponse | null;
  setCurrentSearch: (search: SearchResponse | null) => void;
}

const SearchStateContext = createContext<SearchStateValue | null>(null);

export function SearchStateProvider({
  children,
  initialSearch = null,
}: {
  children: ReactNode;
  initialSearch?: SearchResponse | null;
}) {
  const [currentSearch, setCurrentSearch] = useState<SearchResponse | null>(
    initialSearch,
  );
  return (
    <SearchStateContext value={{ currentSearch, setCurrentSearch }}>
      {children}
    </SearchStateContext>
  );
}

export function useSearchState() {
  const value = use(SearchStateContext);
  if (!value)
    throw new Error("useSearchState must be used within SearchStateProvider");
  return value;
}
