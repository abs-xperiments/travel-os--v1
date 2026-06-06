# Setting up "Continue with Google" (one-time, ~10 minutes)

The code is already live — the Google button appears on /login automatically the moment
`GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` exist in the environment. This guide is the
one part only you can do: creating those credentials in Google Cloud.

## Steps

1. **Open** https://console.cloud.google.com/ and sign in with your Google account.
2. **Create a project** (top bar → project picker → "New project"). Name: `TripOS`. Create.
3. **Configure the consent screen** — left menu → "APIs & Services" → "OAuth consent screen":
   - User type: **External** → Create.
   - App name: `TripOS`; support email: your email; developer contact: your email. Save.
   - Scopes: add **`openid`**, **`email`**, **`profile`** (the non-sensitive defaults). Save.
   - Test users: add your own Gmail address (while the app is in "Testing" mode, only listed
     users can sign in — fine for now; "Publish" later when you want anyone to use it).
4. **Create the OAuth client** — "APIs & Services" → "Credentials" → "+ Create credentials"
   → "OAuth client ID":
   - Application type: **Web application**. Name: `TripOS web`.
   - **Authorized redirect URIs** — add BOTH, exactly (no trailing slash):
     - `http://localhost:8000/auth/google/callback`
     - `https://tripos-web-production-4f1c.up.railway.app/auth/google/callback`
   - Create → copy the **Client ID** and **Client secret**.
5. **Local:** add to `.env`:
   ```
   GOOGLE_CLIENT_ID=...apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=...
   ```
6. **Production:** set the same two as Railway variables (`railway variables --set ...`),
   then redeploy. The button appears; nothing else changes.

## How the flow works (for the curious)

/auth/google sends you to Google with a random `state` (CSRF guard, kept in a 10-minute
cookie). Google sends you back to /auth/google/callback with a code; the server exchanges
it for an access token and asks Google's userinfo endpoint who you are (server-to-server —
no token decoding tricks). Only a **verified** Google email is accepted, and it maps to the
same single TripOS account as a magic-link sign-in for that address — never a duplicate.

## Troubleshooting

- **"redirect_uri_mismatch"** — the URI in Google Console must match
  `{APP_BASE_URL}/auth/google/callback` byte-for-byte (scheme, host, no trailing slash).
- **"access_blocked: app not verified"** — you're not in the Test users list, or publish
  the consent screen.
- Button not showing — one of the two env vars is missing where the app runs.
