# Sprint Grading Assistant

## token.json

Create `token.json` in the project root:

```json
{
    "token": "<your-github-token>"
}
```

**GitHub token scope:** `repo` (read access to the organization and its repositories).

## Sprints

In `main.py`, each `SPRINT_X` is a `Sprint(title, start, end, first_week_cutoff=None)`. Use `get_class_start(month, day)` and `get_class_end(month, day)` for class-time boundaries (timezone and class time come from `TZ`, `CLASS_HOUR`, `CLASS_MINUTE`, `CLASS_DURATION` at the top of the block).

Set `active_sprint` to the sprint to grade, e.g. `active_sprint = SPRINT_1`.

## Run

```bash
pip install -r requirements.txt
python main.py
```

Output goes to stdout and `logs/<SprintName>.log`.
