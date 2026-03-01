import json
from github import Github

with open("token.json", "r") as token_file:
    token = json.load(token_file)
_g = Github(token['token'])
org = _g.get_organization("UNCW-CSC-450")



REPOS = [
    {'name': '450project-team1'},
    {'name': '450project-team2'},
    {'name': '450project-team-3'},
    {'name': '450project-team-4'},
    {'name': '450project-team5'},
    {'name': '450project-team6'},
]
