import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { Dialog } from "@/components/ui/Overlay";
import type { Schemas } from "@/lib/api/client";

type Player = Schemas["PlayerResponse"];

/** Unlinking asks to type the account's Riot ID again: a stray click doesn't delete it along with its snapshots. */
export function UnlinkDialog({
  player,
  open,
  onOpenChange,
  loading,
  onConfirm,
}: {
  player: Player;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  loading: boolean;
  onConfirm: () => void;
}) {
  const name = `${player.game_name}#${player.tag_line}`;
  return (
    <Dialog open={open} onOpenChange={onOpenChange} title="Unlink this account?" description="Its snapshots are deleted too.">
      <UnlinkForm name={name} loading={loading} onCancel={() => onOpenChange(false)} onConfirm={onConfirm} />
    </Dialog>
  );
}

// The form lives inside the dialog, which unmounts its content on closing: what was typed doesn't linger for next time.
function UnlinkForm({ name, loading, onCancel, onConfirm }: { name: string; loading: boolean; onCancel: () => void; onConfirm: () => void }) {
  const [typed, setTyped] = useState("");
  const matches = typed.trim().toLowerCase() === name.toLowerCase();
  return (
    <form
      className="flex flex-col gap-4"
      onSubmit={(event) => {
        event.preventDefault();
        if (matches) onConfirm();
      }}
    >
      <label htmlFor="unlink-name" className="text-sm text-soft">
        Type <strong className="font-black text-text">{name}</strong> exactly as it is to confirm.
      </label>
      <Input
        id="unlink-name"
        autoComplete="off"
        autoFocus
        value={typed}
        onChange={(event) => setTyped(event.target.value)}
      />
      <div className="flex justify-end gap-2">
        <Button variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" variant="danger" disabled={!matches} loading={loading}>
          Unlink
        </Button>
      </div>
    </form>
  );
}
