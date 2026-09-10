import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, use, useCallback, useEffect, useMemo, type ReactNode } from "react";

import { api, isApiError, refreshAccessToken, tokenStore, unwrap, type Schemas } from "@/lib/api/client";
import { queryKeys } from "@/lib/queryKeys";

export type User = Schemas["UserResponse"];
export type AuthStatus = "loading" | "authenticated" | "anonymous" | "error";

interface AuthContextValue {
  status: AuthStatus;
  user: User | null;
  isAdmin: boolean;
  error: unknown;
  retry: () => void;
  login: (credentials: Schemas["UserLogin"]) => Promise<User>;
  register: (data: Schemas["UserRegister"]) => Promise<User>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

/** Al cargar la página no hay access token en memoria: se intenta recuperar la sesión con la cookie de refresh. */
async function loadSession(): Promise<User | null> {
  if (!tokenStore.get() && !(await refreshAccessToken())) return null;
  try {
    return await unwrap(api.GET("/auth/me"));
  } catch (error) {
    if (isApiError(error, 401)) return null;
    throw error;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const session = useQuery({
    queryKey: queryKeys.me,
    queryFn: loadSession,
    staleTime: Number.POSITIVE_INFINITY,
    gcTime: Number.POSITIVE_INFINITY,
    retry: false,
  });

  // Si un refresh falla a mitad de sesión (token revocado, cookie caducada), se vuelve al login.
  useEffect(
    () =>
      tokenStore.subscribe((token) => {
        if (token === null && queryClient.getQueryData(queryKeys.me)) {
          queryClient.setQueryData(queryKeys.me, null);
        }
      }),
    [queryClient],
  );

  const completeSignIn = useCallback(
    async (tokens: Schemas["TokenResponse"]) => {
      tokenStore.set(tokens.access_token);
      const user = await unwrap(api.GET("/auth/me"));
      queryClient.setQueryData(queryKeys.me, user);
      return user;
    },
    [queryClient],
  );

  const login = useCallback(
    async (credentials: Schemas["UserLogin"]) =>
      completeSignIn(await unwrap(api.POST("/auth/login", { body: credentials }))),
    [completeSignIn],
  );

  const register = useCallback(
    async (data: Schemas["UserRegister"]) => completeSignIn(await unwrap(api.POST("/auth/register", { body: data }))),
    [completeSignIn],
  );

  const logout = useCallback(async () => {
    try {
      await api.POST("/auth/logout");
    } catch {
      // Sin conexión: la sesión se descarta igualmente en el cliente.
    }
    tokenStore.set(null);
    queryClient.removeQueries({ predicate: (query) => query.queryKey[0] !== queryKeys.me[0] });
    queryClient.setQueryData(queryKeys.me, null);
  }, [queryClient]);

  const { refetch } = session;
  const retry = useCallback(() => void refetch(), [refetch]);

  const user = session.data ?? null;
  const status: AuthStatus = session.isPending
    ? "loading"
    : session.isError
      ? "error"
      : user
        ? "authenticated"
        : "anonymous";

  const value = useMemo<AuthContextValue>(
    () => ({ status, user, isAdmin: user?.role === "admin", error: session.error, retry, login, register, logout }),
    [status, user, session.error, retry, login, register, logout],
  );

  return <AuthContext value={value}>{children}</AuthContext>;
}

export function useAuth(): AuthContextValue {
  const context = use(AuthContext);
  if (!context) throw new Error("useAuth must be used inside <AuthProvider>");
  return context;
}
