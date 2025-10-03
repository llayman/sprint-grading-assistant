import json
from github import Github

with open("token.json", "r") as token_file:
    token = json.load(token_file)
_g = Github(token['token'])
org = _g.get_organization("UNCW-SENG")



REPOS = [
    {'name': 'seng401-project-jahc'},
    {'name': 'seng401-project-mawc'},
    {'name': 'seng401-project-zopac'},
]
