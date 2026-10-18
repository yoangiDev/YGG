import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(() => vi.resetModules());

async function footer(legal: { operator: string; email: string }) {
  vi.doMock("./entity", async () => {
    const real = await vi.importActual<typeof import("./entity")>("./entity");
    return { ...real, LEGAL: { ...real.LEGAL, ...legal } };
  });
  const { SiteFooter } = await import("./SiteFooter");
  render(
    <MemoryRouter>
      <SiteFooter />
    </MemoryRouter>,
  );
}

describe("SiteFooter", () => {
  it("doesn't show the unfilled blanks: the copyright is YGG's and there is no contact link", async () => {
    await footer({ operator: "[Your full name]", email: "[contact@your-domain]" });
    expect(screen.getByText(/© \d{4} YGG\./)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Contact" })).not.toBeInTheDocument();
    expect(screen.queryByText(/\[Your full name\]/)).not.toBeInTheDocument();
  });

  it("with the details filled in it shows the name and the email", async () => {
    await footer({ operator: "Ada Lovelace", email: "ada@example.com" });
    expect(screen.getByText(/© \d{4} Ada Lovelace\./)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Contact" })).toHaveAttribute("href", "mailto:ada@example.com");
  });
});
