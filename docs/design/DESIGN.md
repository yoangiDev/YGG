> **External visual reference.** This document describes the design system of another project, on which the `apps/web` redesign is based; the `src/…` and `academy/…` paths belong to that project, not to this repository. YGG's brand is **YGG**.

# Elopeak design system

A reference guide for building any Elopeak screen with the same look as the current website. All the values come from `src/app/globals.css`; if you change something there, update this document too.

---

## 1. Visual character

- **Dark and competitive.** The background is almost black and a single accent colour, acid green, stands out on it. Light cream sections give a breather between the dark ones.
- **Square corners.** Buttons, cards, inputs and modals are not rounded. Only the dots, the avatars and the map labels are circular.
- **Heavy, tight headlines.** Weight 900, very negative letter-spacing and line-height below 1.
- **Uppercase microtext.** Labels, buttons and captions are set in small capitals with a lot of letter-spacing.
- **Acid tab.** Featured cards carry a short green strip in the top-left corner. It is the brand's visual signature (see §6.3).
- **The brand is written "Elopeak"**, with a capital E, in any visible text. Lowercase only in the domain and in identifiers.

---

## 2. Colour palette

### 2.1 Tokens (CSS variables)

Defined in `:root`. Always use one when it exists for that colour.

| Token | Value | Use |
|---|---|---|
| `--ink` | `#080a0b` | Base background of the page and of `html` |
| `--ink-soft` | `#101315` | Secondary dark background |
| `--panel` | `#15191b` | Card surfaces |
| `--panel-light` | `#1b2022` | Elevated surface |
| `--line` | `rgba(255,255,255,.11)` | Borders and dividers on a dark background |
| `--text` | `#f4f6f1` | Main text on dark |
| `--muted` | `#9ca39f` | Secondary text on dark |
| `--acid` | `#c8f53f` | **Brand accent.** CTAs, emphasis and active states |
| `--acid-dark` | `#9dbf31` | Muted accent (list bullets) |
| `--acid-accessible` | `#526814` | Accent for small text **on a light background** |
| `--cream` | `#f0f0e8` | Background of the light sections |
| `--dark-text` | `#111412` | Text on cream and on acid green |

### 2.2 Acid green variants

| Value | Use |
|---|---|
| `#d5ff55` / `#d5ff50` | Hover of the primary button |
| `#8ea92f` | Coaches footer links and Academy secondary links |
| `#7f9b26` | `<em>` of the h2 headlines on cream (large size only) |
| `#7e9b23` / `#718d1e` | FAQ accordion icon and hover |
| `rgba(200,245,63,.06–.12)` | Tinted backgrounds and halos |
| `rgba(200,245,63,.18)` | Button hover shadow |
| `rgba(200,245,63,.22–.35)` | Accent borders (cards, labels) |
| `rgba(200,245,63,.48–.52)` | Accent border on hover |

### 2.3 Dark grey scale (text and borders on a dark background)

From lightest to darkest. These are fixed values, not tokens.

| Value | Typical use |
|---|---|
| `#dce0dc` / `#d5ddd7` | Highlighted text, form labels |
| `#c9ccca` / `#c4c8c4` / `#c0c6c2` | Navigation links, notice text |
| `#a9afab` / `#a2aaa4` | Lead text, footer links |
| `#929a94` / `#979f99` | Supporting text in cards |
| `#7f8781` / `#778079` | Captions, language selector |
| `#6f7771` / `#69716c` / `#5e6661` | Low-priority microtext |
| `#434946` / `#4c544d` / `#3a423d` / `#343b37` | Secondary button borders and underlines |
| `#2c3430` | Input border |

### 2.4 Dark backgrounds by section

| Value | Where |
|---|---|
| `#080a0a` | Footer |
| `#0b0e0f` | "Method" section, header of the coaches page |
| `#0c0f0e` | Inputs and dropdowns |
| `#0c0f10` | Expanded mobile menu |
| `#0c1010` | CTA of the coaches page |
| `#101412` | Booking modal |
| `#101415` | Reviews section |
| `#111516` | Step cards |
| `#171b19` | Booking card (price) |
| `#171c1d` | Review card |
| `#182018` / `#182019` | Highlighted step / step hover |

### 2.5 Light surfaces (cream sections)

| Value | Use |
|---|---|
| `#f0f0e8` (`--cream`) | Section background |
| `#f7f7f1` | Card on cream |
| `#f1f2ea` / `#e8e9e1` / `#e6e8dd` | Inner blocks, quotes, role selector |
| `#dfe3d4` / `#e0e2d7` | Chips and hover |
| `#d1d3ca` / `#cdd0c6` / `#cacdc3` | Borders on cream |
| `#777d78` / `#697069` / `#656b66` | Secondary text on cream |
| `#252b25` / `#222722` | Highlighted text on cream |

### 2.6 Status and map colours

| Value | Use |
|---|---|
| `#ffb4b4` | Form error message |
| `#5bc2ff` / `#79d1ff` | Blue side of the map |
| `#ff6979` / `#ff919d` | Red side of the map |
| `rgba(205,168,255,.5)` | Border of the Baron label |
| `rgba(255,145,95,.5)` | Border of the Dragon label |

### 2.7 Contrast (WCAG)

Measured with the relative luminance formula. AA requires 4.5:1 for normal text and 3:1 for large text (≥24 px, or ≥18.7 px in bold).

| Text / background | Ratio | Result |
|---|---|---|
| `--text` on `--ink` | 18.2 | AAA |
| `--acid` on `--ink` | 15.7 | AAA |
| Button text `#0a0c08` on `--acid` | 15.5 | AAA |
| `--dark-text` on `--cream` | 16.2 | AAA |
| `--muted` on `--ink` | 7.7 | AAA |
| `#8ea92f` on `--ink` | 7.4 | AAA |
| `--acid-accessible` on `--cream` | 5.5 | AA |
| `#7f8781` on `--ink` | 5.4 | AA |
| `#6f7771` on footer | 4.3 | Large text only |
| `#777d78` on `--cream` | 3.7 | Large text only |
| `#69716c` on `--panel` | 3.5 | Large text only |
| `#5e6661` on `--ink` | 3.4 | Large text only |
| `#7f9b26` on `--cream` | 2.8 | **Fails.** Only in very large headlines |
| `--acid` on `--cream` | 1.1 | **Never use** |

> **Rule:** on a light background, the green is always `--acid-accessible`. Pure `--acid` only works on dark or as a background with dark text on top.

---

## 3. Typography

> **The web app's scale (08-10).** A single family, Geist (the logo's), and nothing else: no monospace. Six sizes (`text-xs` 12 · `sm` 14 · `base` 16 · `lg` 18 · `xl` 24 · `2xl` 32) and three weights (normal 400, `bold` 700 and `black` 900). Loose sizes (`text-[13px]`) are not written: if it doesn't fit the scale, the scale changes. The history uses the accent for what matters (the analysis, the MVP), blue and red for winning and losing, and grey for everything else. No gradients, glows or decorative backgrounds.

### 3.1 Families

| Role | Font | CSS variable | Fallback stack |
|---|---|---|---|
| Main | **Geist** (Google Fonts, `next/font`) | `--font-geist-sans` | `Arial, Helvetica, sans-serif` |
| Monospace | **Geist Mono** | `--font-geist-mono` | `monospace` |
| Quotes and reviews | **Georgia** (system) | — | `serif` |

They are loaded in `src/app/layout.tsx` with `subsets: ["latin"]` and `display: "swap"` on the main one. The mono is used in codes and technical labels (`404`, "DECISION EXAMPLE").

> **Academy** (`academy/assets/academy.css`) is static HTML and uses only `Arial, Helvetica, sans-serif`, without Geist.

```css
body {
  font-family: var(--font-geist-sans), Arial, Helvetica, sans-serif;
  -webkit-font-smoothing: antialiased;
}
```

### 3.2 Weights

| Weight | Use |
|---|---|
| 500 | Text inside inputs and dropdown options |
| 700 | Navigation links |
| 800 | Labels, text-links, FAQ questions |
| 900 | Brand, buttons, captions and h3 |
| 950 | Display headlines (h1/h2) |

> Variable Geist goes up to 900, so `950` is rendered as 900. It is kept in the CSS in case the font is ever changed to one with a Black weight.

### 3.3 Type scale

| Level | Size | Line-height | Letter-spacing | Weight |
|---|---|---|---|---|
| **Display XL** (h1 of the coaches page) | `clamp(54px, 7vw, 96px)` | .9 | -.07em | 950 |
| **Display** (home h1, final CTA) | `clamp(52px, 5.2vw, 78px)` | .94 | -.065em | 950 |
| **404** | `clamp(44px, 8vw, 86px)` | .9 | -.065em | 950 |
| **Section H2** | `clamp(40px, 4.5vw, 62px)` | .94 | -.065em | 950 |
| **Directory/CTA H2** | `clamp(40px, 5vw, 68px)` | .95 | -.055em to -.06em | 950 |
| **Legal H1** | `clamp(34px, 6vw, 60px)` | .95 | -.06em | 950 |
| **Coach H3** | 38px (32px on mobile) | — | -.055em | bold |
| **Modal H2** | `clamp(26px, 3.4vw, 36px)` | .9 | -.055em | 950 |
| **Card H3** | 30px (25px on mobile) | — | -.045em | bold |
| **Highlighted quote** | 18px | 1.35 | -.025em | 800 |
| **Step H3** | 18px | — | -.03em | bold |
| **Review** (Georgia) | 22px (19px on mobile) | 1.5 | — | 400 |
| **Lead** | 16px | 1.7 | — | 400 |
| **Body** | 14–15px | 1.7–1.75 | — | 400 |
| **Small** | 13px | 1.65–1.7 | — | 400 |
| **Button** | 12px (11px small, 10px outline) | — | .045em | 900, UPPERCASE |
| **Section caption** | 13px | — | .19em | 900, UPPERCASE |
| **Microtext** | 9–11px | — | .08em to .16em | 900, UPPERCASE |

Reductions on mobile: the home h1 to 46px (≤640) and `clamp(38px, 12vw, 46px)` (≤420); the section h2 to 39px and then 34px; the final CTA to 43px and then 36px.

### 3.4 Headline with an accent line

The pattern for every large headline: the second line is in green.

```html
<!-- On dark: the accent drops to its own line -->
<h1>Climb the ladder <span>with a plan</span></h1>

<!-- On cream: the accent stays inline and uses the accessible green -->
<h2>Choose your <em>role</em></h2>
```

```css
.hero h1 span, .section-heading h2 em { display: block; color: var(--acid); font-style: normal; }
.coaching-section .section-heading h2 em { display: inline; color: #7f9b26; }
```

---

## 4. Layout and spacing

### 4.1 Container

```css
.shell { width: min(1180px, calc(100% - 48px)); margin-inline: auto; }
```

| Screen | Total side margin |
|---|---|
| > 640px | 48px (24 per side) |
| ≤ 640px | 30px |
| ≤ 420px | 24px |

The hero grid is wider: `min(1340px, calc(100% - 40px))`. The content of the legal pages is limited to 760px and centred blocks to 720, 760, 910 or 980px.

### 4.2 Breakpoints

| Name | Media query | What changes |
|---|---|---|
| Tablet | `max-width: 900px` | Hamburger menu; two-column grids become one |
| Mobile | `max-width: 640px` | 65px header, full-width buttons, the modal opens as a bottom sheet |
| Small mobile | `max-width: 420px` | More compact typography and paddings |

### 4.3 Heights and sections

| Element | Value |
|---|---|
| Header | 76px (65px on mobile), fixed, `rgba(8,10,11,.84)` + `backdrop-filter: blur(18px)` |
| Section | `min-height: 100svh`, vertical padding `clamp(78px, 10vh, 120px)` (78px on mobile) |
| Hero | `min-height: 100svh`, `padding-top` equal to the header height |
| Trust strip | 60px |
| Bottom footer | 62px |

### 4.4 Usual spacings

There is no formal scale. The values that repeat most are:

`4 · 6 · 8 · 10 · 12 · 14 · 16 · 18 · 20 · 22 · 24 · 28 · 32 · 40 · 48 · 60 · 75 · 100 · 120`

- Gap between buttons: 10–12px. Between a CTA and a text-link: 32px.
- Card padding: 35–55px on desktop and 20–27px on mobile.
- Gap between the columns of split layouts: 100px on desktop and 35–45px on tablet.

---

## 5. Borders, radii, shadows and layers

### 5.1 Radii

| Value | Where |
|---|---|
| `0` | **Default for everything** (buttons, cards, inputs, modals, chips) |
| `50%` | Status dots, avatars, halos |
| `999px` | The map's floating labels |
| `20px` | Only the map's 3D canvas |

### 5.2 Borders

- Standard divider: `1px solid var(--line)`.
- Accent border: `1px solid rgba(200,245,63,.22)` at rest and `.48` on hover.
- Side accent on quotes: `border-left: 2–3px solid var(--acid-accessible)` on light and `var(--acid)` on dark.
- On cream: `1px solid #d1d3ca`.

### 5.3 Shadows

| Name | Value |
|---|---|
| Button glow (hover) | `0 12px 34px rgba(200,245,63,.18)` |
| Floating card | `0 30px 80px rgba(0,0,0,.45)` |
| Floating card (hover) | `0 38px 100px rgba(0,0,0,.58), 0 0 45px rgba(200,245,63,.06)` |
| Popover panel | `0 24px 75px rgba(0,0,0,.52)` |
| Dropdown | `0 18px 44px rgba(0,0,0,.55)` |
| Card on cream | `0 16px 60px rgba(33,38,31,.08)` and `.14` on hover |
| Live-dot halo | `0 0 0 5px rgba(200,245,63,.1)` |

### 5.4 z-index scale

| Value | Element |
|---|---|
| 2 | Content above the decorative backgrounds |
| 10 | Hero card, map |
| 48 | Language notice |
| 49 | Floating cookie-settings button |
| 50 | Header |
| 100 | Cookie banner, skip-link |
| 120 | Booking modal |
| 130 | Elo selector list (portal above the modal) |

---

## 6. Buttons and links

All buttons are rectangular, uppercase, weight 900, and usually carry an `ArrowIcon` on the right.

### 6.1 Variants table

| Class | Height | Padding | Font | Background | Text | Border |
|---|---|---|---|---|---|---|
| `.button` (primary) | 52px | `0 23px` | 12px / .045em | `--acid` | `#0a0c08` | `--acid` |
| `.button.button-small` | 39px | `0 17px` | 11px | `--acid` | `#0a0c08` | `--acid` |
| `.button.button-full` | 52px | — | 12px | `--acid` | `#0a0c08` | width 100% |
| `.outline-button` (secondary) | 42px | `0 17px` | 10px | transparent | inherits | `#4c544d` |
| `.text-link` (tertiary) | auto | `0 0 5px` | 12px / .07em | — | `#c9ccca` | `#434946` underline |
| `.cookie-button-primary` | 43px | `0 18px` | 11px / .08em | `--acid` | `--dark-text` | — |
| `.cookie-button-secondary` | 43px | `0 18px` | 11px / .08em | transparent | `#c0c6c2` | `#3a423d` |
| Icon button (`.review-controls button`) | 38×38 | 0 | — | transparent | `#c9ccca` | `#343b37` |

### 6.2 States

| State | Primary | Outline | Icon |
|---|---|---|---|
| Hover | `translateY(-2px)`, background `#d5ff55`, glow `0 12px 34px rgba(200,245,63,.18)` | border and text `--acid` | border and text `--acid`, `translateY(-1px)` |
| Focus | `outline: 2px solid var(--acid); outline-offset: 4px` (`:focus-visible` only) | same | same |
| Disabled | **No style defined.** The form's submit uses `disabled` but doesn't change its look | — | — |

Transition: `transform .2s, background .2s, box-shadow .2s`.

### 6.3 Markup

```tsx
import ArrowIcon from "@/components/ArrowIcon";

<a className="button" href="#coaching">Book a session <ArrowIcon /></a>
<a className="button button-small" href="/coaches/">Coaches <ArrowIcon /></a>
<button className="button button-full" type="submit">Send request <ArrowIcon /></button>
<a className="outline-button" href={DISCORD_INVITE_URL}>Discord <ArrowIcon /></a>
<a className="text-link" href="#method">See the method <ArrowIcon direction="down" /></a>
```

In `.text-link` the arrow is in `--acid` and the text in grey. On mobile (≤640) the hero's buttons take the full width and stack in a column.

### 6.4 Navigation links

- Colour `#c4c8c4`, 13px, weight 700. On hover they turn `--acid`.
- They carry an animated underline: a 1px line in `--acid`, 9px below, that grows from left to right (`scaleX(0→1)`, .3s).
- Language selector: 11px, weight 900, `#7f8781`. The active language in `--acid` and the hover in white.

---

## 7. Iconography

### 7.1 ArrowIcon

`src/components/ArrowIcon.tsx`, viewBox `0 0 16 16`, drawn at 13×13px.

```css
.arrow-icon {
  width: 13px; height: 13px;
  stroke: currentColor; stroke-width: 1.8;
  stroke-linecap: square; stroke-linejoin: miter;   /* square tips, to match the corners */
}
```

Directions: `ne` (default, ↗), `down`, `left`, `right`.

### 7.2 Small graphic elements

| Element | Specification |
|---|---|
| Live dot (`.live-dot`) | 7×7, `--acid` circle, a halo that pulses every 2s |
| Status dot | 5×5, `--acid` circle |
| Diamond separator | 3×3, `--acid`, `rotate(45deg)` |
| Stars | `--acid`, 10px, `letter-spacing: 3px` |
| Select chevron | Two 5px triangles in `--acid` made with `linear-gradient` (no image) |
| Rank emblem | Hexagon with `clip-path: polygon(50% 0, 95% 25%, 83% 82%, 50% 100%, 17% 82%, 5% 25%)` |

---

## 8. Components

### 8.1 Section caption (eyebrow)

`.eyebrow`, `.section-number`, `.recommendation-kicker`, `.coach-role`:

```css
color: var(--acid);            /* --acid-accessible on cream */
font-size: 13px; font-weight: 900;
letter-spacing: .19em; text-transform: uppercase;
display: inline-flex; gap: 10px;   /* to fit a .live-dot in front */
```

The modal and cookie captions (`.booking-modal-kicker`, `.cookie-consent-kicker`) use the same formula at 10px with `.18em`.

### 8.2 Chips and labels

| Class | Style |
|---|---|
| `.role-tag` | Border `rgba(200,245,63,.35)`, text `--acid`, 10px/900, padding `5px 8px` |
| `.new-label` | Background `--acid`, text `#11150d`, 10px/900, padding `4px 7px` |
| `.rank-label` | Background `--acid`, text `#11150b`, 10px/950, `.16em` |
| `.academy-soon-badge` | Border `rgba(200,245,63,.35)`, text `--acid`, 11px/900, `.2em` |
| `.champion-pool strong` (on cream) | Background `#dfe3d4`, text `--acid-accessible`, 10px |

### 8.3 Cards

**Basic dark card recipe:**

```css
.card {
  position: relative;
  border: 1px solid rgba(200,245,63,.22);
  background: linear-gradient(145deg, rgba(27,33,31,.93), rgba(12,15,15,.96));
  box-shadow: 0 30px 80px rgba(0,0,0,.45);
}
.card::before {                    /* acid tab */
  content: ""; position: absolute; top: -1px; left: -1px;
  width: 75px; height: 2px;        /* 78×3 on the modal and cookies */
  background: var(--acid);
}
```

| Card | Background | Notes |
|---|---|---|
| `.rank-card` | 145° gradient (the recipe above) | Hover: `translateY(-8px) rotate(-.35deg)` |
| `.steps article` | `#111516` (highlighted `#182018` with `border-top: 2px solid var(--acid)`) | Decorative rings in the bottom corner |
| `.review-card` | `#171c1d`, `--line` border | 88px Georgia quotation mark in `#2b332d` |
| `.booking-card` | `#171b19` | Price at 26px with `-.05em` |
| `.recommendation` (cream) | `#f7f7f1`, border `#cacdc3` | Also carries the acid tab |
| `.duo-banner` | `linear-gradient(90deg, #162015, #111512)` | Accent border |

Cards are separated with shared 1px dividers, with no gaps between them (`.steps`, `.rank-stats`, `.coach-achievements`).

### 8.4 Forms

```css
label {                                   /* wrapping label */
  display: grid; gap: 7px;
  color: #d5ddd7; font-size: 11px; font-weight: 800;
  letter-spacing: .06em; text-transform: uppercase;
}
input, select {
  width: 100%; padding: 11px 13px;
  border: 1px solid #2c3430; background: #0c0f0e;
  color: white; font-size: 14px; font-weight: 500;
}
input:focus, select:focus { outline: 1px solid var(--acid); border-color: var(--acid); }
```

- On mobile (≤640) the inputs go to `font-size: 16px` and `min-height: 46px`, so iOS doesn't zoom on focus.
- The form uses two columns (`gap: 12px 14px`) and a single one on mobile.
- Error: `#ffb4b4`, 13px. Success: a title in `--acid` at 18px and text in `--muted`.
- Placeholder of the custom select: `#79817b`. Active option with background `#171c19`; the selected one, in `--acid`.
- Anti-spam trap field: `.booking-honeypot` (off-screen, never `display:none`).

### 8.5 Modal

- Backdrop layer `rgba(5,7,7,.72)`. Panel of `min(640px, 100%)`, maximum height `min(92dvh, 720px)`.
- Background `linear-gradient(135deg, rgba(200,245,63,.05), transparent 40%), #101412`, border `rgba(200,245,63,.28)` and a 78×3 acid tab.
- A 36×36 close button at the top right, with a `--line` border.
- A thin acid scrollbar (`rgba(200,245,63,.4)` on `#151a17`).
- On mobile it becomes a bottom sheet: it sticks to the bottom, with no side borders, and the bottom padding respects `env(safe-area-inset-bottom)`.

### 8.6 Accordion (FAQ, on cream)

- Dividers `#cdd0c6`. Question at 15px/800.
- A 22×22 square indicator with a `#bdc1b6` border and a sign in `#7e9b23`. On hover it rotates 90°.
- The answer unfolds by animating `grid-template-rows: 0fr → 1fr` (.25s), with no JavaScript for the height.

### 8.7 Floating panels (cookies, language notice)

- Background `rgba(12,15,14,.97)` with `backdrop-filter: blur(14–18px)`.
- Cookies: bottom right, 520px, accent border and acid tab. On mobile it takes the full width and the buttons stack with the primary on top (`column-reverse`).
- Language: bottom left, 400px, `--line` border. It only appears once the cookies have been answered.

### 8.8 Progress indicator (carousel)

18×2px bars in `#363e39`. The active one stretches to 35px and is painted `--acid` (transition .3s).

### 8.9 Brand (logo)

```html
<a class="brand"><img class="brand-mark" …/><span>Elo<span>peak</span></span></a>
```

15px (13px at ≤420), weight 900, `-.03em`. The second part of the name is in `--acid`. A 36×36 icon (30 at ≤420) with `drop-shadow(0 0 12px rgba(200,245,63,.12))`.

---

## 9. Backgrounds and textures

| Effect | Recipe |
|---|---|
| Hero background | `radial-gradient(circle at 74% 44%, rgba(71,86,49,.15), transparent 26%), linear-gradient(115deg, #090b0c 0%, #0d1112 55%, #0a0c0c 100%)` |
| Diagonal stripes | `repeating-linear-gradient(115deg, transparent 0 160px, rgba(255,255,255,.018) 161px, transparent 162px)` |
| Technical grid | 1px `rgba(255,255,255,.035)` lines every 76px, `opacity: .35`, with a horizontal mask `linear-gradient(to right, transparent 2%, #000 50%, transparent 98%)` |
| Acid halo | A 360px circle in `--acid`, `filter: blur(120px)`, `opacity: .1` |
| Inner page spotlight | `radial-gradient(circle at 65% 35%, rgba(200,245,63,.11), transparent 30%), var(--ink)` |
| Final CTA | `radial-gradient(circle at 50% 50%, #202b1b, #0b0e0d 65%)` |
| Portrait stripes | `repeating-linear-gradient(110deg, transparent 0 40px, rgba(255,255,255,.025) 41px, transparent 42px)` |
| Radar | `repeating-conic-gradient(from 0deg, rgba(255,255,255,.018) 0deg 1deg, transparent 1deg 15deg)` |

---

## 10. Motion

### 10.1 Curves and durations

| Name | Curve | Duration | Use |
|---|---|---|---|
| Snap | `cubic-bezier(.2,.75,.2,1)` | .35–.85s | Reveal, card hover, hero entrance |
| Soft out | `cubic-bezier(.22,1,.36,1)` | .34–.42s | Review change, page entrance |
| Exit | `cubic-bezier(.4,0,1,1)` | .28s | Page exit |
| Micro | `ease` | .2–.3s | Colours, borders, button hover |

### 10.2 Animations

| Animation | What it does |
|---|---|
| `[data-reveal]` → `.is-visible` | Appears rising 34px (.7s, snap) on entering the screen |
| `hero-copy-in` | Text enters from `(-28px, 18px)` in .75s |
| `hero-card-in` | Card enters from `(32px, 16px) rotate(1deg)` in .85s with a .12s delay |
| `page-out` / `page-in` | View Transitions between pages (rises 10px on leaving and 12px on entering) |
| `pulse` | Live-dot halo, a 2s loop |
| `review-swap` | Review change, rises 6px |
| Card hover | `translateY(-4px to -8px)` and more shadow |

### 10.3 Rules

- Hovers with displacement go inside `@media (hover: hover) and (pointer: fine)`, so they don't stick on touch screens.
- `prefers-reduced-motion: reduce` disables animations, transitions, smooth scroll and view transitions, and shows the `[data-reveal]` content directly.
- Animate only `transform`, `opacity`, colours and shadows. Never `width` or `height`, except the carousel's measured height.

---

## 11. Accessibility

- **Skip link** (`.skip-link`): `--acid` background, hidden at the top, appears at 16px on receiving focus.
- **`.sr-only`** for screen-reader-only text.
- **Visible focus** always: `2px solid var(--acid)` with `offset 4px` on buttons and links, and `1px` on inputs.
- Decorative icons carry `aria-hidden="true"`. Active states are marked with `aria-current` or `aria-selected`, not just with colour.
- Touch targets of at least 38px, and 46–48px on the form controls on mobile.
- Check the contrast in §2.7 before using a new grey for small text.

---

## 12. Ready-to-copy tokens

### 12.1 CSS

The current tokens plus the fixed values that repeat most, with a name of their own. The new tokens (from `--acid-hover` on) are a **proposal** and don't yet exist in `globals.css`.

```css
:root {
  /* Current */
  --ink: #080a0b;
  --ink-soft: #101315;
  --panel: #15191b;
  --panel-light: #1b2022;
  --line: rgba(255, 255, 255, 0.11);
  --text: #f4f6f1;
  --muted: #9ca39f;
  --acid: #c8f53f;
  --acid-dark: #9dbf31;
  --acid-accessible: #526814;
  --cream: #f0f0e8;
  --dark-text: #111412;

  /* Proposed */
  --acid-hover: #d5ff55;
  --acid-link: #8ea92f;
  --acid-border: rgba(200, 245, 63, 0.22);
  --acid-border-strong: rgba(200, 245, 63, 0.48);
  --acid-glow: rgba(200, 245, 63, 0.18);
  --subtle: #7f8781;
  --field-bg: #0c0f0e;
  --field-border: #2c3430;
  --cream-card: #f7f7f1;
  --cream-line: #d1d3ca;
  --danger: #ffb4b4;

  --font-sans: var(--font-geist-sans), Arial, Helvetica, sans-serif;
  --font-mono: var(--font-geist-mono), monospace;
  --font-serif: Georgia, serif;

  --ease-snap: cubic-bezier(.2, .75, .2, 1);
  --ease-out: cubic-bezier(.22, 1, .36, 1);

  --shadow-glow: 0 12px 34px rgba(200, 245, 63, 0.18);
  --shadow-float: 0 30px 80px rgba(0, 0, 0, 0.45);
  --shadow-popover: 0 24px 75px rgba(0, 0, 0, 0.52);

  --header-h: 76px;       /* 65px at ≤640 */
  --shell-max: 1180px;
}
```

### 12.2 Tailwind v4

The project already loads Tailwind v4 (`@import "tailwindcss"`) although almost everything is written in custom CSS. If you want to use utilities with Elopeak's palette, add this below the import:

```css
@theme inline {
  --color-ink: var(--ink);
  --color-panel: var(--panel);
  --color-line: var(--line);
  --color-text: var(--text);
  --color-muted: var(--muted);
  --color-acid: var(--acid);
  --color-acid-accessible: var(--acid-accessible);
  --color-cream: var(--cream);
  --color-dark-text: var(--dark-text);

  --font-sans: var(--font-geist-sans), Arial, Helvetica, sans-serif;
  --font-mono: var(--font-geist-mono), monospace;

  --radius-*: initial;      /* no radii: everything square */
  --radius-full: 9999px;

  --breakpoint-sm: 420px;
  --breakpoint-md: 640px;
  --breakpoint-lg: 900px;
}
```

That way you can write `bg-ink text-acid border-line font-mono` and the rest of the utilities.

---

## 13. Checklist for a new screen

- [ ] Background `--ink` or `--cream`, alternating dark and light between sections.
- [ ] A single accent colour. Acid green isn't mixed with other accents (except the map colours).
- [ ] On cream, the green is `--acid-accessible`.
- [ ] Headline at weight 950 with negative letter-spacing and the accent line in green.
- [ ] Section caption in uppercase, 13px, `.19em`.
- [ ] Square uppercase buttons, with `ArrowIcon`, and at most one primary per block.
- [ ] Featured cards with an acid tab.
- [ ] No `border-radius` except circles.
- [ ] Hover with displacement only inside `(hover: hover) and (pointer: fine)`.
- [ ] Tested at 900, 640 and 420px, and with `prefers-reduced-motion`.
- [ ] Contrast checked (§2.7) and visible focus.
- [ ] "Elopeak" with a capital E in visible text.
