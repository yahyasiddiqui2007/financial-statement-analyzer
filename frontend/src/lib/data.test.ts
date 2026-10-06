import type { Financials } from "../api/types";
import fixture from "../test/fixtures/financials_example.json";
import { chartRows, findMetric, isEmptyRow } from "./data";
import { shortPeriodLabel, visibleIndexes } from "./periods";
import { lineItemTone, metricTone } from "./tone";

const data = fixture as unknown as Financials;

describe("visibleIndexes", () => {
  it("returns the most recent N periods, oldest first", () => {
    expect(visibleIndexes(19, 5)).toEqual([14, 15, 16, 17, 18]);
    expect(visibleIndexes(3, 10)).toEqual([0, 1, 2]);
    expect(visibleIndexes(3, "all")).toEqual([0, 1, 2]);
  });
});

describe("shortPeriodLabel", () => {
  it("uses the company's fiscal year label when known", () => {
    expect(shortPeriodLabel(data.periods[2]!)).toBe("FY2025");
  });
  it("falls back to the end date instead of guessing a fiscal year", () => {
    expect(shortPeriodLabel(data.periods[0]!)).toBe("YE Jun 2023");
  });
});

describe("chartRows", () => {
  it("reads values straight from the pipeline response", () => {
    const rows = chartRows(data, [0, 1, 2], [
      { key: "revenue", label: "Revenue", source: "item" },
      { key: "gross_margin", label: "Gross", source: "metric" },
    ]);
    expect(rows.map((r) => r.revenue)).toEqual([800000000, 1000000000, 1200000000]);
    expect(rows[2]!.gross_margin).toBe(0.425);
    expect(rows[2]!.period).toBe("FY2025");
  });
  it("keeps missing values as null so charts show a gap, not zero", () => {
    const rows = chartRows(data, [2], [{ key: "inventory", label: "Inventory", source: "item" }]);
    expect(rows[0]!.inventory).toBeNull();
  });
});

describe("isEmptyRow", () => {
  it("detects line items never reported in the visible years", () => {
    const balance = data.statements.find((s) => s.id === "balance_sheet")!;
    expect(isEmptyRow(balance.rows.find((r) => r.item === "inventory")!, [0, 1, 2])).toBe(true);
    expect(isEmptyRow(balance.rows.find((r) => r.item === "total_assets")!, [0, 1, 2])).toBe(false);
  });
});

describe("tone", () => {
  it("treats rising revenue as good and rising debt as bad", () => {
    expect(lineItemTone("revenue", 1)).toBe("positive");
    expect(lineItemTone("total_debt", 1)).toBe("negative");
    expect(lineItemTone("inventory", 1)).toBe("neutral");
    expect(metricTone("debt_to_equity", -1)).toBe("positive");
    expect(metricTone("gross_margin", 0)).toBe("neutral");
  });
  it("finds metrics", () => {
    expect(findMetric(data, "fcf_margin")?.format).toBe("percent");
  });
});
