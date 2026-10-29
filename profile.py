"""Renders dark_mode.svg and light_mode.svg for the GitHub profile README.

Usage:
  python profile.py                    # render SVGs (fetches GitHub stats if GH_TOKEN is set)
  python profile.py --photo me.jpg     # convert a photo to ascii.txt first (needs Pillow)

Locally: GH_TOKEN=$(gh auth token) python profile.py
"""

import json
import os
import sys
import urllib.request
from datetime import date, timedelta
from html import escape
from pathlib import Path

ROOT = Path(__file__).parent
LOGIN = "ChristianOlsen"
HEADER = "christian@olsen"

UPTIME_SINCE = date(1998, 9, 7)

# Each entry: (key, value) | None for a blank line | ("-", section title)
# Keys with dots ("Languages.Real") are coloured per segment, like neofetch.
INFO = [
    ("OS", "macOS, Linux"),
    ("Uptime", "{uptime}"),
    ("Host", "OBOS"),
    ("Kernel", "Fullstack Developer"),
    ("IDE", "JetBrains"),
    ("Cloud", "Azure"),
    ("Region", "EU North, Oslo"),
    None,
    ("Languages.Programming.Backend", "C#, Python, Kotlin"),
    ("Languages.Programming.Frontend", "TypeScript"),
    ("Languages.Programming.Infrastructure", "Terraform, Bicep"),
    ("Languages.Natural", "Norwegian, English"),
    ("-", "Contact"),
    ("GitHub", LOGIN),
    ("LinkedIn", "chrolsn"),
    ("Email.Personal", "christian.olsen.dev@gmail.com"),
    ("Email.Work", "christian.olsen@obos.no"),
    ("-", "GitHub Stats"),
    (("Repos", "{repos} {{Contributed: {contributed}}}"), ("Stars", "{stars}")),
    (("Commits", "{commits}"), ("Followers", "{followers}")),
]

WIDTH = 60  # characters per info line, after the leading ". "
CHAR_W = 9.6  # px per character at 16px Consolas
LINE_H = 20

THEMES = {
    "dark": {"bg": "#161b22", "text": "#c9d1d9", "key": "#ffa657", "value": "#a5d6ff", "cc": "#616e7f"},
    "light": {"bg": "#f6f8fa", "text": "#24292f", "key": "#953800", "value": "#0a3069", "cc": "#c2cfde"},
}

RAMP = " .:-=+*#%@"


def photo_to_ascii(path, cols=40, rows=25):
    from PIL import Image, ImageOps

    img = ImageOps.grayscale(Image.open(path))
    img = ImageOps.autocontrast(img).resize((cols, rows))
    px = list(img.getdata())
    lines = []
    for r in range(rows):
        row = px[r * cols:(r + 1) * cols]
        lines.append("".join(RAMP[p * (len(RAMP) - 1) // 255] for p in row).rstrip())
    (ROOT / "ascii.txt").write_text("\n".join(lines) + "\n")


def uptime():
    if UPTIME_SINCE is None:
        return "TODO: set UPTIME_SINCE"
    today = date.today()
    years = today.year - UPTIME_SINCE.year
    months = today.month - UPTIME_SINCE.month
    days = today.day - UPTIME_SINCE.day
    if days < 0:
        months -= 1
        days += (today.replace(day=1) - timedelta(days=1)).day  # length of previous month
    if months < 0:
        years -= 1
        months += 12
    plural = lambda n, w: f"{n} {w}{'' if n == 1 else 's'}"
    return f"{plural(years, 'year')}, {plural(months, 'month')}, {plural(days, 'day')}"


def graphql(token, query, variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as res:
        body = json.load(res)
    if "errors" in body:
        raise RuntimeError(body["errors"])
    return body["data"]


def fetch_stats(token):
    user = graphql(token, """
        query($login: String!) {
          user(login: $login) {
            followers { totalCount }
            repositoriesContributedTo(contributionTypes: [COMMIT, PULL_REQUEST, REPOSITORY]) { totalCount }
            contributionsCollection { contributionYears }
          }
        }""", {"login": LOGIN})["user"]

    stars, repos, cursor = 0, 0, None
    while True:
        page = graphql(token, """
            query($login: String!, $cursor: String) {
              user(login: $login) {
                repositories(ownerAffiliations: OWNER, first: 100, after: $cursor) {
                  totalCount
                  nodes { stargazerCount }
                  pageInfo { hasNextPage endCursor }
                }
              }
            }""", {"login": LOGIN, "cursor": cursor})["user"]["repositories"]
        repos = page["totalCount"]
        stars += sum(n["stargazerCount"] for n in page["nodes"])
        if not page["pageInfo"]["hasNextPage"]:
            break
        cursor = page["pageInfo"]["endCursor"]

    commits = 0
    for year in user["contributionsCollection"]["contributionYears"]:
        c = graphql(token, """
            query($login: String!, $from: DateTime!, $to: DateTime!) {
              user(login: $login) {
                contributionsCollection(from: $from, to: $to) {
                  totalCommitContributions
                  restrictedContributionsCount
                }
              }
            }""", {"login": LOGIN, "from": f"{year}-01-01T00:00:00Z", "to": f"{year}-12-31T23:59:59Z"})
        commits += c["user"]["contributionsCollection"]["totalCommitContributions"]

    return {
        "repos": f"{repos:,}",
        "contributed": f"{user['repositoriesContributedTo']['totalCount']:,}",
        "stars": f"{stars:,}",
        "commits": f"{commits:,}",
        "followers": f"{user['followers']['totalCount']:,}",
    }


def key_spans(key):
    parts = key.split(".")
    return ".".join(f'<tspan class="key">{escape(p)}</tspan>' for p in parts)


def field(key, value, width):
    """key: ....... value, padded with dots to exactly `width` characters."""
    dots = max(1, width - len(key) - len(value) - 3)
    return f'{key_spans(key)}:<tspan class="cc"> {"." * dots} </tspan><tspan class="value">{escape(value)}</tspan>'


def render(theme, ascii_lines, values):
    t = THEMES[theme]
    ascii_w = max((len(l) for l in ascii_lines), default=0)
    x_info = round(15 + (ascii_w + 3) * CHAR_W)

    info_rows = []
    for entry in INFO:
        if entry is None:
            info_rows.append('<tspan class="cc">. </tspan>')
        elif entry[0] == "-":
            info_rows.append("")  # empty line above each section, like neofetch
            title = f"- {entry[1]} "
            info_rows.append(f'{escape(title)}<tspan class="cc">{"-" * (WIDTH + 2 - len(title))}</tspan>')
        elif isinstance(entry[0], tuple):
            half = 33  # left stat carries the longer value ("14 {Contributed: 19}")
            (k1, v1), (k2, v2) = entry
            left = field(k1, v1.format(**values), half)
            right = field(k2, v2.format(**values), WIDTH - 3 - half)
            info_rows.append(f'<tspan class="cc">. </tspan>{left} | {right}')
        else:
            k, v = entry
            info_rows.append(f'<tspan class="cc">. </tspan>{field(k, v.format(**values), WIDTH)}')

    header = f'{escape(HEADER)} <tspan class="cc">{"-" * (WIDTH + 1 - len(HEADER))}</tspan>'
    info_rows.insert(0, header)

    rows = max(len(ascii_lines), len(info_rows))
    height = 30 + rows * LINE_H
    width = round(x_info + (WIDTH + 2) * CHAR_W + 15)

    def y(i):
        return 30 + i * LINE_H

    top = (rows - len(ascii_lines)) // 2  # centre the portrait vertically
    ascii_svg = "\n".join(f'<tspan x="15" y="{y(top + i)}">{escape(l)}</tspan>' for i, l in enumerate(ascii_lines))
    info_svg = "\n".join(f'<tspan x="{x_info}" y="{y(i)}">{r}</tspan>' for i, r in enumerate(info_rows))

    return f"""<?xml version='1.0' encoding='UTF-8'?>
<svg xmlns="http://www.w3.org/2000/svg" font-family="ConsolasFallback,Consolas,monospace" width="{width}px" height="{height}px" font-size="16px">
<style>
@font-face {{
src: local('Consolas'), local('Consolas Bold');
font-family: 'ConsolasFallback';
font-display: swap;
-webkit-size-adjust: 109%;
size-adjust: 109%;
}}
.key {{fill: {t['key']};}}
.value {{fill: {t['value']};}}
.cc {{fill: {t['cc']};}}
text, tspan {{white-space: pre;}}
</style>
<rect width="{width}px" height="{height}px" fill="{t['bg']}" rx="15"/>
<text fill="{t['text']}">
{ascii_svg}
</text>
<text fill="{t['text']}">
{info_svg}
</text>
</svg>
"""


def main():
    if "--photo" in sys.argv:
        photo_to_ascii(sys.argv[sys.argv.index("--photo") + 1])

    ascii_lines = (ROOT / "ascii.txt").read_text().rstrip("\n").split("\n")
    token = os.environ.get("GH_TOKEN")
    stats = fetch_stats(token) if token else dict.fromkeys(["repos", "contributed", "stars", "commits", "followers"], "?")
    values = {"uptime": uptime(), **stats}

    for theme in THEMES:
        (ROOT / f"{theme}_mode.svg").write_text(render(theme, ascii_lines, values))
    print("Rendered dark_mode.svg and light_mode.svg", stats)


if __name__ == "__main__":
    main()
