"""Compare issues per team member between two sprint log files.

For each team member reports:
  (a) Issues that are NEW in Sprint 3 (not present in Sprint 2)
  (b) Issues present in both sprints whose status changed (e.g. OPEN -> CLOSED)
  (c) Issues that were OPEN in Sprint 2 and are still OPEN in Sprint 3
"""

import re
import sys
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class IssueEntry:
    state: str          # "OPEN" or "CLOSED"
    milestone: str      # e.g. "Sprint 2", or "" if blank
    number: int
    title: str
    url: str

    def format(self) -> str:
        milestone_part = f"({self.milestone}) " if self.milestone else "() "
        return (
            f"{self.state} ({self.milestone}) #{self.number} {self.title} {self.url}"
        )


# Matches issue lines like:
#   \t\tOPEN (Sprint 3) #122 US: Controls Instructions https://github.com/.../issues/122
_ISSUE_RE = re.compile(
    r"^\t\t(OPEN|CLOSED)\s+\(([^)]*)\)\s+#(\d+)\s+(.*?)\s+(https://\S+)\s*$"
)

# Matches user header lines like:
#   jeb6965 (Jordan Boykin) - 12 commits, 4 PRs, 12 issues assigned
_USER_RE = re.compile(r"^(\S+)\s+\(([^)]+)\)\s+-\s+\d+ commits")

# Matches repo separator lines like:
#   UNCW-CSC-450/450project-team1
_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\s*$")


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def parse_log(path: Path) -> Dict[str, Dict[str, List[IssueEntry]]]:
    """Parse a sprint log file.

    Returns a nested dict:
        { repo_name -> { username -> [IssueEntry, ...] } }
    """
    result: Dict[str, Dict[str, List[IssueEntry]]] = {}
    current_repo: Optional[str] = None
    current_user: Optional[str] = None
    in_issues_block = False
    prev_line_was_separator = False

    for raw_line in path.read_text().splitlines():
        line = raw_line.rstrip()

        # Detect repo separator (========== followed by repo name)
        if line.strip() == "=" * 10:
            prev_line_was_separator = True
            current_user = None
            in_issues_block = False
            continue

        if prev_line_was_separator:
            prev_line_was_separator = False
            if _REPO_RE.match(line.strip()):
                current_repo = line.strip()
                result.setdefault(current_repo, {})
                continue

        prev_line_was_separator = False

        if current_repo is None:
            continue

        # Detect user header (not indented)
        if not line.startswith("\t"):
            m = _USER_RE.match(line)
            if m:
                current_user = m.group(1)
                result[current_repo].setdefault(current_user, [])
                in_issues_block = False
            continue

        # Inside a user block
        if current_user is None:
            continue

        stripped = line.strip()

        # Start of issues block
        if stripped.startswith("Issues:"):
            in_issues_block = True
            continue

        # End of issues block when we hit Commits: or PRs:
        if stripped.startswith("Commits:") or stripped.startswith("PRs:"):
            in_issues_block = False
            continue

        if in_issues_block:
            m = _ISSUE_RE.match(line)
            if m:
                entry = IssueEntry(
                    state=m.group(1),
                    milestone=m.group(2),
                    number=int(m.group(3)),
                    title=m.group(4),
                    url=m.group(5),
                )
                result[current_repo][current_user].append(entry)

    return result


# ---------------------------------------------------------------------------
# Comparison logic
# ---------------------------------------------------------------------------

def compare(
    sprint2: Dict[str, Dict[str, List[IssueEntry]]],
    sprint3: Dict[str, Dict[str, List[IssueEntry]]],
) -> Dict[str, Dict[str, Dict]]:
    """Compare sprint2 vs sprint3 per repo per user.

    Returns:
        { repo -> { user -> { 'new': [...], 'changed': [(s2, s3), ...], 'still_open': [...] } } }
    """
    all_repos = set(sprint2) | set(sprint3)
    out: Dict[str, Dict[str, Dict]] = {}

    def _team_num(repo_name: str) -> int:
        m = re.search(r"team-?(\d+)", repo_name, re.IGNORECASE)
        return int(m.group(1)) if m else 0

    for repo in sorted(all_repos, key=_team_num):
        out[repo] = {}
        users2 = sprint2.get(repo, {})
        users3 = sprint3.get(repo, {})
        all_users = set(users2) | set(users3)

        for user in sorted(all_users):
            issues2: Dict[int, IssueEntry] = {i.number: i for i in users2.get(user, [])}
            issues3: Dict[int, IssueEntry] = {i.number: i for i in users3.get(user, [])}

            new_issues = [
                issues3[n] for n in sorted(issues3)
                if n not in issues2
            ]
            changed = [
                (issues2[n], issues3[n])
                for n in sorted(issues3)
                if n in issues2 and issues2[n].state != issues3[n].state
            ]
            still_open = [
                issues2[n]
                for n in sorted(issues2)
                if issues2[n].state == "OPEN" and issues3.get(n) and issues3[n].state == "OPEN"
            ]

            out[repo][user] = {
                "new": new_issues,
                "changed": changed,
                "still_open": still_open,
            }

    return out


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def report(
    comparison: Dict[str, Dict[str, Dict]],
    sprint2_path: Path,
    sprint3_path: Path,
) -> None:
    log = logging.getLogger()
    log.info("Sprint Issue Delta Report")
    log.info("  Comparing: %s  ->  %s", sprint2_path.name, sprint3_path.name)
    log.info("=" * 72)

    for repo, users in comparison.items():
        log.info("\n%s", repo)
        log.info("-" * 60)

        for user, data in users.items():
            new = data["new"]
            changed = data["changed"]
            still_open = data["still_open"]

            if not new and not changed and not still_open:
                continue

            log.info("\n  %s", user)

            if new:
                log.info("    (a) New in Sprint 3 [%d]:", len(new))
                for i in new:
                    log.info("          %s", i.format())

            if changed:
                log.info("    (b) Status changed [%d]:", len(changed))
                for i2, i3 in changed:
                    log.info(
                        "          %s -> %s  #%d %s %s",
                        i2.state, i3.state, i3.number, i3.title, i3.url,
                    )

            if still_open:
                log.info("    (c) Still OPEN from Sprint 2 [%d]:", len(still_open))
                for i in still_open:
                    log.info("          %s", i.format())


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logs_dir = Path("logs")
    sprint2_path = logs_dir / "Sprint2.log"
    sprint3_path = logs_dir / "Sprint3.log"

    # Allow overrides from command line: compare_sprints.py <sprint2.log> <sprint3.log>
    if len(sys.argv) == 3:
        sprint2_path = Path(sys.argv[1])
        sprint3_path = Path(sys.argv[2])

    for p in (sprint2_path, sprint3_path):
        if not p.exists():
            print(f"ERROR: file not found: {p}", file=sys.stderr)
            sys.exit(1)

    out_path = logs_dir / "Sprint2_vs_Sprint3.log"
    logs_dir.mkdir(exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(out_path, "w"),
        ],
    )

    sprint2_data = parse_log(sprint2_path)
    sprint3_data = parse_log(sprint3_path)
    comparison = compare(sprint2_data, sprint3_data)
    report(comparison, sprint2_path, sprint3_path)

    logging.getLogger().info("\nOutput written to %s", out_path)
