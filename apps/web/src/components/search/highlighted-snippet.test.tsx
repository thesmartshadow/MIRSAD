import { render, screen } from "@testing-library/react";

import { HighlightedSnippet } from "@/components/search/highlighted-snippet";

describe("HighlightedSnippet", () => {
  it("renders retrieved markup as text and uses structured mark ranges", () => {
    const text = '<img src=x onerror="alert(1)"> public policy';
    const start = text.indexOf("public policy");
    const { container } = render(
      <p>
        <HighlightedSnippet
          text={text}
          ranges={[{ start, end: start + "public policy".length }]}
        />
      </p>,
    );
    expect(container.querySelector("img")).toBeNull();
    expect(screen.getByText(/<img src=x/)).toBeInTheDocument();
    expect(container.querySelector("mark")).toHaveTextContent("public policy");
  });
});
