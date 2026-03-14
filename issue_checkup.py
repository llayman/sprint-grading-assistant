"""Scrape and summarize GitHub issues by milestone across configured repositories."""

import config


def scrape_issues(title, print_issues=True):
    """Scrape issues by milestone across configured repos and print assignee summaries."""
    for repo in config.REPOS:
        r = config.org.get_repo(repo)
        print('=' * 10)
        print(r.full_name)
        collaborators = filter(lambda x: x.login != 'llayman', r.get_collaborators())
        member_issues = {m: [] for m in map(lambda x: x.login, collaborators)}

        milestones = list(r.get_milestones())
        milestone = next((x for x in milestones if x.title.strip() == title), None)
        if not milestone:
            print(f"ERROR: No milestone named {title}: {milestones}")
            exit(1)

        multiple_assignees = []
        ms_issues = list(r.get_issues(state='all', milestone=milestone))
        print(f'\t{title} issues({len(ms_issues)}): {[x.number for x in ms_issues]} ')
        for i in ms_issues:
            for assignee in i.assignees:
                member_issues[assignee.login].append(i.number)
            if len(i.assignees) > 1:
                multiple_assignees.append(i.number)
            if print_issues:
                print(f"\t\t#{i.number} {i.title[:64]}")

        for member, issues in member_issues.items():
            print(f'\t{member}({len(issues)}): {issues}')

        if multiple_assignees:
            print(f"MULTIPLE_ASSIGNEES: {multiple_assignees}")


if __name__ == "__main__":
    scrape_issues("Sprint 3", False)
