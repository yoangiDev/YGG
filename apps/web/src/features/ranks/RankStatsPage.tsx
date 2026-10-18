import { Clock, Swords } from "lucide-react";
import type { ReactNode } from "react";
import { useSearchParams } from "react-router";

import { RankEmblem } from "@/components/player/PlayerBits";
import { Card } from "@/components/ui/Card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/Overlay";
import { PageHeader } from "@/components/ui/PageHeader";
import { formatNumber } from "@/lib/format";

import { DeepDive } from "./DeepDive";
import { ByRole, Overview } from "./Overview";
import { ROLES, stats, TIERS } from "./rankStats";

/**
 * Stats by rank: what changes from Gold to Challenger across the whole sample. The entry view is for everyone
 * (few figures, in words); "Deep dive" keeps all the tables for whoever wants them.
 */
const VIEWS = [
  { value: "overview", label: "Overview" },
  { value: "roles", label: "By role" },
  { value: "deep", label: "Deep dive" },
] as const;

function Fact({ icon, value, detail }: { icon: ReactNode; value: ReactNode; detail: string }) {
  return (
    <Card className="flex items-center gap-4 p-5">
      {icon}
      <div>
        <p className="text-xl font-black text-text tabular-nums">{value}</p>
        <p className="text-xs text-muted">{detail}</p>
      </div>
    </Card>
  );
}

export function RankStatsPage() {
  const [params, setParams] = useSearchParams();
  const view = VIEWS.find((option) => option.value === params.get("view"))?.value ?? "overview";
  const role = ROLES.find((option) => option.role === params.get("role"))?.role ?? "TOP";
  const [gold = 0, ...rest] = stats.duration.means;
  const challenger = rest[rest.length - 1] ?? gold;

  const go = (next: Record<string, string>) =>
    setParams(Object.fromEntries(Object.entries(next).filter(([, value]) => value !== "overview")), {
      replace: true,
      preventScrollReset: true,
    });

  return (
    <>
      <PageHeader
        eyebrow="Ranked solo · EUW"
        title="Stats by"
        accent="rank"
        description="How do the best players play differently? We watched ranked games from Gold to Challenger, second by second, and compared what players actually do."
      />

      <div className="mb-10 grid gap-4 md:grid-cols-3">
        <Fact
          icon={<Swords className="size-8 shrink-0 text-acid" aria-hidden="true" />}
          value="Second by second"
          detail="every game decoded from its replay file"
        />
        <Card className="flex flex-col justify-center gap-2 p-5">
          <span className="flex items-center justify-between" aria-hidden="true">
            {TIERS.map((tier) => (
              <RankEmblem key={tier} tier={tier} size={30} />
            ))}
          </span>
          <p className="text-xs text-muted">7 tiers: from Gold to Challenger</p>
        </Card>
        <Fact
          icon={<Clock className="size-8 shrink-0 text-stat-blue" aria-hidden="true" />}
          value={`${formatNumber(gold - challenger, 0)} min shorter`}
          detail={`Challenger games end faster: ${formatNumber(gold, 1)} → ${formatNumber(challenger, 1)} minutes`}
        />
      </div>

      <Tabs value={view} onValueChange={(value) => go(value === "roles" ? { view: value, role } : { view: value })}>
        <TabsList aria-label="Stats by rank views" className="mb-8">
          {VIEWS.map((option) => (
            <TabsTrigger key={option.value} value={option.value}>
              {option.label}
            </TabsTrigger>
          ))}
        </TabsList>

        <TabsContent value="overview" className="focus:outline-none">
          <Overview onDeepDive={() => go({ view: "deep" })} />
        </TabsContent>
        <TabsContent value="roles" className="focus:outline-none">
          <ByRole role={role} onRole={(next) => go({ view: "roles", role: next })} />
        </TabsContent>
        <TabsContent value="deep" className="focus:outline-none">
          <DeepDive />
        </TabsContent>
      </Tabs>
    </>
  );
}
