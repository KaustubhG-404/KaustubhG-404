
import os
import json
import html
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

USERNAME = "KaustubhG-404"
TOKEN = os.environ.get("GITHUB_TOKEN")

if not TOKEN:
    raise RuntimeError("GITHUB_TOKEN is not configured.")

today = datetime.now(timezone.utc).date()
start = today - timedelta(days=364)

query = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            date
            contributionCount
          }
        }
      }
    }
  }
}
"""

payload = {
    "query": query,
    "variables": {
        "login": USERNAME,
        "from": f"{start.isoformat()}T00:00:00Z",
        "to": f"{today.isoformat()}T23:59:59Z"
    }
}

request = urllib.request.Request(
    "https://api.github.com/graphql",
    data=json.dumps(payload).encode("utf-8"),
    headers={
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
        "User-Agent": "GitHub-Profile-Dashboard"
    }
)

with urllib.request.urlopen(request, timeout=30) as response:
    result = json.loads(response.read().decode("utf-8"))

if result.get("errors"):
    raise RuntimeError(
        "GitHub GraphQL error: " + json.dumps(result["errors"])
    )

user = result.get("data", {}).get("user")
if not user:
    raise RuntimeError("GitHub user not found: " + USERNAME)

calendar = user["contributionsCollection"]["contributionCalendar"]
days = {}

for week in calendar["weeks"]:
    for item in week["contributionDays"]:
        date = datetime.strptime(item["date"], "%Y-%m-%d").date()
        days[date] = int(item["contributionCount"])

if not days:
    raise RuntimeError("GitHub returned an empty contribution calendar.")

# Current streak: today, or yesterday if today has no contribution yet.
current_end = today if days.get(today, 0) > 0 else today - timedelta(days=1)
current_streak = 0
cursor = current_end

while days.get(cursor, 0) > 0:
    current_streak += 1
    cursor -= timedelta(days=1)

# Longest consecutive streak in the returned calendar.
longest_streak = 0
run = 0

for date in sorted(days):
    if days[date] > 0:
        run += 1
        longest_streak = max(longest_streak, run)
    else:
        run = 0

total = int(calendar["totalContributions"])

# Build the SVG dashboard.
first_day = min(days)
last_day = max(days)
first_monday = first_day - timedelta(days=first_day.weekday())
week_count = ((last_day - first_monday).days // 7) + 1

cell = 11
gap = 3
step = cell + gap
left = 42
top = 128
width = max(900, left + week_count * step + 35)
height = 222

def esc(value):
    return html.escape(str(value), quote=True)

parts = [
    f'<svg xmlns="http://www.w3.org/2000/svg" '
    f'width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
    '<rect width="100%" height="100%" rx="12" fill="#0d1117"/>',
    '<text x="24" y="30" fill="#58a6ff" font-size="19" '
    'font-family="Arial,sans-serif" font-weight="bold">'
    'GitHub Contribution Dashboard</text>',
    f'<text x="24" y="51" fill="#8b949e" font-size="11" '
    f'font-family="Arial,sans-serif">{esc(USERNAME)} · Last 365 days</text>'
]

metrics = [
    ("TOTAL CONTRIBUTIONS", total),
    ("CURRENT STREAK", current_streak),
    ("LONGEST STREAK", longest_streak)
]

for (label, value), x in zip(metrics, [24, 310, 596]):
    parts.append(
        f'<text x="{x}" y="79" fill="#8b949e" font-size="10" '
        f'font-family="Arial,sans-serif">{label}</text>'
    )
    parts.append(
        f'<text x="{x}" y="106" fill="#3fb950" font-size="22" '
        f'font-weight="bold" font-family="Arial,sans-serif">{value}</text>'
    )

parts.append(
    '<text x="24" y="119" fill="#8b949e" font-size="9" '
    'font-family="Arial,sans-serif">Contribution calendar</text>'
)

# Month labels
seen_months = set()

for date in sorted(days):
    if date.day == 1:
        week_index = (date - first_monday).days // 7
        x = left + week_index * step
        label = date.strftime("%b")
        if label not in seen_months:
            parts.append(
                f'<text x="{x}" y="{top - 9}" fill="#8b949e" '
                f'font-size="10" font-family="Arial,sans-serif">'
                f'{label}</text>'
            )
            seen_months.add(label)

def contribution_color(count):
    if count == 0:
        return "#161b22"
    if count <= 2:
        return "#0e4429"
    if count <= 5:
        return "#006d32"
    if count <= 9:
        return "#26a641"
    return "#39d353"

for date, count in days.items():
    week_index = (date - first_monday).days // 7
    weekday = date.weekday()  # Monday = 0
    x = left + week_index * step
    y = top + weekday * step

    parts.append(
        f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" '
        f'rx="2" fill="{contribution_color(count)}">'
        f'<title>{date.isoformat()}: {count} contributions</title>'
        f'</rect>'
    )

parts.append(
    f'<text x="24" y="{height - 10}" fill="#8b949e" font-size="10" '
    f'font-family="Arial,sans-serif">Updated {today.isoformat()} · '
    f'Streaks count consecutive days with contributions.</text>'
)
parts.append("</svg>")

output = Path("profile/contributions.svg")
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text("\n".join(parts), encoding="utf-8")

print(f"Generated {output}")
print(f"Total contributions: {total}")
print(f"Current streak: {current_streak}")
print(f"Longest streak: {longest_streak}")
