import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ShieldCheck } from "lucide-react";

import { ProfileIcon } from "@/components/player/PlayerBits";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { useToast } from "@/components/ui/Toast";
import { api, unwrap, type Schemas } from "@/lib/api/client";
import { queryKeys } from "@/lib/queryKeys";

/** Prove that the linked account is yours: put on in the client the icon YGG asks for (only whoever has the account
 * can change it) and have the API see it in Riot. Without this, replays aren't analysed. */
export function VerifyAccount({ player }: { player: Schemas["PlayerResponse"] }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const verify = useMutation({
    mutationFn: () => unwrap(api.POST("/players/{player_id}/verify", { params: { path: { player_id: player.id } } })),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.players });
      toast.success(`${player.game_name}#${player.tag_line} verified`);
    },
    onError: (error) => toast.error(error.message),
  });

  return (
    <Card featured className="flex flex-wrap items-center gap-6 p-6">
      <ProfileIcon iconId={player.verify_icon} name="?" size={88} className="ring-2 ring-acid" />
      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <h2 className="text-base font-black text-text">Verify it's your account</h2>
        <ol className="list-decimal space-y-1 pl-5 text-sm text-muted">
          <li>In your League client, click your profile picture and choose this icon. Every account has it.</li>
          <li>Come back and press Verify. You can switch back to your icon right after.</li>
        </ol>
      </div>
      <Button loading={verify.isPending} onClick={() => verify.mutate()}>
        {!verify.isPending && <ShieldCheck className="size-4" aria-hidden="true" />}
        Verify
      </Button>
    </Card>
  );
}
