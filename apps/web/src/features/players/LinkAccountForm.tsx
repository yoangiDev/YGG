import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/components/ui/Button";
import { Field, Input, Select } from "@/components/ui/Field";
import { useToast } from "@/components/ui/Toast";
import { api, isApiError, unwrap, type Schemas } from "@/lib/api/client";
import { queryKeys } from "@/lib/queryKeys";
import { parseRiotId } from "@/lib/riotId";
import { PLAYABLE_ROLES, REGIONS, roleLabel, toRegion, type Region } from "@/lib/roles";

const schema = z.object({
  riotId: z.string().trim().refine((value) => parseRiotId(value) !== null, "Use the format Name#TAG"),
  region: z.custom<Region>((value) => typeof value === "string" && toRegion(value) === value, "Pick a region"),
  role: z.enum(["TOP", "JUNGLE", "MID", "BOTTOM", "SUPPORT", "ALL"]),
});

/** Link a LoL account. The API checks it against Riot before storing it; when done, the accounts list is
 * refreshed and `onLinked` receives the new one (to make it active). */
export function LinkAccountForm({ onLinked }: { onLinked?: (player: Schemas["PlayerResponse"]) => void }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<z.input<typeof schema>, unknown, z.output<typeof schema>>({
    resolver: zodResolver(schema),
    defaultValues: { riotId: "", region: "EUW", role: "ALL" },
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
            nickname: "",
            notes: "",
          },
        }),
      );
      await queryClient.invalidateQueries({ queryKey: queryKeys.players });
      toast.success(`${player.game_name}#${player.tag_line} linked`);
      onLinked?.(player);
    } catch (error) {
      setFormError(
        isApiError(error, 404)
          ? `${values.riotId} does not exist in ${values.region}.`
          : error instanceof Error
            ? error.message
            : "Could not link the account.",
      );
    }
  });

  return (
    <form className="flex flex-col gap-4" noValidate onSubmit={(event) => void onSubmit(event)}>
      {formError && (
        <p role="alert" className="border border-stat-red/40 bg-stat-red/10 px-3 py-2 text-sm text-stat-red">
          {formError}
        </p>
      )}
      <Field label="Riot ID" error={errors.riotId?.message} hint="Name and tag, as shown in your Riot client.">
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
      <div className="mt-2 flex justify-end">
        <Button type="submit" loading={isSubmitting}>
          Link account
        </Button>
      </div>
    </form>
  );
}
