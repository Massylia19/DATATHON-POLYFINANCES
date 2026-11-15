import { describe, expect, it } from "vitest";
import { formatRatio, formatWeight, scenarioKey } from "./format";

describe("formatage financier", () => {
  it("multiplie les ratios mais pas les pondérations", () => {
    expect(formatRatio(0.736744)).toContain("73,67");
    expect(formatWeight(32.5)).toContain("32,5");
  });

  it("construit une clé sensible au scénario", () => {
    expect(scenarioKey("amira", "NVDA", 10)).not.toBe(scenarioKey("mateo", "NVDA", 10));
    expect(scenarioKey("amira", "NVDA", 10)).not.toBe(scenarioKey("amira", "NVDA", 20));
  });
});
