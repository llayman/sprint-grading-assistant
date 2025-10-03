import logging
import sys
from collections import namedtuple
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
    title: str
    start: datetime
    end: datetime
    first_week_cutoff: datetime = None

class UserStats:

    def __init__(self, name: str = None):
        self.name = name
        self.pulls: List[PullRequest] = []
        self.commits: List[Commit] = []
        self.issues: List[Issue] = []


def get_stats_for_sprint(sprint: Sprint):
    log = logging.getLogger()

    for repo in config.REPOS:
        r = config.org.get_repo(repo['name'])
        log.info('=' * 10)
        log.info(r.full_name)

        user_stats: Dict[str, UserStats] = {}

        # Gather commits authored by a user. This may be separate from the committer due to merging.
        for c in r.get_commits(since=sprint.start, until=sprint.end, sha=repo.get('branch', NotSet)):
            # Commits can have no author for unknown reasons.
            if c.author is None:
                log.info(f"c.author is None: https://github.com/{r.full_name}/commit/{c.url.split('/')[-1]}")
                continue
            user_stats.setdefault(c.author.login, UserStats(c.author.name)).commits.append(c)

        # Gather user-initiated PRs
        for p in r.get_pulls(state="all"):
            if sprint.start <= p.created_at.replace(tzinfo=timezone.utc) <= sprint.end:
                user_stats.setdefault(p.user.login, UserStats(p.user.login)).pulls.append(p)

        # Gather user-assigned issues
        for i in r.get_issues(state='all'):
            if i.assignees:
                for assignee in i.assignees:
                    user_stats.setdefault(assignee.login, UserStats(assignee.login)).issues.append(i)

        sprint_first_week_cutoff = sprint.first_week_cutoff if sprint.first_week_cutoff is not None else sprint.end - timedelta(days=7)
        # Loop over user_stats dictionary to compute statistics on a per-user basis.
        for author, stats in user_stats.items():
            has_printed_cutoff = False
            log.info(
                f"\n\n{author} ({stats.name}) - {len(stats.commits)} commits, {len(stats.pulls)} PRs, {len(stats.issues)} issues assigned")

            # Show issues
            log.info(f'\tIssues: {len(stats.issues)}')
            for i in stats.issues:
                log.info(
                    f'\t\t{i.state.upper()} ({"" if i.milestone is None else i.milestone.title}) #{i.number} {i.title[:64]} https://github.com/{r.full_name}/issues/{i.number}')

            # Compute commit statistics
            log.info(f'\tCommits: {len(stats.commits)}')
            for c in stats.commits:
                # the commit's last_modified is when it was merged into main
                # the commitStats last_modified is when the source files were last worked on
                # format is Mon, 10 Oct 2022 21:33:08 GMT
                date_format = '%a, %d %b %Y %H:%M:%S %Z'
                commit_date = datetime.strptime(c.stats.last_modified, date_format).replace(tzinfo=timezone.utc)
                if commit_date < sprint_first_week_cutoff and not has_printed_cutoff:
                    log.info(f'\t\t----- FIRST WEEK END -----')
                    has_printed_cutoff = True

                # TODO: Figure a way to print the branch name
                # TODO: print commit comment
                log.info(
                    f"\t\t{to_local_time(c.stats.last_modified)} {len(c.files)} files, total:{c.stats.total} adds:{c.stats.additions} "
                    f"deletes:{c.stats.deletions} https://github.com/{r.full_name}/commit/{c.url.split('/')[-1]}")

            if not has_printed_cutoff:
                log.info(f'\t\t----- FIRST WEEK END -----')

            # compute pull request statistics
            pr_stats = {}
            for p in stats.pulls:
                pr_stats[p.state] = pr_stats.get(p.state, 0) + 1

            log.info(f'\tPRs:{len(stats.pulls)}, {pr_stats}')
            for p in stats.pulls:
                log.info(f"\t\t{to_local_time(p.created_at)} {p.html_url}")


def to_local_time(utc_date):
    if isinstance(utc_date, str):
        date_format = '%a, %d %b %Y %H:%M:%S %Z'
        utc_date = datetime.strptime(utc_date, date_format).replace(tzinfo=timezone.utc)

    return utc_date.astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')


if __name__ == "__main__":
    # SPRINT_0 = Sprint("Sprint0",
    #                   datetime(year=2024, month=9, day=13, tzinfo=ZoneInfo('US/Eastern')),
    #                   datetime(year=2024, month=10, day=3, hour=9, minute=30, tzinfo=ZoneInfo('US/Eastern')))

    SPRINT_1 = Sprint("Sprint1",
                      start=datetime(year=2024, month=2, day=22, hour=15, minute=15, tzinfo=ZoneInfo('US/Eastern')),
                      end=datetime(year=2025, month=9, day=30, hour=9, minute=30, tzinfo=ZoneInfo('US/Eastern')),
                      )

    # SPRINT_2 = Sprint("Sprint2",
    #                   datetime(year=2024, month=3, day=14, hour=15, minute=15, tzinfo=ZoneInfo('US/Eastern')),
    #                   datetime(year=2024, month=3, day=26, hour=12, minute=30,
    #                            tzinfo=ZoneInfo('US/Eastern')))  # class time the day after to include late night commits
    #
    # SPRINT_3 = Sprint("Sprint3",
    #                   start=datetime(year=2024, month=3, day=26, hour=15, minute=00, tzinfo=ZoneInfo('US/Eastern')),
    #                   end=datetime(year=2024, month=4, day=9, hour=6, minute=00, tzinfo=ZoneInfo('US/Eastern')),
    #                   first_week_cutoff=datetime(year=2024, month=4, day=4, hour=23, minute=59, tzinfo=ZoneInfo('US/Eastern')))
    #
    # SPRINT_4 = Sprint("Sprint4",
    #                   datetime(year=2024, month=4, day=9, hour=15, minute=00, tzinfo=ZoneInfo('US/Eastern')),
    #                   # Extra day
    #                   datetime(year=2024, month=4, day=23, hour=15, minute=00, tzinfo=ZoneInfo('US/Eastern')),
    #                   first_week_cutoff=datetime(year=2024, month=4, day=16, hour=23, minute=59, tzinfo=ZoneInfo('US/Eastern')))
    #
    # SPRINT_5_001 = Sprint("Sprint5",
    #                       datetime(year=2023, month=12, day=5, hour=12, minute=30, tzinfo=ZoneInfo('US/Eastern')),
    #                       datetime(year=2023, month=12, day=12, hour=12, minute=30, tzinfo=ZoneInfo('US/Eastern')))
    #
    # SPRINT_5_002 = Sprint("Sprint5",
    #                       datetime(year=2023, month=12, day=5, hour=12, minute=30, tzinfo=ZoneInfo('US/Eastern')),
    #                       datetime(year=2023, month=12, day=14, hour=12, minute=30, tzinfo=ZoneInfo('US/Eastern')))

    active_sprint = SPRINT_1

    from pathlib import Path

    # creating a new directory called pythondirectory
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
