"""Build the Slack payload for a production release notification.

Reads everything from the environment (set by action.yml) and writes a
Block Kit payload as JSON to the path given in PAYLOAD_PATH. The changelog
body is the lines release-please added to CHANGELOG.md between the previous
production tip and this one, converted from Markdown to Slack mrkdwn.
"""

from __future__ import annotations

import json
import os
import re

# Slack caps a section's text at 3000 characters; leave room for the footer.
BODY_LIMIT = 2800

LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
RELEASE_HEADING = re.compile(r"^##\s+\[(?P<version>[^\]]+)\]\([^)]*\)(?:\s+\((?P<date>[^)]+)\))?")
SECTION_HEADING = re.compile(r"^###\s+(.+)")
BULLET = re.compile(r"^\*\s+(.*)")
# release-please appends "([<sha>](<commit url>))" to every entry; the PR
# link right before it is the one people click, so the sha link is dropped
# and the sha itself names the entry's author (action.yml resolves it).
COMMIT_LINK = re.compile(r"\s*\(\[[0-9a-f]{7,40}\]\(https?://[^)]+/commit/(?P<sha>[0-9a-f]{7,40})\)\)")
BOLD = re.compile(r"\*\*([^*]+)\*\*")

Authors = dict[str, dict[str, str]]


def escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def author_label(author: dict[str, str], server: str) -> str:
    """The commit author's name, linked to their GitHub profile when the email resolved to one."""
    login = author.get("login", "")
    name = escape(author.get("name", "") or login)
    if not name:
        return ""
    return f"<{server}/{login}|{name}>" if login else name


def inline(text: str, authors: Authors, server: str) -> str:
    commit = COMMIT_LINK.search(text)
    text = COMMIT_LINK.sub("", text)
    text = escape(text)
    text = LINK.sub(lambda m: f"<{m.group(2)}|{m.group(1)}>", text)
    text = BOLD.sub(r"*\1*", text)
    label = author_label(authors.get(commit.group("sha"), {}), server) if commit else ""
    return f"{text}  ·  {label}" if label else text


def to_mrkdwn(markdown: str, authors: Authors, server: str) -> str:
    lines: list[str] = []
    for raw in markdown.splitlines():
        line = raw.rstrip()
        if not line or line.startswith("# "):
            continue
        heading = RELEASE_HEADING.match(line)
        if heading:
            version = heading.group("version")
            label = version if version.startswith("v") else f"v{version}"
            date = heading.group("date")
            if lines:
                lines.append("")
            lines.append(f"*{label}*" + (f"  ·  {date}" if date else ""))
            continue
        section = SECTION_HEADING.match(line)
        if section:
            lines.append(f"_{section.group(1).strip()}_")
            continue
        bullet = BULLET.match(line)
        if bullet:
            lines.append(f"•  {inline(bullet.group(1), authors, server)}")
            continue
        lines.append(inline(line, authors, server))
    return "\n".join(lines)


def truncate(body: str, limit: int) -> str:
    if len(body) <= limit:
        return body
    cut = body.rfind("\n", 0, limit)
    return body[: cut if cut > 0 else limit] + "\n_…truncated, full notes in the compare link below_"


def main() -> None:
    env = os.environ
    repo = env["REPO"]
    server = env["SERVER_URL"]
    mode = env["MODE"]
    status = env["STATUS"]
    environment = env["ENVIRONMENT"]
    old_version = env.get("OLD_VERSION", "")
    new_version = env.get("NEW_VERSION", "")
    image_tag = env.get("IMAGE_TAG", "")
    headline = env.get("HEADLINE", "")
    commit_subject = env.get("COMMIT_SUBJECT", "")
    sha = env.get("SHA", "")
    run_url = env["RUN_URL"]
    changelog = env.get("CHANGELOG", "")
    authors: Authors = {}
    authors_path = env.get("AUTHORS_PATH", "")
    if authors_path and os.path.exists(authors_path):
        with open(authors_path, encoding="utf-8") as fh:
            authors = json.load(fh)

    name = repo.split("/", 1)[1]
    repo_url = f"{server}/{repo}"
    links = [f"<{run_url}|Run>"]
    body = ""

    if status != "success":
        what = f"image `{image_tag}`" if mode == "image" else f"v{new_version}"
        outcome = "was cancelled" if status == "cancelled" else "failed"
        title = f":x: *{name}* {environment} deploy of {what} {outcome}"
    elif mode == "image":
        title = f":arrows_counterclockwise: *{name}* {environment} deployed image `{image_tag}`"
    elif old_version and old_version != new_version:
        verb = headline or f"is live in {environment}"
        title = f":rocket: *{name}* v{old_version} → v{new_version} {verb}"
        body = truncate(to_mrkdwn(changelog, authors, server), BODY_LIMIT)
        links.insert(0, f"<{repo_url}/compare/v{old_version}...v{new_version}|Full diff>")
    else:
        # Same version on both sides is a hotfix merged without a release cut.
        # An empty old version means HEAD^1 was not fetched, so nothing is
        # claimed about what changed beyond the commit itself.
        verb = headline or f"redeployed to {environment}"
        suffix = " (no release cut)" if old_version else ""
        title = f":rocket: *{name}* v{new_version} {verb}{suffix}"
        if commit_subject:
            body = f"`{escape(commit_subject)}`"
        if sha:
            links.insert(0, f"<{repo_url}/commit/{sha}|Commit>")

    blocks: list[dict[str, object]] = [{"type": "section", "text": {"type": "mrkdwn", "text": title}}]
    if body:
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": body}})
    blocks.append(
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": "  ·  ".join(links)}],
        }
    )

    payload = {"text": re.sub(r"[*`]", "", title), "blocks": blocks}
    with open(env["PAYLOAD_PATH"], "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
