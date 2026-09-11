import { zodResolver } from "@hookform/resolvers/zod";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash, UserCheck, UserPlus, UserX } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useSearchParams } from "react-router";
import { z } from "zod";

import { Button } from "@/components/ui/Button";
import { Card, Skeleton } from "@/components/ui/Card";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { Field, Input, Select } from "@/components/ui/Field";
import { Dialog, Tooltip } from "@/components/ui/Overlay";
import { Pager } from "@/components/ui/Pager";
import { ErrorState } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { useAuth } from "@/features/auth/AuthProvider";
import { emailSchema, newPasswordSchema, usernameSchema } from "@/features/auth/schemas";
import { api, unwrap, type Schemas } from "@/lib/api/client";
import { cn } from "@/lib/cn";
import { queryKeys } from "@/lib/queryKeys";

type AdminUser = Schemas["UserOut"];

const PAGE_SIZE = 25;

export function usePageParam(): [number, (page: number) => void] {
  const [params, setParams] = useSearchParams();
  const page = Math.max(0, Number.parseInt(params.get("page") ?? "0", 10) || 0);
  const setPage = (next: number) =>
    setParams(
      (current) => {
        const updated = new URLSearchParams(current);
        if (next > 0) updated.set("page", String(next));
        else updated.delete("page");
        return updated;
      },
      { replace: true },
    );
  return [page, setPage];
}

export function AdminUsersPage() {
  const { user: me } = useAuth();
  const queryClient = useQueryClient();
  const toast = useToast();
  const [page, setPage] = usePageParam();
  const [creating, setCreating] = useState(false);
  const [toDelete, setToDelete] = useState<AdminUser | null>(null);
  const [confirmPurge, setConfirmPurge] = useState(false);
  const offset = page * PAGE_SIZE;

  const users = useQuery({
    queryKey: queryKeys.admin.users(offset),
    queryFn: () => unwrap(api.GET("/admin/users/", { params: { query: { limit: PAGE_SIZE, offset } } })),
    placeholderData: keepPreviousData,
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: queryKeys.admin.all });
  const onError = (error: Error) => toast.error(error.message);

  const updateRole = useMutation({
    mutationFn: ({ id, role }: { id: number; role: string }) =>
      unwrap(api.PATCH("/admin/users/{user_id}/role", { params: { path: { user_id: id } }, body: { role } })),
    onSuccess: (user) => {
      toast.success(`${user.username} is now ${user.role}`);
      void invalidate();
    },
    onError,
  });

  const toggleActive = useMutation({
    mutationFn: (id: number) => unwrap(api.PATCH("/admin/users/{user_id}/active", { params: { path: { user_id: id } } })),
    onSuccess: (user) => {
      toast.success(`${user.username} ${user.is_active ? "activated" : "deactivated"}`);
      void invalidate();
    },
    onError,
  });

  const remove = useMutation({
    mutationFn: (id: number) => unwrap(api.DELETE("/admin/users/{user_id}", { params: { path: { user_id: id } } })),
    onSuccess: () => {
      setToDelete(null);
      toast.success("User deleted");
      void invalidate();
    },
    onError,
  });

  const purge = useMutation({
    mutationFn: () => unwrap(api.DELETE("/admin/users/inactive")),
    onSuccess: (result) => {
      setConfirmPurge(false);
      toast.success(`${result.deleted} inactive user${result.deleted === 1 ? "" : "s"} deleted`);
      void invalidate();
    },
    onError,
  });

  return (
    <>
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border/60 p-4">
          <p className="text-sm text-muted">{users.data ? `${users.data.total} accounts` : "Accounts"}</p>
          <div className="flex gap-2">
            <Button variant="danger" size="sm" onClick={() => setConfirmPurge(true)}>
              <UserX className="size-3.5" aria-hidden="true" />
              Delete inactive
            </Button>
            <Button size="sm" onClick={() => setCreating(true)}>
              <UserPlus className="size-3.5" aria-hidden="true" />
              Create user
            </Button>
          </div>
        </div>

        {users.isPending ? (
          <div className="flex flex-col gap-2 p-4">
            {Array.from({ length: 5 }, (_, index) => (
              <Skeleton key={index} className="h-11" />
            ))}
          </div>
        ) : users.isError ? (
          <ErrorState error={users.error} onRetry={() => void users.refetch()} />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className={cn("w-full text-sm", users.isPlaceholderData && "opacity-60")}>
                <thead>
                  <tr className="border-b border-border/60 text-left text-[11px] tracking-wider text-muted uppercase">
                    <th scope="col" className="px-4 py-3 font-semibold">
                      User
                    </th>
                    <th scope="col" className="px-4 py-3 font-semibold">
                      Role
                    </th>
                    <th scope="col" className="px-4 py-3 font-semibold">
                      Status
                    </th>
                    <th scope="col" className="px-4 py-3">
                      <span className="sr-only">Actions</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {users.data.items.map((user) => {
                    const isMe = user.id === me?.id;
                    return (
                      <tr key={user.id} className="border-b border-border/40 last:border-0">
                        <td className="px-4 py-3">
                          <p className="font-semibold text-fg">
                            {user.username}
                            {isMe && <span className="ml-2 text-xs font-normal text-muted">(you)</span>}
                          </p>
                          <p className="text-xs text-muted">{user.email}</p>
                        </td>
                        <td className="px-4 py-3">
                          <Select
                            aria-label={`Role of ${user.username}`}
                            className="h-8 w-28 text-xs"
                            value={user.role}
                            disabled={isMe || updateRole.isPending}
                            onChange={(event) => updateRole.mutate({ id: user.id, role: event.target.value })}
                          >
                            <option value="user">User</option>
                            <option value="admin">Admin</option>
                          </Select>
                        </td>
                        <td className="px-4 py-3">
                          <span
                            className={cn(
                              "rounded-full px-2 py-0.5 text-xs font-semibold",
                              user.is_active ? "bg-stat-green/15 text-stat-green" : "bg-stat-gray/15 text-stat-gray",
                            )}
                          >
                            {user.is_active ? "Active" : "Inactive"}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex justify-end gap-1">
                            <Tooltip content={user.is_active ? "Deactivate" : "Activate"}>
                              <Button
                                variant="ghost"
                                size="icon"
                                disabled={isMe}
                                aria-label={`${user.is_active ? "Deactivate" : "Activate"} ${user.username}`}
                                onClick={() => toggleActive.mutate(user.id)}
                              >
                                {user.is_active ? (
                                  <UserX className="size-4" aria-hidden="true" />
                                ) : (
                                  <UserCheck className="size-4" aria-hidden="true" />
                                )}
                              </Button>
                            </Tooltip>
                            <Tooltip content="Delete user">
                              <Button
                                variant="ghost"
                                size="icon"
                                disabled={isMe}
                                aria-label={`Delete ${user.username}`}
                                onClick={() => setToDelete(user)}
                              >
                                <Trash className="size-4" aria-hidden="true" />
                              </Button>
                            </Tooltip>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <Pager page={page} pageSize={PAGE_SIZE} total={users.data.total} onPageChange={setPage} />
          </>
        )}
      </Card>

      <CreateUserDialog
        open={creating}
        onOpenChange={setCreating}
        onCreated={(user) => {
          toast.success(`${user.username} created`);
          void invalidate();
        }}
      />
      <ConfirmDialog
        open={toDelete !== null}
        onOpenChange={(open) => {
          if (!open) setToDelete(null);
        }}
        title={`Delete ${toDelete?.username ?? "user"}?`}
        description="Their players and snapshots are deleted too. This cannot be undone."
        loading={remove.isPending}
        onConfirm={() => {
          if (toDelete) remove.mutate(toDelete.id);
        }}
      />
      <ConfirmDialog
        open={confirmPurge}
        onOpenChange={setConfirmPurge}
        title="Delete all inactive users?"
        description="Every deactivated account and its data is removed. This cannot be undone."
        confirmLabel="Delete inactive users"
        loading={purge.isPending}
        onConfirm={() => purge.mutate()}
      />
    </>
  );
}

const createUserSchema = z.object({
  username: usernameSchema,
  email: emailSchema,
  password: newPasswordSchema,
  role: z.enum(["user", "admin"]),
});

function CreateUserDialog({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: (user: AdminUser) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange} title="Create user">
      <CreateUserForm
        onCancel={() => onOpenChange(false)}
        onCreated={(user) => {
          onCreated(user);
          onOpenChange(false);
        }}
      />
    </Dialog>
  );
}

function CreateUserForm({ onCancel, onCreated }: { onCancel: () => void; onCreated: (user: AdminUser) => void }) {
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<z.input<typeof createUserSchema>, unknown, z.output<typeof createUserSchema>>({
    resolver: zodResolver(createUserSchema),
    defaultValues: { username: "", email: "", password: "", role: "user" },
  });

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null);
    try {
      onCreated(await unwrap(api.POST("/admin/users/", { body: values })));
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Could not create the user.");
    }
  });

  return (
    <form className="flex flex-col gap-4" noValidate onSubmit={(event) => void onSubmit(event)}>
      {formError && (
        <p role="alert" className="rounded-lg border border-stat-red/40 bg-stat-red/10 px-3 py-2 text-sm text-stat-red">
          {formError}
        </p>
      )}
      <Field label="Username" error={errors.username?.message}>
        {(props) => <Input {...props} autoComplete="off" {...register("username")} />}
      </Field>
      <Field label="Email" error={errors.email?.message}>
        {(props) => <Input {...props} type="email" autoComplete="off" {...register("email")} />}
      </Field>
      <Field label="Temporary password" error={errors.password?.message} hint="At least 10 characters.">
        {(props) => <Input {...props} type="password" autoComplete="new-password" {...register("password")} />}
      </Field>
      <Field label="Role" error={errors.role?.message}>
        {(props) => (
          <Select {...props} {...register("role")}>
            <option value="user">User</option>
            <option value="admin">Admin</option>
          </Select>
        )}
      </Field>
      <div className="mt-2 flex justify-end gap-2">
        <Button variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" loading={isSubmitting}>
          Create user
        </Button>
      </div>
    </form>
  );
}
