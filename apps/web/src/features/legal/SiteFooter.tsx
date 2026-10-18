import { Link } from "react-router";

import { isFilled, LEGAL, pendingLegalDetails, RIOT_DISCLAIMER } from "./entity";

const LINKS = [
  { to: "/legal/terms", label: "Terms" },
  { to: "/legal/privacy", label: "Privacy" },
  { to: "/legal/cookies", label: "Cookies" },
];

/** The legal links on one line: also used on the login. */
export function LegalLinks({ className }: { className?: string }) {
  return (
    <nav aria-label="Legal" className={className ?? "flex flex-wrap gap-x-6 gap-y-2 text-sm text-muted"}>
      {LINKS.map(({ to, label }) => (
        <Link key={to} to={to} className="-my-1 py-1 transition-colors hover:text-text">
          {label}
        </Link>
      ))}
      {isFilled(LEGAL.email) && (
        <a href={`mailto:${LEGAL.email}`} className="-my-1 py-1 transition-colors hover:text-text">
          Contact
        </a>
      )}
    </nav>
  );
}

/** The footer of all screens: the legal links, Riot's notice and the copyright. It starts where the content does. */
export function SiteFooter() {
  return (
    <footer className="mt-12 border-t border-line">
      <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-8 sm:px-6">
        <LegalLinks />
        <p className="max-w-4xl text-xs text-subtle">{RIOT_DISCLAIMER}</p>
        <p className="text-xs text-subtle">
          © {new Date().getFullYear()} {isFilled(LEGAL.operator) ? LEGAL.operator : "YGG"}. Game images © Riot Games, Inc.
        </p>
        {import.meta.env.DEV && pendingLegalDetails && (
          <p className="text-xs text-stat-gold">Fill in your name and email in features/legal/entity.ts before publishing.</p>
        )}
      </div>
    </footer>
  );
}
