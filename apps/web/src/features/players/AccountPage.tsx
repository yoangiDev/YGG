import { useSearchParams } from "react-router";

import { Card, Skeleton } from "@/components/ui/Card";
import { Dialog } from "@/components/ui/Overlay";
import { PageHeader } from "@/components/ui/PageHeader";
import { ErrorState } from "@/components/ui/States";

import { setActiveAccount, useAccounts } from "./accounts";
import { LinkAccountForm } from "./LinkAccountForm";
import { PlayerDetail } from "./PlayerDetailPage";
import { VerifyAccount } from "./VerifyAccount";

const STEPS = [
  "Type the Riot ID of the account you play on, with its tag, and pick your region. Then prove it's yours by setting the profile icon we ask for.",
  "Pick a game of this patch, download its replay in your League client and upload it: YGG analyses it in about a minute.",
];

/** Your LoL accounts: the active one, with its page, and the others in the list above. With none, how to link the first. */
export function AccountPage() {
  const { query, active } = useAccounts();
  // the bar menu's "Link another account" arrives here with ?link
  const [params, setParams] = useSearchParams();
  const linking = params.has("link");

  if (query.isPending) {
    return (
      <Card>
        <Skeleton className="h-40" />
      </Card>
    );
  }
  if (query.isError) {
    return (
      <Card>
        <ErrorState error={query.error} onRetry={() => void query.refetch()} />
      </Card>
    );
  }
  if (active) {
    return (
      <>
        {/* unverified, its page is shown (it is public Riot data), but its replays aren't analysed */}
        {!active.verified && (
          <div className="mb-6">
            <VerifyAccount player={active} />
          </div>
        )}
        <PlayerDetail key={active.id} playerId={active.id} />
        <Dialog open={linking} onOpenChange={() => setParams({}, { replace: true })} title="Link another account">
          <LinkAccountForm
            onLinked={(player) => {
              setActiveAccount(player.id);
              setParams({}, { replace: true });
            }}
          />
        </Dialog>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="My"
        accent="account"
        description="Link your League of Legends account. YGG analyses the games you play on it."
      />
      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,28rem)]">
        <Card className="p-6">
          <h2 className="text-base font-black text-text">How it works</h2>
          <ol className="mt-4 flex flex-col gap-3">
            {STEPS.map((step, i) => (
              <li key={step} className="flex gap-3 text-sm leading-relaxed text-muted">
                <span className="grid size-6 shrink-0 place-items-center rounded-full border border-acid/50 text-xs font-black text-acid">
                  {i + 1}
                </span>
                {step}
              </li>
            ))}
          </ol>
        </Card>
        <Card className="p-6">
          <LinkAccountForm />
        </Card>
      </div>
    </>
  );
}
