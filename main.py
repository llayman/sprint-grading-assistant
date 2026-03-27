"""Sprint grading assistant: aggregates GitHub PRs, commits, and issues per user for a sprint."""
import logging
import sys
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Dict, List
from zoneinfo import ZoneInfo

from github.PullRequest import PullRequest
from github.Commit import Commit
from github.Issue import Issue
from github.GithubObject import NotSet

import config


@dataclass
class Sprint:
    """Represents a sprint with its title and date range (start, end, first_week_cutoff)."""
    title: str
    start: datetime
    end: datetime
    first_week_cutoff: datetime = None


class UserStats:
    """Holds per-user sprint stats: name and lists of pulls, commits, and assigned issues."""

    def __init__(self, name: str = None):
        self.name = name
        self.pulls: List[PullRequest] = []
        self.commits: List[Commit] = []
        self.issues: List[Issue] = []


def get_stats_for_sprint(sprint: Sprint):
    """Aggregate commits, PRs, and assigned issues per user for the given
    sprint and log the stats."""
    log = logging.getLogger()

    for repo in config.REPOS:
        r = config.org.get_repo(repo['name'])
        log.info('=' * 10)
        log.info(r.full_name)

        user_stats: Dict[str, UserStats] = {}

        # Gather commits authored by a user (may differ from committer due to merging).
        # c.author is the GitHub user (can be None if not linked); c.commit.author is the
        # git author (name/email) and is what GitHub's UI shows on the commit page.
        for c in r.get_commits(
                since=sprint.start, until=sprint.end, sha=repo.get('branch', NotSet)):
            if c.author is not None:
                login, name = c.author.login, (c.author.name or c.author.login)
            else:
                login = (c.commit.author.name or c.commit.author.email or "unknown")
                name = c.commit.author.name or c.commit.author.email or "unknown"
            user_stats.setdefault(login, UserStats(name)).commits.append(c)

        # Gather user-initiated PRs
        for p in r.get_pulls(state="all"):
            if sprint.start <= p.created_at.replace(tzinfo=timezone.utc) <= sprint.end:
                user_stats.setdefault(p.user.login, UserStats(p.user.login)).pulls.append(p)

        # Gather user-assigned issues
        for i in r.get_issues(state='all'):
            if i.assignees:
                for assignee in i.assignees:
                    entry = user_stats.setdefault(assignee.login, UserStats(assignee.login))
                    entry.issues.append(i)

        if sprint.first_week_cutoff is not None:
            sprint_first_week_cutoff = sprint.first_week_cutoff
        else:
            sprint_first_week_cutoff = sprint.end - timedelta(days=7)
        # Loop over user_stats dictionary to compute statistics on a per-user basis.
        for author, stats in user_stats.items():
            has_printed_cutoff = False
            log.info(
                "\n\n%s (%s) - %s commits, %s PRs, %s issues assigned",
                author, stats.name, len(stats.commits), len(stats.pulls), len(stats.issues))

            # Show issues
            log.info('\tIssues: %s', len(stats.issues))
            for i in stats.issues:
                milestone_title = "" if i.milestone is None else i.milestone.title
                log.info(
                    '\t\t%s (%s) #%s %s https://github.com/%s/issues/%s',
                    i.state.upper(), milestone_title, i.number, i.title[:64],
                    r.full_name, i.number)

            # Compute commit statistics
            log.info('\tCommits: %s', len(stats.commits))
            for c in stats.commits:
                # the commit's last_modified is when it was merged into main
                # the commitStats last_modified is when the source files were last worked on
                # format is Mon, 10 Oct 2022 21:33:08 GMT
                commit_date = datetime.strptime(
                    c.stats.last_modified, _COMMIT_DATE_FMT).replace(tzinfo=timezone.utc)
                if commit_date < sprint_first_week_cutoff and not has_printed_cutoff:
                    log.info('\t\t----- FIRST WEEK END -----')
                    has_printed_cutoff = True

                # TODO: Figure a way to print the branch name
                # TODO: print commit comment
                log.info(
                    "\t\t%s %s files, total:%s adds:%s deletes:%s https://github.com/%s/commit/%s",
                    to_local_time(c.stats.last_modified), len(c.files), c.stats.total,
                    c.stats.additions, c.stats.deletions, r.full_name, c.url.split('/')[-1])

            if not has_printed_cutoff:
                log.info('\t\t----- FIRST WEEK END -----')

            # compute pull request statistics
            pr_stats = {}
            for p in stats.pulls:
                pr_stats[p.state] = pr_stats.get(p.state, 0) + 1

            log.info('\tPRs:%s, %s', len(stats.pulls), pr_stats)
            for p in stats.pulls:
                log.info("\t\t%s %s %s", to_local_time(p.created_at), p.head.ref, p.html_url)


# GMT date format from GitHub commit stats API
_COMMIT_DATE_FMT = '%a, %d %b %Y %H:%M:%S %Z'
_OUTPUT_DATE_FMT = '%Y-%m-%d %H:%M:%S'


def to_local_time(utc_date):
    """Convert a UTC datetime to local time in the specified format."""
    if isinstance(utc_date, str):
        utc_date = datetime.strptime(utc_date, _COMMIT_DATE_FMT).replace(tzinfo=timezone.utc)
    return utc_date.astimezone().strftime(_OUTPUT_DATE_FMT)


if __name__ == "__main__":
    TZ = ZoneInfo('US/Eastern')
    YEAR = datetime.now().year
    CLASS_HOUR = 11
    CLASS_MINUTE = 00
    CLASS_DURATION = 50

    def get_class_start(month, day, year=YEAR, hours=CLASS_HOUR, minutes=CLASS_MINUTE, tz=TZ):
        """Return a datetime for the start of class on the given date."""
        return datetime(year, month, day, hours, minutes, tzinfo=tz)

    def get_class_end(
            month, day, duration=CLASS_DURATION, year=YEAR,
            hours=CLASS_HOUR, minutes=CLASS_MINUTE, tz=TZ):
        """Return a datetime for the end of class on the given date (start + duration)."""
        return datetime(year, month, day, hours, minutes, tzinfo=tz) + timedelta(minutes=duration)

    SPRINT_0 = Sprint("Sprint0",
                      datetime(year=2026, month=2, day=1, tzinfo=TZ),
                      get_class_start(month=2, day=23))

    SPRINT_1 = Sprint("Sprint1",
                start=get_class_end(month=2, day=23),
                end=datetime(year=2026, month=3, day=11, hour=0, minute=0, tzinfo=TZ),
                first_week_cutoff=datetime(
                    year=YEAR, month=2, day=28, hour=0, minute=0, tzinfo=TZ))

    SPRINT_2 = Sprint("Sprint2",
                      start=get_class_end(3, 11),
                      end=datetime(year=2026, month=3, day=25, hour=0, minute=0, tzinfo=TZ),
                      first_week_cutoff=datetime(year=YEAR, month=3, day=18, hour=0, minute=0,
                                                 tzinfo=TZ))
    
    SPRINT_2_TEAM_5 = Sprint("Sprint2 Team 5",
                    start=get_class_end(3, 11),
                    end=datetime(year=2026, month=3, day=27, hour=0, minute=0, tzinfo=TZ),
                    first_week_cutoff=datetime(year=YEAR, month=3, day=18, hour=0, minute=0,
                                                tzinfo=TZ))

    SPRINT_3 = Sprint("Sprint3",
                      start=get_class_end(10, 16),
                      end=get_class_start(10, 28),
                      first_week_cutoff=datetime(
                          year=YEAR, month=10, day=20, hour=23, minute=59, tzinfo=TZ))

    SPRINT_4 = Sprint("Sprint4",
                      start=get_class_end(10, 28),
                      end=get_class_start(11, 11),
                      first_week_cutoff=datetime(
                          year=YEAR, month=11, day=3, hour=23, minute=59, tzinfo=TZ))

    SPRINT_5 = Sprint("Sprint5", start=get_class_end(11,11), end=get_class_start(11,25))
    #
    # SPRINT_5_002 = Sprint("Sprint5",
    #                       datetime(year=2023, month=12, day=5, hour=12, minute=30, tzinfo=TZ),
    #                       datetime(year=2023, month=12, day=14, hour=12, minute=30, tzinfo=TZ))

    active_sprint = SPRINT_2_TEAM_5

    from pathlib import Path

    # creating a new directory called logs
    Path("logs").mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(Path('logs') / f'{active_sprint.title}.log', 'w+')
        ]
    )

    get_stats_for_sprint(active_sprint)
