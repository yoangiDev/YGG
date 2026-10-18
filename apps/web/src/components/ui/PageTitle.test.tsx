import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";

import { NotFound } from "@/app/RouteError";

import { PageHeader } from "./PageHeader";

describe("the tab title", () => {
  it("is set by the page headline, with its accent, and changes with the screen", () => {
    const { rerender } = render(<PageHeader title="Rank cutoffs" accent="Europe West" />);
    expect(document.title).toBe("Rank cutoffs Europe West · YGG");

    rerender(<PageHeader title="Administration" documentTitle="Administration · Users" />);
    expect(document.title).toBe("Administration · Users · YGG");
  });

  it("a «not found» screen has its headline and its title", () => {
    render(
      <MemoryRouter>
        <NotFound />
      </MemoryRouter>,
    );
    expect(screen.getByRole("heading", { level: 1, name: "Page not found" })).toBeInTheDocument();
    expect(document.title).toBe("Page not found · YGG");
  });
});
