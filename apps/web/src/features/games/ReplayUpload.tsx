import { useQueryClient } from "@tanstack/react-query";
import { Upload } from "lucide-react";
import { useRef, useState } from "react";

import { Button } from "@/components/ui/Button";
import { useToast } from "@/components/ui/Toast";
import { api, isApiError, unwrap } from "@/lib/api/client";
import { cn } from "@/lib/cn";
import { queryKeys } from "@/lib/queryKeys";

/** EUW1_123 → "EUW1-123.rofl", the name under which the League client stores the replay. */
export const replayFile = (matchId: string) => `${matchId.replace("_", "-")}.rofl`;

/** "EUW1-123.rofl" → EUW1_123, or null if the file isn't named like a replay. */
export function matchIdOf(fileName: string): string | null {
  const m = /^([A-Z0-9]{2,5})-(\d{6,15})\.rofl$/i.exec(fileName);
  return m ? `${m[1]?.toUpperCase()}_${m[2]}` : null;
}

/** Which match each file goes to: the one in its name if it is one of `expected`; with a single one expected, that one (the API
 * checks anyway that the file is that match). */
export function targetOf(fileName: string, expected: string[]): string | null {
  const id = matchIdOf(fileName);
  if (id && expected.includes(id)) return id;
  return expected.length === 1 ? (expected[0] ?? null) : null;
}

const MAX_BYTES = 40 * 1024 * 1024; // as in the API: a replay is 12-20 MB

/** Upload replays (.rofl): a large button that opens the file picker, or drag them onto it. Each one is uploaded
 * to its match (`POST /games/{id}/replay`) and the API analyses it in the background. */
export function ReplayUpload({
  expected,
  label,
  disabled = false,
  onUploaded,
}: {
  expected: string[];
  label: string;
  disabled?: boolean;
  onUploaded?: () => void;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [over, setOver] = useState(false);

  async function upload(files: File[]) {
    setBusy(true);
    let sent = false;
    for (const file of files) {
      const matchId = targetOf(file.name, expected);
      if (!matchId) {
        toast.error(`${file.name} is not the replay of any of these games.`);
        continue;
      }
      // the cheap check, without spending the upload; the API checks everything again and it is the one in charge
      if (file.size > MAX_BYTES || (await file.slice(0, 4).text()) !== "RIOT") {
        toast.error(`${file.name} is not a League replay.`);
        continue;
      }
      try {
        await unwrap(
          api.POST("/games/{match_id}/replay", {
            params: { path: { match_id: matchId } },
            body: file as unknown as string,
            bodySerializer: (body) => body,
            headers: { "Content-Type": "application/octet-stream" },
          }),
        );
        sent = true;
      } catch (error) {
        toast.error(
          isApiError(error, 429)
            ? "You've used your analyses for the last 24 hours."
            : `${file.name}: ${error instanceof Error ? error.message : "upload failed"}`,
        );
      }
    }
    setBusy(false);
    await queryClient.invalidateQueries({ queryKey: queryKeys.gameAnalyses });
    // and the replay analysis of a snapshot that was waiting for any of these
    await queryClient.invalidateQueries({ predicate: (query) => query.queryKey[2] === "premium" });
    if (sent) onUploaded?.();
  }

  return (
    <div
      onDragOver={(event) => {
        event.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(event) => {
        event.preventDefault();
        setOver(false);
        if (!disabled && !busy) void upload([...event.dataTransfer.files]);
      }}
      className={cn("border border-dashed border-transparent p-2 transition-colors", over && "border-acid bg-acid/5")}
    >
      <input
        ref={input}
        type="file"
        accept=".rofl"
        multiple={expected.length > 1}
        className="sr-only"
        aria-hidden="true"
        tabIndex={-1}
        onChange={(event) => {
          const files = [...(event.target.files ?? [])];
          event.target.value = ""; // the same file again must also trigger onChange
          if (files.length) void upload(files);
        }}
      />
      <Button size="lg" loading={busy} disabled={disabled} onClick={() => input.current?.click()}>
        {!busy && <Upload className="size-4" aria-hidden="true" />}
        {label}
      </Button>
    </div>
  );
}

/** How to download a replay: the only thing the web can't do for you. */
export function HowToDownload({ many = false }: { many?: boolean }) {
  return (
    <ol className="max-w-md list-decimal space-y-1 pl-5 text-left text-sm text-muted">
      <li>
        In your League client: profile → <span className="text-soft">Match History</span> → the download icon next to{" "}
        {many ? "each game" : "the game"}.
      </li>
      <li>
        Choose {many ? "the files" : "the file"} here, in <code className="text-soft">Documents\League of Legends\Replays</code>.
      </li>
    </ol>
  );
}
