# oura-health-sync

Daily Oura Ring scores for Louise-OS. Runs **once a day on GitHub's servers** —
your Mac doesn't need to be on.

## What this is (and isn't)
- Public repo, on purpose: `ouraDaily.json` is fetched directly by Louise-OS.html
  in your browser (`fetch()` from `raw.githubusercontent.com`), which only works
  without a login token if the file is publicly readable.
- Contains **only**: date, sleep/readiness/activity scores, HRV, heart rate,
  temperature deviation, steps, calories, workouts. No name, no account ID,
  no login details, nothing that identifies the Oura account behind it.
- All real secrets (access token, refresh token, client ID/secret) live as
  **encrypted GitHub Actions repo secrets** (Settings → Secrets and variables →
  Actions) — never in a file in this repo.

## How it works
1. `.github/workflows/sync.yml` runs daily (08:00 UTC) and on-demand
   (Actions tab → "Oura daily sync" → Run workflow).
2. `sync_oura.py` calls the Oura API using the `OURA_ACCESS_TOKEN` secret,
   pulls the last 7 days (so a missed run doesn't lose a day), and
   upserts them into `ouraDaily.json` by date.
3. The workflow commits the updated file if anything changed.
4. Louise-OS.html pulls this file in automatically on load, and via the
   "🔄 Refresh Oura data" button on the Health page. It merges by date —
   never touches your manually-logged health entries.

## Maintenance
The Oura access token is valid ~30 days. When it expires, the daily
run starts failing (visible as a red ✗ on the Actions tab). Ask Claude to
get a fresh one (a 2-minute re-authorisation, same as the original setup),
then update the `OURA_ACCESS_TOKEN` secret with the new value here.

## How to check it's healthy
GitHub → this repo → **Actions** tab → "Oura daily sync". A green tick
means it ran and (if there was new data) committed it.
