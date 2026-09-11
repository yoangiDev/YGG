import { createBrowserRouter, Navigate } from "react-router";

import { FullPageLoader, RequireAdmin, RequireAuth } from "@/features/auth/guards";

import { NotFound, RouteError } from "./RouteError";

/**
 * Cada pantalla es un chunk aparte (route.lazy), y también el marco de la app:
 * el login no descarga Recharts, TanStack Table ni los menús de Radix, y el
 * panel de administración solo lo baja quien lo abre. React Router pide el chunk
 * de la ruta en paralelo con la comprobación de sesión.
 */
export const router = createBrowserRouter([
  {
    path: "/login",
    lazy: () => import("@/features/auth/LoginPage").then((m) => ({ Component: m.LoginPage })),
    errorElement: <RouteError />,
    hydrateFallbackElement: <FullPageLoader />,
  },
  {
    element: <RequireAuth />,
    errorElement: <RouteError />,
    hydrateFallbackElement: <FullPageLoader />,
    children: [
      {
        lazy: () => import("./AppLayout").then((m) => ({ Component: m.AppLayout })),
        children: [
          {
            errorElement: <RouteError />,
            children: [
              { index: true, element: <Navigate to="/players" replace /> },
              {
                path: "players",
                lazy: () => import("@/features/players/PlayersPage").then((m) => ({ Component: m.PlayersPage })),
              },
              {
                path: "players/:playerId",
                lazy: () =>
                  import("@/features/players/PlayerDetailPage").then((m) => ({ Component: m.PlayerDetailPage })),
              },
              {
                path: "players/:playerId/snapshots/compare",
                lazy: () => import("@/features/snapshots/ComparePage").then((m) => ({ Component: m.ComparePage })),
              },
              {
                path: "players/:playerId/snapshots/:snapshotId",
                lazy: () => import("@/features/snapshots/SnapshotPage").then((m) => ({ Component: m.SnapshotPage })),
              },
              {
                path: "cutoffs",
                lazy: () => import("@/features/cutoffs/CutoffsPage").then((m) => ({ Component: m.CutoffsPage })),
              },
              {
                path: "admin",
                element: <RequireAdmin />,
                children: [
                  {
                    lazy: () => import("@/features/admin/AdminLayout").then((m) => ({ Component: m.AdminLayout })),
                    children: [
                      { index: true, element: <Navigate to="stats" replace /> },
                      {
                        path: "stats",
                        lazy: () =>
                          import("@/features/admin/AdminStatsPage").then((m) => ({ Component: m.AdminStatsPage })),
                      },
                      {
                        path: "users",
                        lazy: () =>
                          import("@/features/admin/AdminUsersPage").then((m) => ({ Component: m.AdminUsersPage })),
                      },
                      {
                        path: "players",
                        lazy: () =>
                          import("@/features/admin/AdminPlayersPage").then((m) => ({
                            Component: m.AdminPlayersPage,
                          })),
                      },
                    ],
                  },
                ],
              },
              { path: "*", element: <NotFound /> },
            ],
          },
        ],
      },
    ],
  },
]);
