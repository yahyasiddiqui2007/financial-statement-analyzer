import {
  direction,
  formatAxisUsd,
  formatCompactUsd,
  formatDifference,
  formatMetric,
  formatMillions,
  formatPercent,
  formatPercentChange,
  formatRatio,
  formatTrendValue,
  toNumber,
} from "./format";

describe("toNumber", () => {
  it("keeps missing values missing, never zero", () => {
    expect(toNumber(null)).toBeNull();
    expect(toNumber(undefined)).toBeNull();
  });
  it("parses exact decimal strings", () => {
    expect(toNumber("391035000000")).toBe(391035000000);
    expect(toNumber("0.2022")).toBe(0.2022);
  });
  it("rejects non-numbers", () => {
    expect(toNumber("abc")).toBeNull();
  });
});

describe("formatMillions", () => {
  it.each([
    ["391035000000", "391,035"],
    ["-22354000000", "(22,354)"],
    ["0", "0"],
    ["12345678", "12.3"],
    ["-450000", "(0.45)"],
    [null, "—"],
  ])("%s → %s", (input, expected) => {
    expect(formatMillions(input)).toBe(expected);
  });
});

describe("formatCompactUsd", () => {
  it.each([
    ["391035000000", "$391.0B"],
    ["98767000000", "$98.8B"],
    ["512300000", "$512.3M"],
    ["2100000000000", "$2.1T"],
    ["-1200000000", "−$1.2B"],
    [null, "—"],
  ])("%s → %s", (input, expected) => {
    expect(formatCompactUsd(input)).toBe(expected);
  });
});

describe("percent and ratio formats", () => {
  it("formats percentages from fractions", () => {
    expect(formatPercent("0.4693")).toBe("46.9%");
    expect(formatPercent("-0.028")).toBe("−2.8%");
    expect(formatPercent("1.755")).toBe("175.5%");
  });
  it("never shows negative zero", () => {
    expect(formatPercent("-0.00001")).toBe("0.0%");
    expect(formatPercentChange("-0.00001")).toBe("0.0%");
  });
  it("formats ratios", () => {
    expect(formatRatio("0.8932")).toBe("0.89x");
    expect(formatRatio("2.371")).toBe("2.37x");
  });
  it("formats signed year-over-year changes", () => {
    expect(formatPercentChange("0.064")).toBe("+6.4%");
    expect(formatPercentChange("-0.0281")).toBe("−2.8%");
  });
  it("dispatches by metric format", () => {
    expect(formatMetric("0.25", "percent")).toBe("25.0%");
    expect(formatMetric("1.5", "ratio")).toBe("1.50x");
    expect(formatMetric("98767000000", "usd")).toBe("$98.8B");
    expect(formatMetric(null, "ratio")).toBe("—");
  });
});

describe("formatDifference", () => {
  it("shows margin changes in percentage points", () => {
    expect(formatDifference("0.007", "percent")).toBe("+0.7 pp");
    expect(formatDifference("-0.025", "percent")).toBe("−2.5 pp");
  });
  it("shows ratio changes in x", () => {
    expect(formatDifference("0.12", "ratio")).toBe("+0.12x");
  });
  it("shows dollar changes compactly", () => {
    expect(formatDifference("-10040000000", "usd")).toBe("−$10.0B");
  });
});

describe("direction", () => {
  it("follows the sign after display rounding", () => {
    expect(direction("0.064", "change")).toBe(1);
    expect(direction("-0.02", "change")).toBe(-1);
    expect(direction("0.0001", "change")).toBe(0); // shows as 0.0%
    expect(direction(null, "change")).toBeNull();
    expect(direction("0.004", "ratio")).toBe(0); // shows as 0.00x
  });
});

describe("formatAxisUsd", () => {
  it.each([
    [0, "$0"],
    [600e9, "$600B"],
    [150e9, "$150B"],
    [1.5e12, "$1.5T"],
    [-95e9, "−$95B"],
  ])("%s → %s", (input, expected) => {
    expect(formatAxisUsd(input)).toBe(expected);
  });
});

describe("trend formats", () => {
  it.each([
    ["416161000000", "usd", "$416,161M"],
    ["-17674000000", "usd", "−$17,674M"],
    ["12500000", "usd", "$12.5M"],
    ["903000000", "usd_change", "+$903M"],
    ["-26062000000", "usd_change", "−$26,062M"],
    ["0.0328", "percent", "3.3%"],
    ["0.064", "percent_change", "+6.4%"],
    ["0.022", "pp_change", "+2.2 pp"],
    ["1.3412", "ratio", "1.34x"],
    ["-0.64", "ratio_change", "−0.64x"],
    [null, "usd", "—"],
  ] as const)("%s as %s → %s", (value, format, expected) => {
    expect(formatTrendValue(value, format)).toBe(expected);
  });
});
