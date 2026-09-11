import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MetricGrid } from "./MetricGrid";

describe("MetricGrid", () => {
  it("renders each metric with its semantic colour and target", () => {
    render(
      <MetricGrid
        metrics={[
          { key: "kill_participation", label: "Kill participation", value: 64.25, status: "excellent", threshold: 60, unit: "%" },
          { key: "deaths", label: "Deaths", value: 6.2, status: "bad", threshold: 4, unit: "" },
          { key: "cs_per_min", label: "CS per minute", value: 6.1, status: "normal", threshold: 7, unit: "" },
        ]}
      />,
    );

    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(3);

    const [kp, deaths, cs] = items as [HTMLElement, HTMLElement, HTMLElement];
    expect(within(kp).getByText("64.3%")).toHaveClass("text-stat-gold");
    expect(within(kp).getByText("target ≥ 60%")).toBeInTheDocument();

    // En las muertes, "bad" es rojo y el objetivo es un máximo.
    expect(within(deaths).getByText("6.2")).toHaveClass("text-stat-red");
    expect(within(deaths).getByText("Needs work")).toBeInTheDocument();
    expect(within(deaths).getByText("target ≤ 4")).toBeInTheDocument();

    expect(within(cs).getByText("6.1")).toHaveClass("text-stat-green");
    expect(within(cs).getByText("Average")).toBeInTheDocument();
  });
});
