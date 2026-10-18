import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router";

import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { Dialog } from "@/components/ui/Overlay";
import { useToast } from "@/components/ui/Toast";
import { useAuth } from "@/features/auth/AuthProvider";
import { setActiveAccount } from "@/features/players/accounts";
import { api, unwrap } from "@/lib/api/client";

/** Delete your YGG account: asks for the password, deletes everything of yours (linked accounts, snapshots and analyses) and closes the
 * session. It can't be undone. */
export function DeleteAccountDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title="Delete your account?"
      description="Your linked accounts, snapshots and analyses are deleted for good."
    >
      <DeleteForm onCancel={() => onOpenChange(false)} />
    </Dialog>
  );
}

// It lives inside the dialog, which unmounts its content on closing: the typed password doesn't linger.
function DeleteForm({ onCancel }: { onCancel: () => void }) {
  const { logout } = useAuth();
  const navigate = useNavigate();
  const toast = useToast();
  const queryClient = useQueryClient();
  const [password, setPassword] = useState("");

  const remove = useMutation({
    mutationFn: () => unwrap(api.POST("/auth/delete-account", { body: { password } })),
    onSuccess: async () => {
      setActiveAccount(null);
      queryClient.clear();
      await logout();
      toast.success("Account deleted");
      void navigate("/login", { replace: true });
    },
    onError: (error) => toast.error(error.message),
  });

  return (
    <form
      className="flex flex-col gap-4"
      onSubmit={(event) => {
        event.preventDefault();
        if (password) remove.mutate();
      }}
    >
      <Input
        type="password"
        aria-label="Password"
        placeholder="Your password"
        autoComplete="current-password"
        autoFocus
        value={password}
        onChange={(event) => setPassword(event.target.value)}
      />
      <div className="flex justify-end gap-2">
        <Button variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" variant="danger" disabled={!password} loading={remove.isPending}>
          Delete account
        </Button>
      </div>
    </form>
  );
}
