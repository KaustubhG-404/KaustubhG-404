
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
# Build a cleaner, responsive SVG dashboard.
first_day = min(days)
last_day = max(days)
first_monday = first_day - timedelta(days=first_day.weekday())
week_count = ((last_day - first_monday).days // 7) + 1

cell = 12
gap = 4
step = cell + gap
left = 42
top = 145
calendar_height = 7 * step - gap
width = max(900, left + week_count * step + 28)
height = top + calendar_height + 42

def esc(value):
    return html.escape(str(value), quote=True)

parts = [
    f'<svg xmlns="http://www.w3.org/2000/svg" '
    f'width="100%" height="auto" viewBox="0 0 {width} {height}" '
    f'role="img" aria-label="GitHub contribution dashboard">',
    '<rect width="100%" height="100%" rx="14" fill="#0d1117"/>',
    '<text x="24" y="32" fill="#58a6ff" font-size="21" '
    'font-family="Arial,sans-serif" font-weight="bold">'
    'GitHub Contribution Dashboard</text>',
    f'<text x="24" y="53" fill="#8b949e" font-size="12" '
    f'font-family="Arial,sans-serif">{esc(USERNAME)} · Last 365 days</text>'
]

metrics = [
    ("TOTAL CONTRIBUTIONS", total),
    ("CURRENT STREAK", current_streak),
    ("LONGEST STREAK", longest_streak)
]

metric_x = [24, width // 3, (width * 2) // 3]

for (label, value), x in zip(metrics, metric_x):
    parts.append(
        f'<text x="{x}" y="82" fill="#8b949e" font-size="10" '
        f'font-family="Arial,sans-serif">{label}</text>'
    )
    parts.append(
        f'<text x="{x}" y="111" fill="#3fb950" font-size="25" '
        f'font-weight="bold" font-family="Arial,sans-serif">'
        f'{value}</text>'
    )

parts.append(
    f'<text x="24" y="133" fill="#c9d1d9" font-size="11" '
    f'font-family="Arial,sans-serif">Contribution activity</text>'
)

# Month labels: show each month once, with enough room above the grid.
last_month = None

for date in sorted(days):
    month_key = (date.year, date.month)
    if month_key != last_month and date.weekday() == 0:
        week_index = (date - first_monday).days // 7
        x = left + week_index * step
        parts.append(
            f'<text x="{x}" y="{top - 9}" fill="#8b949e" '
            f'font-size="10" font-family="Arial,sans-serif">'
            f'{date.strftime("%b")}</text>'
        )
        last_month = month_key

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

# Draw all days in chronological order.
for date in sorted(days):
    count = days[date]
    week_index = (date - first_monday).days // 7
    weekday = date.weekday()
    x = left + week_index * step
    y = top + weekday * step

    parts.append(
        f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" '
        f'rx="3" fill="{contribution_color(count)}">'
        f'<title>{date.isoformat()}: {count} contributions</title>'
        f'</rect>'
    )

footer_y = height - 13
parts.append(
    f'<text x="24" y="{footer_y}" fill="#8b949e" font-size="10" '
    f'font-family="Arial,sans-serif">'
    f'Updated {today.isoformat()} · Each square represents one day'
    f'</text>'
)
parts.append("</svg>")

output = Path("profile/contributions.svg")
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text("\n".join(parts), encoding="utf-8")

print(f"Generated {output}")
print(f"Total contributions: {total}")
print(f"Current streak: {current_streak}")
print(f"Longest streak: {longest_streak}")
