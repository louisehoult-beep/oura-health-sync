"""Daily Oura Ring sync for Louise-OS.

Fetches the last 7 days of sleep/readiness/activity data from the Oura API
and upserts them (by date) into ouraDaily.json in this repo. Louise-OS.html
fetches that file directly (public raw URL) and merges it into its own data,
additively — this script never touches anything on Lou's machine.

Auth: uses OURA_ACCESS_TOKEN (a bearer token, valid ~30 days from issue).
This script does NOT refresh the token — when it expires, this job will
start failing (visible as a red X on the Actions tab), and a fresh token
needs to be obtained via the Oura OAuth flow and the OURA_ACCESS_TOKEN
secret updated by hand. OURA_CLIENT_ID / OURA_CLIENT_SECRET / OURA_REFRESH_TOKEN
are also stored as repo secrets for that purpose, but are not used by this
script — kept simple deliberately rather than having the job self-mutate
its own secrets.

Standard library only — no pip install needed.
"""
import json
import os
import sys
import datetime
import urllib.request
import urllib.parse
import urllib.error

TOKEN = os.environ.get("OURA_ACCESS_TOKEN")
DAYS_BACK = 7
OUT_FILE = "ouraDaily.json"


def get(ep, start, end):
    params = urllib.parse.urlencode({"start_date": start, "end_date": end})
    url = f"https://api.ouraring.com/v2/usercollection/{ep}?{params}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {TOKEN}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["data"]


def main():
    if not TOKEN:
        print("OURA_ACCESS_TOKEN not set — nothing to do.", file=sys.stderr)
        sys.exit(1)

    end = datetime.date.today().isoformat()
    start = (datetime.date.today() - datetime.timedelta(days=DAYS_BACK)).isoformat()

    try:
        daily_sleep = {d["day"]: d for d in get("daily_sleep", start, end)}
        daily_activity = {d["day"]: d for d in get("daily_activity", start, end)}
        daily_readiness = {d["day"]: d for d in get("daily_readiness", start, end)}
        sleep_periods = get("sleep", start, end)
        workouts = get("workout", start, end)
    except urllib.error.HTTPError as e:
        print(f"Oura API error {e.code}: {e.read().decode('utf-8', 'replace')}", file=sys.stderr)
        if e.code == 401:
            print("Access token has expired — needs a fresh OURA_ACCESS_TOKEN secret.", file=sys.stderr)
        sys.exit(1)

    sleep_by_day = {}
    for s in sleep_periods:
        day = s["day"]
        if day not in sleep_by_day or s.get("total_sleep_duration", 0) > sleep_by_day[day].get("total_sleep_duration", 0):
            sleep_by_day[day] = s

    workouts_by_day = {}
    for w in workouts:
        workouts_by_day.setdefault(w.get("day"), []).append(w)

    fresh_days = sorted(set(daily_sleep) | set(daily_activity) | set(daily_readiness) | set(sleep_by_day))

    fresh = {}
    for day in fresh_days:
        ds = daily_sleep.get(day, {})
        da = daily_activity.get(day, {})
        dr = daily_readiness.get(day, {})
        sp = sleep_by_day.get(day, {})
        entry = {
            "date": day,
            "sleepScore": ds.get("score"),
            "readinessScore": dr.get("score"),
            "activityScore": da.get("score"),
            "totalSleepHrs": round(sp["total_sleep_duration"] / 3600, 1) if sp.get("total_sleep_duration") else None,
            "timeInBedHrs": round(sp["time_in_bed"] / 3600, 1) if sp.get("time_in_bed") else None,
            "sleepEfficiency": sp.get("efficiency"),
            "avgHRV": sp.get("average_hrv"),
            "avgHeartRate": sp.get("average_heart_rate"),
            "lowestHeartRate": sp.get("lowest_heart_rate"),
            "temperatureDeviation": dr.get("temperature_deviation"),
            "steps": da.get("steps"),
            "activeCalories": da.get("active_calories"),
            "totalCalories": da.get("total_calories"),
            "workouts": [
                {
                    "activity": w.get("activity"),
                    "durationMins": round((w.get("duration") or 0) / 60, 1) if w.get("duration") else None,
                    "calories": w.get("calories"),
                }
                for w in workouts_by_day.get(day, [])
            ],
            "source": "oura_api",
        }
        entry = {k: v for k, v in entry.items() if v is not None and v != []}
        fresh[day] = entry

    existing = []
    if os.path.exists(OUT_FILE):
        try:
            with open(OUT_FILE) as f:
                existing = json.load(f)
        except (json.JSONDecodeError, OSError):
            existing = []

    by_date = {e["date"]: e for e in existing if isinstance(e, dict) and e.get("date")}
    by_date.update(fresh)  # fresh pulls always win for the days they cover

    merged = [by_date[d] for d in sorted(by_date)]

    with open(OUT_FILE, "w") as f:
        json.dump(merged, f, indent=2)
        f.write("\n")

    print(f"Synced {len(fresh)} day(s) ({start} to {end}); {len(merged)} total days in {OUT_FILE}.")


if __name__ == "__main__":
    main()
