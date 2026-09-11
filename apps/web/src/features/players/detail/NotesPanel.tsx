import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { Textarea } from "@/components/ui/Field";
import { useToast } from "@/components/ui/Toast";
import { api, unwrap, type Schemas } from "@/lib/api/client";

import { playerUpdate, updateCachedPlayer } from "../cache";

type Player = Schemas["PlayerResponse"];

export function NotesPanel({ player }: { player: Player }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const saved = player.notes ?? "";
  const [notes, setNotes] = useState(saved);

  const save = useMutation({
    mutationFn: () =>
      unwrap(api.PUT("/players/{player_id}", { params: { path: { player_id: player.id } }, body: playerUpdate(player, { notes }) })),
    onSuccess: (updated) => {
      updateCachedPlayer(queryClient, updated);
      toast.success("Notes saved");
    },
    onError: (error) => toast.error(error.message),
  });

  return (
    <Card>
      <CardHeader title="Coach notes" />
      <form
        className="flex flex-col gap-3 p-5"
        onSubmit={(event) => {
          event.preventDefault();
          save.mutate();
        }}
      >
        <label htmlFor="player-notes" className="sr-only">
          Notes
        </label>
        <Textarea
          id="player-notes"
          value={notes}
          maxLength={1000}
          placeholder="Habits, goals, things to review…"
          onChange={(event) => setNotes(event.target.value)}
        />
        {notes !== saved && (
          <div className="flex justify-end gap-2">
            <Button variant="ghost" size="sm" onClick={() => setNotes(saved)}>
              Discard
            </Button>
            <Button type="submit" size="sm" loading={save.isPending}>
              Save notes
            </Button>
          </div>
        )}
      </form>
    </Card>
  );
}
