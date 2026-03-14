"""Scrape GitHub organization project boards via the GraphQL API."""

import json
import sys
from pathlib import Path

import logging
import requests

import config



with open("token.json", "r", encoding="utf-8") as token_file:
    _HEADERS = {'Authorization': f"Bearer {json.load(token_file)['graphql_token']}"}


def _query(query: str):
    return requests.post(
        url='https://api.github.com/graphql',
        headers=_HEADERS,
        json=query,
        timeout=30
    ).json()


# def get_fields_for_project(project_id):
#     query = {
#         "query": 'query{ node(id: "' + project_id + '") { ... on ProjectV2 { fields(first: 20) '
#         '{ nodes { ... on ProjectV2Field { id name } ... on ProjectV2IterationField '
#         '{ id name configuration { iterations { startDate id }}} '
#         '... on ProjectV2SingleSelectField '
#         '{ id name options { id name }}}}}}}'}
#     print(_query(query))


def get_projects_for_org(org_login: str) -> list[dict[str, str]]:
    """
    Get all the GitHub Projects (open or closed) in an organization
    :param org_login: a string containing the plaintext org name, e.g., "UNCW-CSC-450"
    :return: a list of dictionaries containing the GitHub "id" of the project and it's "title"
    """
    query = {
        "query": '{organization(login: "' + org_login
        + '") {projectsV2(first: 20) {nodes {id title}}}}'
    }
    result = _query(query)
    return result['data']['organization']['projectsV2']['nodes']


def print_items_for_project(project: dict[str, str]) -> None:
    """
    Prints out the title and contents of items (issues) for a project
    :param project: a dictionary containing the GitHub "id" and "title" of a project
    :return: None
    """

    log = logging.getLogger()

    log.info('%s BEGIN PROJECT: %s', '=' * 10, project["title"])
    # This query gets all "items" affiliated with a GitHub Project
    items_query = (
        'query{ node(id: "' + project["id"] + '") { ... on ProjectV2 { items(first: 100) { '
        'nodes{ id '
        'fieldValues(first: 8) { nodes{ ... on ProjectV2ItemFieldTextValue { text field { '
        '... on ProjectV2FieldCommon {  name }}} '
        '... on ProjectV2ItemFieldDateValue { date field { '
        '... on ProjectV2FieldCommon { name } } } '
        '... on ProjectV2ItemFieldSingleSelectValue { name field { '
        '... on ProjectV2FieldCommon { name }}}}} content{ ... on DraftIssue { title '
        'body } ...on Issue { title assignees(first: 10) { nodes{ login }}} ...on PullRequest { '
        'title assignees(first: 10) { nodes{ login }}}}}}}}}'
    )
    query = {"query": items_query}
    result = _query(query)

    # Get a list of individual items to iterate over
    items = result['data']['node']['items']['nodes']
    for item in items:
        # Each issue has 'content' with 'title', 'body', 'assignees'. Body/assignees may be absent.
        content = item['content']
        title = content['title']
        body = content.get('body')
        # assignees = content.get('assignees')

        log.info('%s\nTitle: "%s"', '-' * 10, title)
        log.info('%s\n', body if body else "<< No content >>")

    log.info('%s END PROJECT: %s', '=' * 10, project["title"])


if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(Path('logs') / 'project_boards.log', 'w+')
        ]
    )

    PROJECT_ID = 'PVT_kwDOBUTQDs4ALeSM'
    # get_fields_for_project(PROJECT_ID)
    # get_items_for_project(PROJECT_ID)
    projects = get_projects_for_org(config.org.login)
    for p in projects:
        print(p)
        print_items_for_project(p)
