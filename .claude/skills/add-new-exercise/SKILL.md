---
name: add-new-exercise
description: Wire up support for a new exercise (or a new variant of an existing one) end-to-end across the Python backend, .NET backend, and frontend. Use when the user says "add support for X", "wire up the Y exercise", "I want to add a new lift", or similar. Covers config edits, template creation, and UI updates so nothing is missed.
---

# Add a new exercise

There are five places that need to agree for a new exercise to work end-to-end. Miss one and the API silently falls back to `DEFAULT_EXERCISE` (back_squat) or the UI offers a lift the backend can't analyze. Run through them in order.

Required input from the user: the **exercise key** (snake_case, e.g. `overhead_squat`), a **human-readable label** (e.g. "Overhead Squat"), the **family** it belongs to (`squat` / `deadlift` / `benchpress` / `military_press`, or a brand-new family), and a **pro reference video** (or confirmation that one is coming).

## Step 1 — `AI/process_landmarks/exercise_config.py`

Edit in this order:

1. **`EXERCISE_INDEX`** — append `'<key>': <next_index>`. The dict is used for one-hot encoding in the learned-model path; indices must be contiguous and stable. **Never renumber existing entries** — that invalidates any trained model checkpoint that consumed those one-hots. `NUM_EXERCISES` derives from the dict, no manual edit.

2. **`CORE_FEATURES`** — only edit if the exercise belongs to a *new family*. The existing keys cover most barbell work (`squat`, `deadlift`, `benchpress`, `military_press`). Variants like `front_squat`, `overhead_squat`, `box_squat` all reuse `squat`. If you do add a new family, list 4–5 joints that drive form for that movement (mirror the structure of the existing entries).

3. **`EXERCISE_CONFIGS`** — only add a new tempo preset if none of `heavy_squat`, `bodyweight_squat`, `jump_squat`, `adaptive` fit. Most barbell work reuses `heavy_squat`. Add only if the rep cadence is genuinely different (e.g. paused reps, super-slow tempo).

4. **`EXERCISE_MAPPING`** — append:
   ```python
   '<key>': {
       'template': '<key>_template.npz',  # or whatever name build-template-from-video produced
       'tempo': 'heavy_squat',             # the EXERCISE_CONFIGS key
       'core_key': 'squat',                # the CORE_FEATURES key
   },
   ```
   This is what the API actually reads at request time. **The exercise is not reachable until this entry exists.**

## Step 2 — Create the template

Run the `build-template-from-video` skill against the pro reference. Output goes to `AI/templates/<key>_template.npz` and the filename must match what `EXERCISE_MAPPING[<key>]['template']` says.

If the user does not have a pro reference yet, stop here and tell them. The mapping can land in a PR but the template file must exist before anything is shipped — otherwise the endpoint 500s on first request.

## Step 3 — Frontend (`frontend/src/App.tsx`)

Two edits, both near the top of the file:

1. Add `<key>` to the `Exercise` union type (currently around line 11). It must match the Python key exactly — that string is sent over the wire.
2. Add `{ value: "<key>", label: "<Human Label>" }` to the `EXERCISES` array (currently around line 93). Order in the array controls UI order.

If the new exercise needs a different camera-angle workflow than the existing ones, also check the angle-selection step that appears after exercise selection — the angle options are likely shared, but verify the user's selected angle is one the template was built for.

No CSS module changes needed unless the user wants a custom icon or color.

Run `npm run lint` from `frontend/` before reporting frontend work done.

## Step 4 — .NET backend (`Backend/`)

Usually nothing to edit. The .NET side passes the `exercise` string through to Python without interpreting it (`UploadController.cs` / `VideoController.cs` forward to `PythonBackendUrl`). Confirm by grepping for hardcoded exercise strings:

```
Grep pattern: "back_squat|front_squat|deadlift|benchpress|military_press" path: Backend/
```

If any controller, service, or DTO whitelists exercise names, add `<key>` there. As of this skill being written, `Backend/PublicClasses/` DTOs use `string Exercise` — no enum to maintain — but verify this is still true.

No EF Core migration is required for adding an exercise (it's not a schema change).

## Step 5 — Verify end-to-end

1. `docker-compose up --build` (the Python image needs to pick up the new `.npz` and config; the frontend image needs to pick up the new dropdown entry).
2. In the browser at `http://localhost`, the new exercise appears in the selector.
3. Upload a test video for that exercise. Watch `docker-compose logs -f python-backend` — it should log the matched template filename and not fall back to `DEFAULT_EXERCISE`.
4. Confirm the response includes per-rep grades, not an empty result. An empty result usually means the tempo preset is wrong for the test video — adjust `EXERCISE_MAPPING[<key>]['tempo']` and reload.

## Checklist (use this verbatim when reporting back)

- [ ] `EXERCISE_INDEX` entry added (index: `<n>`)
- [ ] `CORE_FEATURES` entry added/reused (key: `<core_key>`)
- [ ] `EXERCISE_CONFIGS` tempo preset added/reused (key: `<tempo>`)
- [ ] `EXERCISE_MAPPING[<key>]` added pointing to `<template_filename>`
- [ ] Template file exists at `AI/templates/<template_filename>` (built via `build-template-from-video`)
- [ ] `Exercise` union in `frontend/src/App.tsx` updated
- [ ] `EXERCISES` array in `frontend/src/App.tsx` updated
- [ ] `npm run lint` clean
- [ ] No hardcoded exercise whitelist in `Backend/`
- [ ] End-to-end smoke-tested via Docker

## Things that often go wrong

- **Renumbering `EXERCISE_INDEX`.** Don't. Append only. Existing model checkpoints encode the old order.
- **Template filename mismatch.** `EXERCISE_MAPPING[...]['template']` must match the file in `AI/templates/` exactly, including case. Python doesn't normalize.
- **Frontend key drift.** The string in the `Exercise` type literal must match the Python `EXERCISE_MAPPING` key byte-for-byte. Typos here just silently fall back to `DEFAULT_EXERCISE`.
- **Skipping the rebuild.** Editing `exercise_config.py` while containers are running won't take effect — the Python backend reads the config at import time. Restart at minimum; rebuild if `requirements.txt` also changed.
