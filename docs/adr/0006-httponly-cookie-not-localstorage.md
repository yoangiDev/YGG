# 0006 · In-memory access token and an httpOnly-cookie refresh token

**Status:** accepted · **Phases:** 3 and 5 · **Resolves:** P5

## Context

The API issued a single 30-minute JWT with `python-jose` (unmaintained), with no refresh or revocation. In Flutter Web the
token lived in `shared_preferences`, which in the browser is `localStorage`: any XSS could read it and use it from another
machine. There was also no limit on login attempts.

## Decision

- **Access token**: a 15-minute JWT (PyJWT) that the client keeps **only in memory** and sends in
  `Authorization: Bearer`.
- **Opaque refresh token** in an `httpOnly; Secure; SameSite=Lax; Path=/auth` cookie. Its SHA-256 hash is stored in the
  database, it is **rotated on every use** and, if one that was already used is presented, the **whole family is
  revoked** (a sign of theft).
- Passwords with bcrypt, a policy of 10 characters up to 72 bytes, and a comparison against a dummy hash when the email
  doesn't exist, so as not to reveal which accounts exist through response time.
- Redis rate limiting for login (per IP and per email), sign-up and refresh.
- On the web side, the generated client intercepts the 401s, asks for a refresh and repeats the request. Concurrent
  refreshes **share a single request**: two rotations in parallel would look like reuse and close the session.

## Alternatives

- **JWT in `localStorage`.** The simplest and what there was: exposed to any XSS.
- **Cookie-only session**, with no `Authorization` header. Every cookie-bearing request would need CSRF protection. With
  the cookie limited to `/auth`, the rest of the API isn't authenticated by cookie and the CSRF surface shrinks to
  refresh and logout, whose response another origin can't read thanks to CORS.
- **BFF** (an intermediate server that stores the tokens). Safer still, but it adds a service.

## Consequences

- An XSS can use the session while the tab is open, but can't carry off a long-lived token.
- Reloading the page costs one refresh request; the session survives (tested in `e2e/real-api.spec.ts` against the real
  API).
- **The web app and the API must share a *site*** (the same registrable domain) for the `SameSite=Lax` cookie to travel: in
  production, `ygg.yourdomain.dev` and `api.ygg.yourdomain.dev` (see [`deploy.md`](../deploy.md)).
- CORS with credentials requires explicit origins; never `*`.
