/**
 * The details of whoever publishes YGG, in one place: the only thing to fill in before publishing. Everything
 * else (terms, privacy, cookies, footer) already reads them from here. Texts that start with "[" are
 * blanks; the footer warns in development while any remain.
 */
export const LEGAL = {
  operator: "[Your full name]",
  email: "[contact@your-domain]",
  country: "Spain",
  updated: "8 October 2026",
  // The name and email are enough to start. If a postal address and a tax ID are needed, fill them in here;
  // they appear in the texts by themselves.
  address: "",
  taxId: "",
};

/** Who publishes YGG, as written in the texts: the name and, if filled in, the address and tax ID. */
export const operatorLine = () =>
  [LEGAL.operator, LEGAL.address, LEGAL.taxId && `NIF ${LEGAL.taxId}`].filter(Boolean).join(", ");

/** A legal detail already filled in: the blanks are the texts that start with «[». */
export const isFilled = (value: string) => !value.startsWith("[");

export const pendingLegalDetails = Object.values(LEGAL).some((value) => !isFilled(value));

/** The text Riot Games requires from whoever uses its API (Developer Portal → Policies). */
export const RIOT_DISCLAIMER =
  "YGG isn't endorsed by Riot Games and doesn't reflect the views or opinions of Riot Games or anyone officially involved in producing or managing Riot Games properties. Riot Games, and all associated properties are trademarks or registered trademarks of Riot Games, Inc.";

/** The links to YGG's social networks, for the profile menu. Empty = the icon appears dimmed until you fill it in. */
export const SOCIALS = { discord: "", x: "", instagram: "", tiktok: "" };
