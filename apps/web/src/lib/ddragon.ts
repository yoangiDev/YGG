import { useQuery } from "@tanstack/react-query";

import { api, unwrap } from "@/lib/api/client";
import { queryKeys } from "@/lib/queryKeys";

/**
 * Data Dragon. The API only provides the patch version and the spell and rune
 * JSON (cached in Redis); images are requested directly from Riot's
 * CDN, which already has caching and compression.
 */

const CDN = "https://ddragon.leagueoflegends.com/cdn";

/**
 * Official icons of the game's minimap (CommunityDragon: Data Dragon doesn't have them), pinned to patch 16.19 so
 * they don't change by themselves: tower, dragon, baron, riftherald and grub.
 */
export const OBJECTIVE_ICONS = "https://raw.communitydragon.org/16.19/game/assets/ux/minimap/icons";

/**
 * The Rift minimap in 16.19 (CommunityDragon, 512 px). It covers -120 to 14,870 in x and -120 to 14,980 in z,
 * the limits Riot gives for its map image: with them any game position falls in its place.
 */
export const MINIMAP = {
  src: "https://raw.communitydragon.org/16.19/game/assets/maps/info/map11/2dlevelminimap_base_baron1.png",
  x: [-120, 14870],
  z: [-120, 14980],
} as const;

export interface DDragonData {
  version: string;
  spellImages: Map<number, string>;
  runeIcons: Map<number, string>;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

export function parseSpells(spells: Record<string, unknown>): Map<number, string> {
  const images = new Map<number, string>();
  for (const spell of Object.values(spells)) {
    if (!isRecord(spell) || !isRecord(spell.image)) continue;
    const key = Number(spell.key);
    const file = spell.image.full;
    if (Number.isFinite(key) && typeof file === "string") images.set(key, file);
  }
  return images;
}

export function parseRunes(trees: readonly unknown[]): Map<number, string> {
  const icons = new Map<number, string>();
  const add = (node: unknown) => {
    if (isRecord(node) && typeof node.id === "number" && typeof node.icon === "string") icons.set(node.id, node.icon);
  };
  for (const tree of trees) {
    add(tree);
    if (!isRecord(tree) || !Array.isArray(tree.slots)) continue;
    for (const slot of tree.slots) {
      if (isRecord(slot) && Array.isArray(slot.runes)) slot.runes.forEach(add);
    }
  }
  return icons;
}

async function loadDDragon(): Promise<DDragonData> {
  const [version, spells, runes] = await Promise.all([
    unwrap(api.GET("/ddragon/version")),
    unwrap(api.GET("/ddragon/spells")),
    unwrap(api.GET("/ddragon/runes")),
  ]);
  return { version, spellImages: parseSpells(spells), runeIcons: parseRunes(runes) };
}

export function useDDragon() {
  return useQuery({
    queryKey: queryKeys.ddragon,
    queryFn: loadDDragon,
    staleTime: 6 * 60 * 60 * 1000,
    gcTime: Number.POSITIVE_INFINITY,
  });
}

/** match-v5 championName → Data Dragon id (Riot keeps a few historical exceptions). */
const CHAMPION_ID_FIXES: Record<string, string> = { FiddleSticks: "Fiddlesticks" };

export const ddragonUrl = {
  champion: (version: string, championName: string) =>
    `${CDN}/${version}/img/champion/${encodeURIComponent(CHAMPION_ID_FIXES[championName] ?? championName)}.png`,
  item: (version: string, itemId: number) => `${CDN}/${version}/img/item/${itemId}.png`,
  profileIcon: (version: string, iconId: number) => `${CDN}/${version}/img/profileicon/${iconId}.png`,
  spell: (version: string, file: string) => `${CDN}/${version}/img/spell/${file}`,
  rune: (iconPath: string) => `${CDN}/img/${iconPath}`,
  map: (version: string) => `${CDN}/${version}/img/map/map11.png`,
};
