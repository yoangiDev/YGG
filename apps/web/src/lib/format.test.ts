import { describe, expect, it } from "vitest";

import {
  asPercent,
  dateInputToUnix,
  formatDuration,
  formatMetric,
  formatPercent,
  formatSigned,
  timeAgo,
  toDateInput,
} from "./format";

describe("format", () => {
  it("formats signed differentials", () => {
    expect(formatSigned(150)).toBe("+150");
    expect(formatSigned(-35)).toBe("−35");
    expect(formatSigned(0)).toBe("0");
    expect(formatSigned(0.04, 1)).toBe("0");
    expect(formatSigned(2.456, 1)).toBe("+2.5");
  });

  it("formats durations and percentages", () => {
    expect(formatDuration(1845)).toBe("30:45");
    expect(formatDuration(59)).toBe("0:59");
    expect(formatPercent(66.666)).toBe("66.7%");
  });

  it("describes elapsed time", () => {
    const now = new Date("2026-09-11T12:00:00Z");
    expect(timeAgo("2026-09-11T11:59:30Z", now)).toBe("just now");
    expect(timeAgo("2026-09-11T09:00:00Z", now)).toBe("3h ago");
    expect(timeAgo("2026-09-08T12:00:00Z", now)).toBe("3d ago");
  });

  it("converts date inputs to unix seconds in UTC", () => {
    expect(dateInputToUnix("2026-09-01")).toBe(Date.UTC(2026, 8, 1) / 1000);
    expect(dateInputToUnix("2026-09-01", true) - dateInputToUnix("2026-09-01")).toBe(86_399);
    expect(toDateInput(new Date(Date.UTC(2026, 8, 1)))).toBe("2026-09-01");
    expect(() => dateInputToUnix("not-a-date")).toThrow();
  });

  it("formats metrics with their unit", () => {
    expect(formatMetric(62.456, "%")).toBe("62.5%");
    expect(formatMetric(1845, "s")).toBe("30:45");
    expect(formatMetric(7.456)).toBe("7.46");
    expect(formatMetric(15.26)).toBe("15.3");
    expect(formatMetric(1234.5, "gold")).toBe("1,235 gold");
  });

  it("normalizes ratios to percentages", () => {
    expect(asPercent(0.62)).toBeCloseTo(62);
    expect(asPercent(62)).toBe(62);
  });
});
