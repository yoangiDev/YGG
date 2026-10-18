import { LEGAL, operatorLine } from "./entity";

export interface LegalSection {
  heading: string;
  paragraphs?: string[];
  list?: string[];
}

export interface LegalDocument {
  title: string;
  sections: LegalSection[];
}

/*
 * Drafts ready to publish. They are written about what the site really does (what it stores, who it sends it to,
 * how long it keeps it) and with the usual structure of League stats sites. They are a basis, not legal
 * advice: have them reviewed by an accountant or a lawyer before opening the site. And they are not true until they are:
 * the cookie consent notice must be working the day it is published.
 * When what the site does with the data changes, change it here too.
 */
export const DOCUMENTS: Record<string, LegalDocument> = {
  terms: {
    title: "Terms of Service",
    sections: [
      {
        heading: "1. Who we are and what you agree to",
        paragraphs: [
          `YGG is operated by ${operatorLine()} (“we”, “us”). By creating an account or using YGG you agree to these terms and to our Privacy Policy and Cookie Policy. If you don't agree, don't use the service.`,
          "You must be at least 16 years old to use YGG.",
        ],
      },
      {
        heading: "2. What YGG does",
        paragraphs: [
          "YGG analyses your own League of Legends games: it reads your match history and the replays you upload, measures how you played and compares it with other players of your rank and role. It gives you a rating, the moments that decided each game and an AI-written review.",
          "The analysis is informational. It isn't professional coaching and it doesn't guarantee that you will improve or climb.",
        ],
      },
      {
        heading: "3. Your account",
        list: [
          "Give us a real email address and keep your password secret. You are responsible for what happens under your account.",
          "One person, one account. Don't share it or sell it.",
          "Tell us at once if you think someone else has access to it.",
        ],
      },
      {
        heading: "4. Linking League accounts",
        paragraphs: [
          "You can link up to five League of Legends accounts, and only accounts that you own. To prove it, YGG asks you to set a specific profile icon in your League client and checks it with Riot's API. An account can be verified by one YGG user at a time. Unverified accounts can't be used to analyse replays.",
        ],
      },
      {
        heading: "5. Uploading replays",
        paragraphs: [
          "To analyse a game you download its replay (.rofl) from your own League client and upload it to YGG. By uploading a file you confirm that you played that game with one of your verified accounts.",
          "Before accepting a file we check that it is a valid replay, that it belongs to the game you picked and that you played it. We reject anything that doesn't pass. The replay file is deleted as soon as it has been processed; the Privacy Policy explains what we keep.",
        ],
      },
      {
        heading: "6. Acceptable use",
        paragraphs: ["Don't:"],
        list: [
          "upload files that aren't genuine replays of your own games, or files designed to harm or overload the service;",
          "use automated queries, bots, scraping or crawling on YGG without our written permission (search engines may index public pages within the limits of copyright law);",
          "bypass or try to bypass limits, verification or security measures;",
          "analyse games of accounts that aren't yours, or use YGG to harass, stalk or gain an unfair advantage over other players;",
          "reverse engineer, copy, resell or redistribute the service or its data;",
          "break the law or the rules of Riot Games.",
        ],
      },
      {
        heading: "7. AI-generated reviews",
        paragraphs: [
          "Reviews are written by an AI model from the numbers measured in your games. They can be wrong or incomplete. Use your own judgement.",
        ],
      },
      {
        heading: "8. Intellectual property and your content",
        paragraphs: [
          "YGG, its software, design and the benchmarks and ratings it produces belong to us. Riot Games' names, champions, items and images belong to Riot Games.",
          "You keep your rights in what you upload. You give us a licence to process your replays and game data to provide the service to you. You also allow us to use the games you analyse, as game data only and without your identity, to produce statistics and to train and improve our own analysis and coaching models and the benchmarks your results are compared with, and we may keep that game data after you delete your account. We won't publish your individual games or identify you, and you can object to this use (see the Privacy Policy).",
        ],
      },
      {
        heading: "9. Feedback",
        paragraphs: [
          "If you send us comments, questions or suggestions, you give us a free, perpetual, irrevocable and worldwide licence to use them for any purpose without having to pay or credit you. We have no duty of confidentiality about them.",
        ],
      },
      {
        heading: "10. Riot Games",
        paragraphs: [
          "YGG isn't endorsed by Riot Games and doesn't reflect the views or opinions of Riot Games or anyone officially involved in producing or managing Riot Games properties. Riot Games, and all associated properties are trademarks or registered trademarks of Riot Games, Inc. League of Legends © Riot Games, Inc.",
          "YGG uses Riot's public API and is bound by Riot's API terms; if Riot restricts access to its data, parts of YGG may stop working.",
        ],
      },
      {
        heading: "11. Links to other websites",
        paragraphs: [
          "YGG may link to websites or services that we don't own or control. We aren't responsible for their content, privacy policies or practices, or for any loss that comes from using them. Read their terms and policies before you use them.",
        ],
      },
      {
        heading: "12. Availability and changes to the service",
        paragraphs: [
          "We try to keep YGG running but we don't promise it will always be available or free of errors. We may change, suspend or stop any part of the service, for example when a new patch needs work before its games can be analysed.",
        ],
      },
      {
        heading: "13. Liability",
        paragraphs: [
          "YGG is provided “as is”. To the extent the law allows, we, and anyone working for us, aren't liable for lost profits, or for indirect, special, punitive or consequential losses, arising from the use of, or the inability to use, YGG, even if we were told they were possible; nor for losses caused by Riot's changes, by third-party services or by something outside our control. Nothing in these terms limits liability that can't be limited by law, including your rights as a consumer.",
        ],
      },
      {
        heading: "14. Ending your use",
        paragraphs: [
          "You can stop using YGG at any time and ask us to delete your account (see the Privacy Policy). We may suspend or close accounts that break these terms, without notice when the breach is serious. Sections that by their nature should survive (ownership, disclaimers, liability and governing law) survive the end of your use.",
        ],
      },
      {
        heading: "15. Changes to these terms",
        paragraphs: [
          "We may update these terms. We will post the new version here with its date and, if the change is important, tell you by email or in the app. Continuing to use YGG after that means you accept the new terms. Please check this page from time to time.",
        ],
      },
      {
        heading: "16. Governing law and general",
        paragraphs: [
          `These terms are governed by the laws of ${LEGAL.country}, without removing the mandatory consumer protections of the country where you live. If a provision is found to be invalid, the rest stays in force. Not enforcing a right doesn't mean we give it up. These terms are the whole agreement between you and us about YGG.`,
          `Questions: ${LEGAL.email}. Last updated: ${LEGAL.updated}.`,
        ],
      },
    ],
  },

  privacy: {
    title: "Privacy Policy",
    sections: [
      {
        heading: "1. Introduction",
        paragraphs: [
          "This policy explains what personal data YGG collects, why, who receives it and what rights you have. It applies to all users. By using YGG you confirm that you have read it together with the Terms of Service.",
          `We may update it, for example when the law or our service changes. We will post the new version here with its date. Last updated: ${LEGAL.updated}.`,
        ],
      },
      {
        heading: "2. Who is responsible",
        paragraphs: [`${operatorLine()} is the controller of your personal data. Contact: ${LEGAL.email}.`],
      },
      {
        heading: "3. Principles we follow",
        list: [
          "Purpose: we collect data for specific, clear and legitimate purposes, and don't use it later in ways that don't fit them.",
          "Minimisation: we only collect what we need and keep it up to date.",
          "Transparency: we tell you what we do with your data, here and where we collect it.",
        ],
      },
      {
        heading: "4. What we collect and how",
        paragraphs: ["Data you give us, data we get from Riot, and technical data from your use of YGG:"],
        list: [
          "Account: your email, username and a hash of your password (we never store the password itself).",
          "Linked League accounts: Riot ID, region, rank, profile icon, the account identifier (PUUID) Riot assigns and the verification icon we asked you to set.",
          "Game data from Riot's API: the match history and timelines of the accounts you link.",
          "Replays you upload: the file is used to read the game and deleted when processing ends. We keep the decoded game data (the events of the game) and the analysis (rating, moments, statistics and the AI review). The decoded game data is stored under the game's ID, not under your account.",
          "Usage: which games you analysed and when (to apply usage limits) and the snapshots you create.",
          "Technical: your IP address, browser details, pages viewed and connection dates, collected in server logs and, with your consent where the law requires it, by cookies (see the Cookie Policy).",
        ],
      },
      {
        heading: "5. Why we use it and on what basis",
        list: [
          "To create your account, verify your accounts and provide the analysis you ask for: performance of a contract.",
          "To keep YGG secure, prevent abuse, apply limits and fix errors: our legitimate interest.",
          "To produce statistics, and to train and improve our own analysis and coaching models (how ratings are calculated, the patterns we look for and the benchmarks you are compared with), using the games analysed on YGG. Only game data is used: your email, username and Riot ID aren't part of it, and the game is stored under its game ID, not under your account. This is our legitimate interest and you can object to it at any time (section 10).",
          "We send you service messages (such as password or security notices). We don't send marketing without your consent.",
        ],
      },
      {
        heading: "6. Who receives your data",
        paragraphs: [
          "Only people at YGG who need it to do their work can access your data. We share it with the providers that run the service for us, with Riot to fetch your games, and with authorities when the law requires it:",
        ],
        list: [
          "Riot Games: your Riot ID and region are sent to Riot's API to look up your account and games.",
          "Hosting, database, storage and content delivery providers: [hosting provider], [database provider], [storage / CDN provider].",
          "AI provider (Anthropic): the statistics and in-game moments of the game being reviewed are sent to write the review. We don't send your email, username or Riot ID, and under our agreement with them this data isn't used to train their models.",
          "Error monitoring (Sentry), if enabled: technical error reports that may include your IP address.",
        ],
      },
      {
        heading: "7. Content loaded from Riot",
        paragraphs: [
          "Champion, item and rune images are loaded directly by your browser from Riot's Data Dragon and Community Dragon servers, which therefore receive your IP address. We don't control their cookies or logs.",
        ],
      },
      {
        heading: "8. Transfers outside the EEA",
        paragraphs: [
          "Some providers (for example Google, the AI provider, Riot and cloud services) may process data outside the European Economic Area. When they do, we rely on adequacy decisions or standard contractual clauses.",
        ],
      },
      {
        heading: "9. How long we keep it",
        list: [
          "Replay files: deleted when processing ends, and any left over after a failure when the server restarts.",
          "Analyses, snapshots and linked accounts: while your account exists. Unlinking an account deletes its snapshots.",
          "Decoded game data: kept after you delete your account, because it isn't linked to it (it's stored under the game ID). It is used for statistics and to train our models. If you ask us to remove a game, we delete its data and stop using it; models already trained aren't undone.",
          "Account data: until you delete your account.",
          "IP addresses, browsing data and request and error logs: one month from the last activity.",
          "Requests to exercise your rights: kept as proof for as long as claims could still be made, and in any case no more than five years.",
          "Anonymised, aggregated statistics aren't personal data and may be kept.",
        ],
      },
      {
        heading: "10. Your rights",
        paragraphs: ["You have the right to:"],
        list: [
          "access your data and get confirmation of whether we process it;",
          "correct it if it is inaccurate or incomplete;",
          "ask us to delete it;",
          "ask us to restrict its processing;",
          "receive it, or have it sent to another controller (portability);",
          "object to some uses, such as using your games to train our models, or marketing; if you object, tell us the game ID of the games and we delete their data and stop using them;",
          "withdraw any consent you gave, without affecting what we did before;",
          "complain to the Spanish Data Protection Agency (AEPD, aepd.es) or to your local authority.",
        ],
      },
      {
        heading: "11. How to use your rights",
        paragraphs: [
          `Write to ${LEGAL.email} from the address of your account. If we can't tell it's you, we may ask you to prove it. We answer within one month. To delete your account, ask us at that address: we will delete your account, linked accounts, snapshots and analyses. We may have to keep some data as proof in case of a dispute or because the law requires it.`,
        ],
      },
      {
        heading: "12. Security",
        paragraphs: [
          "We use technical and organisational measures that fit the sensitivity of the data, to protect it from intrusion, loss, alteration and disclosure. Passwords are stored hashed. Sessions use short-lived tokens and a refresh cookie that scripts can't read. Uploaded files are validated before they are processed, and each upload is processed in isolation and deleted afterwards. We choose our providers carefully and require them to protect data as we do, to use it only for the service they give us and to follow the law. Security also depends on you: use a strong, unique password.",
        ],
      },
      {
        heading: "13. Children",
        paragraphs: ["YGG is for people aged 16 or over. If you think a child has signed up, tell us and we will delete the account."],
      },
      {
        heading: "14. External links",
        paragraphs: [
          "YGG may link to other websites. Their operators may collect or share data under their own policies, which can differ from this one. Please read them.",
        ],
      },
      {
        heading: "15. Contact",
        paragraphs: [`Questions or requests about your data: ${LEGAL.email}.`],
      },
    ],
  },

  cookies: {
    title: "Cookie Policy",
    sections: [
      {
        heading: "1. What cookies are",
        paragraphs: [
          "Cookies are small text files that your browser stores when you visit a website. Similar technologies, such as your browser's local storage, work the same way. We use both, and in this policy “cookies” means all of them.",
        ],
      },
      {
        heading: "2. Strictly necessary",
        paragraphs: ["These make YGG work and don't need your consent:"],
        list: [
          "Session cookie (refresh token): keeps you signed in. It's HttpOnly, so scripts can't read it, and it expires after 14 days or when you sign out.",
          "Local storage: remembers which of your accounts is selected and which analyses are running in the background, so they survive a reload. It stays on your device.",
          "Your cookie choices, once you make them.",
        ],
      },
      {
        heading: "3. Third-party content",
        paragraphs: [
          "Game images come from Riot's servers (Data Dragon and Community Dragon). When your browser loads them, Riot receives your IP address and may use its own technical cookies. See Riot's own policy for details.",
        ],
      },
      {
        heading: "4. How to manage them",
        paragraphs: [
          "You can accept, refuse or change your cookie choices from the cookie settings, and delete or block cookies from your browser settings. If you block the strictly necessary ones, you won't be able to sign in.",
          `Questions: ${LEGAL.email}. Last updated: ${LEGAL.updated}.`,
        ],
      },
    ],
  },
};
