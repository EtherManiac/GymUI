# Personal Workout Planner

A small Streamlit application for selecting, shortening, and checking off workouts while maintaining a reusable exercise library and routine definitions.

The included Push 1, Pull 1, and Legs routines are fictional sample data. Replace or edit them in the app rather than treating them as training advice.

## Features

- Mobile-friendly workout checklist with short-lived workout recovery
- Completed exercises move below active work; supersets move only when every member is complete
- Explicit exercise alternatives per routine slot
- Supersets that remain adjacent during selection and shuffling
- Exercise library and routine editors with stable IDs
- Validated, human-readable JSON storage
- Single-file backup download and restore
- Lightweight Tyler, Mia, and Dev profiles without authentication or credentials

## Local setup

Python 3.10 or newer is recommended.

### Windows PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run app.py
```

### macOS or Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
streamlit run app.py
```

Streamlit prints a local URL, normally `http://localhost:8501`. Use the sidebar to move between Workout, Edit exercises, and Edit routines.

Run the standard-library test suite with:

```bash
python -m unittest discover -s tests -v
```

## Data model

Each profile has independent `exercises.json` and `routines.json` files under
`data/users/<user-id>/`. Both documents use `schema_version: 1`. The bundled
sample data belongs to Dev; Tyler and Mia begin with empty libraries.

An exercise contains:

- `id`: stable unique string used by routine references
- `name`: display name
- `muscles_targeted`: one or more required muscle-group labels
- `tags`: optional additional labels such as movement type or equipment
- `notes`: optional technique or setup note

A routine contains a stable `id`, a `name`, and ordered `slots`. Each slot contains:

- Stable `id` and positive `order`
- Positive integer `priority`, where 1 is highest and is kept longest
- Non-empty `required_muscles` and optional `required_tags`; both use match-all filtering
- `default_exercise_id` and explicit `alternative_exercise_ids`
- String values for `sets`, `reps`, and `reference_weight`
- Optional `superset_group_id`; slots sharing an ID form one group

Sets, reps, and reference weight belong to a routine slot—not to the reusable exercise. A workout substitution keeps the slot's prescription and never changes the saved routine.

### Order, priority, and shortened workouts

Order and priority are independent. Order controls where an item appears in the workout. Priority controls which items are retained when fewer exercises are requested; 1 is the highest priority. Equal priorities are resolved by routine order, and the final selection is always displayed in routine order.

The app treats every grouped set as one indivisible unit with one shared priority. It searches for a combination that exactly matches the requested exercise count. If several combinations have the same count, it keeps the highest-priority combination; routine order breaks remaining ties. If an exact count is impossible, it returns the closest lower count. It never silently breaks a superset, triset, or giant set.

## Saving and backups

Editor changes are validated and then written to the selected profile's two
local JSON files using atomic file replacement. In-progress workout state is
stored separately in `active_workout.json` for up to 12 hours so checked items,
weights, substitutions, and order can be recovered after a session ends. This
draft never modifies the saved routine.

In the sidebar, **Data backup** downloads both JSON documents as one portable backup. Import validates the entire backup before replacing local data.

Streamlit Community Cloud does not provide durable application filesystem storage. Edits made in a deployed app can disappear after a restart, redeployment, or replica change. Hosted users should download a backup after editing and import it in a future session. This keeps the MVP free of external services, but it requires deliberate user action. A durable database or object store can be added later only if its credentials, cost, and operational tradeoffs are explicitly approved.

## GitHub and Streamlit Community Cloud

1. Commit the project to a GitHub repository. Do not commit `.venv`.
2. Test locally with `streamlit run app.py`.
3. In Streamlit Community Cloud, choose **Create app** and connect the repository.
4. Select the intended branch and set the entry point to `app.py`.
5. Deploy. The service installs `requirements.txt` automatically.

No secrets are required. Commit intentional changes to the seed JSON files when you want deployments to start with updated data.

## Project layout

```text
app.py                       Native navigation entry point
pages/                       Workout and editor page scripts
workout_app/storage.py       JSON loading, atomic saves, and backup handling
workout_app/validation.py    Schema and cross-reference checks
workout_app/workout_logic.py Pure selection, grouping, and shuffle behavior
workout_app/ui_helpers.py    Shared Streamlit controls
data/users/                  Per-profile exercise, routine, and temporary draft JSON
tests/                       Standard-library unit tests
PROJECT_REQUIREMENTS.md      Original project brief
```
