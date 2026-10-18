import { ChampionIcon } from "@/components/player/PlayerBits";
import { Dialog } from "@/components/ui/Overlay";
import { formatNumber } from "@/lib/format";

import type { Match } from "./analyses";
import { HowToDownload, ReplayUpload, replayFile } from "./ReplayUpload";

/** Champion, KDA and CS/min of a match: the only thing needed to recognise it in the list. */
export function GameLine({ match }: { match: Match }) {
  return (
    <span className="flex min-w-0 items-center gap-3">
      <ChampionIcon name={match.champion} size={36} />
      <span className="w-28 truncate text-sm font-black text-text">{match.champion}</span>
      <span className="w-20 text-sm tabular-nums text-soft">
        {match.kills}/{match.deaths}/{match.assists}
      </span>
      <span className="text-sm tabular-nums text-muted">{formatNumber(match.cs_per_min, 1)} CS/min</span>
    </span>
  );
}

/** Asks for a match's replay. Before accepting it, the API checks that it is of that match and of your account
 * (`POST /games/{id}/replay`); if it is, the analysis carries on by itself and this closes. */
export function UploadReplayDialog({ match, onClose, onUploaded }: { match: Match | null; onClose: () => void; onUploaded?: () => void }) {
  return (
    <Dialog
      open={match !== null}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title="Upload the replay"
      description={match ? replayFile(match.match_id) : undefined}
    >
      {match && (
        <div className="flex flex-col items-center gap-5">
          <GameLine match={match} />
          <ReplayUpload
            expected={[match.match_id]}
            label="Choose the file"
            onUploaded={() => {
              onClose();
              onUploaded?.();
            }}
          />
          <HowToDownload />
        </div>
      )}
    </Dialog>
  );
}
