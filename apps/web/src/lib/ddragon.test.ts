import { describe, expect, it } from "vitest";

import { ddragonUrl, parseRunes, parseSpells } from "./ddragon";

describe("Data Dragon parsing", () => {
  it("indexes summoner spells by numeric key", () => {
    const spells = parseSpells({
      SummonerFlash: { key: "4", image: { full: "SummonerFlash.png" } },
      Broken: { key: "x" },
    });
    expect(spells.get(4)).toBe("SummonerFlash.png");
    expect(spells.size).toBe(1);
  });

  it("indexes rune trees and the runes inside their slots", () => {
    const runes = parseRunes([
      {
        id: 8100,
        icon: "perk-images/Styles/7200_Domination.png",
        slots: [{ runes: [{ id: 8112, icon: "perk-images/Styles/Domination/Electrocute/Electrocute.png" }] }],
      },
    ]);
    expect(runes.get(8100)).toContain("Domination");
    expect(runes.get(8112)).toContain("Electrocute");
  });

  it("builds CDN urls", () => {
    expect(ddragonUrl.champion("16.10.1", "FiddleSticks")).toBe(
      "https://ddragon.leagueoflegends.com/cdn/16.10.1/img/champion/Fiddlesticks.png",
    );
    expect(ddragonUrl.item("16.10.1", 3031)).toMatch(/item\/3031\.png$/);
  });
});
