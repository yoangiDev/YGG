import { useState } from "react";

import { ProgressBar, Skeleton } from "@/components/ui/Card";
import { cn } from "@/lib/cn";
import { ddragonUrl, useDDragon } from "@/lib/ddragon";
import { formatPercent } from "@/lib/format";
import { isApexTier, normalizeTier, RANK_COLORS, rankImage, rankLabel, rankProgress, type Cutoffs } from "@/lib/rank";
import { roleIcon, roleLabel } from "@/lib/roles";
import { toneBackground, toneText, winRateTone } from "@/lib/stats";

// ── Rango ─────────────────────────────────────────────────────────────────────

export function RankEmblem({ tier, size = 40, className }: { tier: string | null | undefined; size?: number; className?: string }) {
  return (
    <img
      src={rankImage(tier)}
      alt=""
      width={size}
      height={size}
      loading="lazy"
      decoding="async"
      className={cn("shrink-0 object-contain", className)}
      style={{ width: size, height: size }}
    />
  );
}

export function RankBadge({
  tier,
  division,
  lp,
  cutoffs,
  size = 40,
  showProgress = false,
}: {
  tier: string | null | undefined;
  division?: string | null | undefined;
  lp?: number | null | undefined;
  cutoffs?: Cutoffs;
  size?: number;
  showProgress?: boolean;
}) {
  const normalized = normalizeTier(tier);
  const color = normalized ? RANK_COLORS[normalized] : "var(--color-stat-gray)";
  const progress = rankProgress(tier, lp, cutoffs);
  const nextLabel = normalized === "MASTER" ? "Grandmaster" : normalized === "GRANDMASTER" ? "Challenger" : "next division";

  return (
    <div className="flex min-w-0 items-center gap-2.5">
      <RankEmblem tier={tier} size={size} />
      <div className="min-w-0">
        <p className="truncate text-sm font-semibold" style={{ color }}>
          {rankLabel(tier, division, lp)}
        </p>
        {showProgress && normalized && normalized !== "CHALLENGER" && (
          <ProgressBar
            className="mt-1.5 w-28"
            value={progress * 100}
            color={color}
            label={isApexTier(normalized) ? `Progress to ${nextLabel}` : "Progress to next division"}
          />
        )}
      </div>
    </div>
  );
}

// ── Rol ───────────────────────────────────────────────────────────────────────

export function RoleIcon({ role, size = 20, className }: { role: string | null | undefined; size?: number; className?: string }) {
  const src = roleIcon(role);
  const label = roleLabel(role);
  if (!src) return <span className={cn("text-xs text-muted", className)}>{label}</span>;
  return (
    <img
      src={src}
      alt={label}
      title={label}
      width={size}
      height={size}
      className={cn("shrink-0 opacity-90", className)}
      style={{ width: size, height: size }}
    />
  );
}

// ── Iconos de Data Dragon ─────────────────────────────────────────────────────

function DDragonImage({
  src,
  alt,
  size,
  fallback,
  className,
}: {
  src: string | null;
  alt: string;
  size: number;
  fallback: string;
  className?: string;
}) {
  const [failed, setFailed] = useState<string | null>(null);
  const style = { width: size, height: size };

  if (!src || failed === src) {
    return (
      <span
        role={alt ? "img" : undefined}
        aria-label={alt || undefined}
        className={cn("grid shrink-0 place-items-center bg-surface-2 text-[0.65rem] font-bold text-muted uppercase", className)}
        style={style}
      >
        {fallback}
      </span>
    );
  }
  return (
    <img
      src={src}
      alt={alt}
      width={size}
      height={size}
      loading="lazy"
      decoding="async"
      onError={() => {
        setFailed(src);
      }}
      className={cn("shrink-0 bg-surface-2 object-cover", className)}
      style={style}
    />
  );
}

export function ChampionIcon({ name, size = 32, className }: { name: string; size?: number; className?: string }) {
  const { data } = useDDragon();
  if (!data) return <Skeleton className={cn("shrink-0 rounded-md", className)} />;
  return (
    <DDragonImage
      src={ddragonUrl.champion(data.version, name)}
      alt={name}
      size={size}
      fallback={name.slice(0, 2)}
      className={cn("rounded-md", className)}
    />
  );
}

export function ProfileIcon({
  iconId,
  name,
  size = 40,
  className,
}: {
  iconId: number | null | undefined;
  name: string;
  size?: number;
  className?: string;
}) {
  const { data } = useDDragon();
  const src = data && iconId ? ddragonUrl.profileIcon(data.version, iconId) : null;
  return <DDragonImage src={src} alt="" size={size} fallback={name.slice(0, 1)} className={cn("rounded-full", className)} />;
}

export function ItemIcon({ itemId, size = 22 }: { itemId: number; size?: number }) {
  const { data } = useDDragon();
  if (!itemId) return <span className="shrink-0 rounded bg-surface-2/70" style={{ width: size, height: size }} aria-hidden="true" />;
  return (
    <DDragonImage
      src={data ? ddragonUrl.item(data.version, itemId) : null}
      alt={`Item ${itemId}`}
      size={size}
      fallback=""
      className="rounded"
    />
  );
}

export function SpellIcon({ spellId, size = 20 }: { spellId: number; size?: number }) {
  const { data } = useDDragon();
  const file = data?.spellImages.get(spellId);
  return (
    <DDragonImage
      src={data && file ? ddragonUrl.spell(data.version, file) : null}
      alt={file ? file.replace(/^Summoner|\.png$/g, "") : ""}
      size={size}
      fallback=""
      className="rounded"
    />
  );
}

export function RuneIcon({ runeId, size = 20 }: { runeId: number; size?: number }) {
  const { data } = useDDragon();
  const icon = data?.runeIcons.get(runeId);
  return <DDragonImage src={icon ? ddragonUrl.rune(icon) : null} alt="" size={size} fallback="" className="rounded-full" />;
}

// ── Win rate ──────────────────────────────────────────────────────────────────

export function WinRate({ wins, losses, compact = false }: { wins: number; losses: number; compact?: boolean }) {
  const games = wins + losses;
  const winRate = games > 0 ? (wins / games) * 100 : 0;
  const tone = winRateTone(winRate);
  if (games === 0) return <span className="text-xs text-muted">No ranked games</span>;
  return (
    <div className="min-w-0">
      <p className="text-sm">
        <span className={cn("font-semibold", toneText[tone])}>{formatPercent(winRate, 0)}</span>
        <span className="ml-1.5 text-xs text-muted">
          {wins}W {losses}L
        </span>
      </p>
      {!compact && (
        <div className="mt-1.5 flex h-1 w-28 overflow-hidden rounded-full bg-stat-red/35" aria-hidden="true">
          <div className={toneBackground[tone]} style={{ width: `${winRate}%` }} />
        </div>
      )}
    </div>
  );
}
