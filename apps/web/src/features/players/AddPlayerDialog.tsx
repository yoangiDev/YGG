import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useNavigate } from "react-router";
import { z } from "zod";

import { Button } from "@/components/ui/Button";
import { Field, Input, Select, Textarea } from "@/components/ui/Field";
import { Dialog } from "@/components/ui/Overlay";
import { useToast } from "@/components/ui/Toast";
import { api, isApiError, unwrap } from "@/lib/api/client";
import { queryKeys } from "@/lib/queryKeys";
import { parseRiotId } from "@/lib/riotId";
import { PLAYABLE_ROLES, REGIONS, roleLabel } from "@/lib/roles";

const schema = z.object({
  riotId: z.string().trim().refine((value) => parseRiotId(value) !== null, "Use the format Name#TAG"),
  region: z.string().min(1, "Pick a region"),
  role: z.enum(["TOP", "JUNGLE", "MID", "BOTTOM", "SUPPORT", "ALL"]),
  nickname: z.string().trim().max(50, "Use at most 50 characters"),
  notes: z.string().max(1000, "Use at most 1000 characters"),
});

function AddPlayerForm({ onDone }: { onDone: () => void }) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const toast = useToast();
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<z.input<typeof schema>, unknown, z.output<typeof schema>>({
    resolver: zodResolver(schema),
    defaultValues: { riotId: "", region: "EUW", role: "ALL", nickname: "", notes: "" },
  });

  const onSubmit = handleSubmit(async (values) => {
    const riotId = parseRiotId(values.riotId);
    if (!riotId) return;
    setFormError(null);
    try {
      const player = await unwrap(
        api.POST("/players/", {
          body: {
            game_name: riotId.gameName,
            tag_line: riotId.tagLine,
            region: values.region,
            role: values.role,
            nickname: values.nickname,
            notes: values.notes,
          },
        }),
      );
      await queryClient.invalidateQueries({ queryKey: queryKeys.players });
      toast.success(`${player.game_name}#${player.tag_line} added`);
      onDone();
      void navigate(`/players/${player.id}`);
    } catch (error) {
      setFormError(
        isApiError(error, 404)
          ? `${values.riotId} does not exist in ${values.region}.`
          : error instanceof Error
            ? error.message
            : "Could not add the player.",
      );
    }
  });

  return (
    <form className="flex flex-col gap-4" noValidate onSubmit={(event) => void onSubmit(event)}>
      {formError && (
        <p role="alert" className="rounded-lg border border-stat-red/40 bg-stat-red/10 px-3 py-2 text-sm text-stat-red">
          {formError}
        </p>
      )}
      <Field label="Riot ID" error={errors.riotId?.message} hint="Name and tag, as shown in the Riot client.">
        {(props) => <Input {...props} placeholder="Faker#KR1" autoComplete="off" autoFocus {...register("riotId")} />}
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Region" error={errors.region?.message}>
          {(props) => (
            <Select {...props} {...register("region")}>
              {REGIONS.map((region) => (
                <option key={region.value} value={region.value}>
                  {region.value} · {region.label}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Main role" error={errors.role?.message}>
          {(props) => (
            <Select {...props} {...register("role")}>
              {[...PLAYABLE_ROLES, "ALL" as const].map((role) => (
                <option key={role} value={role}>
                  {roleLabel(role)}
                </option>
              ))}
            </Select>
          )}
        </Field>
      </div>
      <Field label="Nickname" error={errors.nickname?.message}>
        {(props) => <Input {...props} placeholder="Optional" {...register("nickname")} />}
      </Field>
      <Field label="Notes" error={errors.notes?.message}>
        {(props) => <Textarea {...props} placeholder="Optional" {...register("notes")} />}
      </Field>
      <div className="mt-2 flex justify-end gap-2">
        <Button variant="ghost" onClick={onDone}>
          Cancel
        </Button>
        <Button type="submit" loading={isSubmitting}>
          Add player
        </Button>
      </div>
    </form>
  );
}

export function AddPlayerDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title="Add player"
      description="YGG checks the Riot ID against the Riot API before saving it."
    >
      <AddPlayerForm onDone={() => onOpenChange(false)} />
    </Dialog>
  );
}
