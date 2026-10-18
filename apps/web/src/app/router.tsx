import { createBrowserRouter, Navigate } from "react-router";

import { FullPageLoader, RequireAdmin, RequireAuth } from "@/features/auth/guards";

import { NotFound, RouteError } from "./RouteError";

/**
 * Each screen is a separate chunk (route.lazy), and so is the app's frame:
 * the login doesn't download Recharts, TanStack Table or the Radix menus, and the
 * admin panel is only downloaded by whoever opens it. React Router requests the route's
 * chunk in parallel with the session check.
 */
export const router = createBrowserRouter([
  {
    // public: read before signing up
    path: "/legal/:doc",
    lazy: () => import("@/features/legal/LegalPage").then((m) => ({ Component: m.LegalPage })),
    errorElement: <RouteError />,
    hydrateFallbackElement: <FullPageLoader />,
  },
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
              { index: true, element: <Navigate to="/account" replace /> },
              {
                path: "account",
                lazy: () => import("@/features/players/AccountPage").then((m) => ({ Component: m.AccountPage })),
              },
              // one account per user: the players list no longer exists and its page is the one at /account
              { path: "players", element: <Navigate to="/account" replace /> },
              { path: "players/:playerId", element: <Navigate to="/account" replace /> },
              {
                path: "players/:playerId/snapshots/compare",
                lazy: () => import("@/features/snapshots/ComparePage").then((m) => ({ Component: m.ComparePage })),
              },
              {
                path: "players/:playerId/snapshots/:snapshotId",
                lazy: () => import("@/features/snapshots/SnapshotPage").then((m) => ({ Component: m.SnapshotPage })),
              },
              { path: "games", element: <Navigate to="/account" replace /> },
              {
                path: "analysis/:matchId",
                lazy: () => import("@/features/games/GameAnalysisPage").then((m) => ({ Component: m.GameAnalysisPage })),
              },
              {
                path: "cutoffs",
                lazy: () => import("@/features/cutoffs/CutoffsPage").then((m) => ({ Component: m.CutoffsPage })),
              },
              {
                path: "ranks",
                lazy: () => import("@/features/ranks/RankStatsPage").then((m) => ({ Component: m.RankStatsPage })),
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
