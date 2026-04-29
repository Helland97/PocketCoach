---
description: List user-reported ideas and implement one of them
argument-hint: [id-or-index | list | dismiss <id> | done <id>]
allowed-tools: Bash, Read, Edit, Write, Glob, Grep
---

# Work on a reported idea

Ideas submitted via the "Report an idea/improvement" button in the frontend are persisted to `ideas/ideas.json` (when running via Docker, the `./ideas:/app/Ideas` bind mount makes them appear at the repo root). Each entry has this shape:

```json
{
  "id": "idea-YYYYMMDD-HHMMSS-xxxxxx",
  "submittedAt": "ISO 8601 UTC",
  "status": "new | in-progress | done | dismissed",
  "title": "...",
  "category": "new feature | UI/UX improvement | analysis accuracy | performance | exercise/camera support | other",
  "affectedArea": "frontend | dotnet-backend | python-backend | cross-cutting | infrastructure/docker | not sure",
  "description": "...",
  "problem": "...",
  "acceptance": "..."
}
```

## Find the file

Check both locations (Docker bind mount vs local-dev run from `Backend/`):

1. `ideas/ideas.json` (primary — this is what the Docker compose bind mount produces)
2. `Backend/Ideas/ideas.json` (fallback — if the user ran `dotnet run` locally instead of Docker)

If neither exists, report "No ideas reported yet." and stop. Do NOT create the file from Claude's side — it's produced by the backend when the user submits through the form.

## Argument handling

`$ARGUMENTS` can be:
- empty → list all non-dismissed ideas, ask the user to pick one
- `list` → list all ideas (including dismissed and done), then stop
- `<id>` (e.g. `idea-20260423-142330-abc123`) → load that idea and proceed to implementation
- `<index>` (e.g. `3`) → pick the N-th idea from the `new` / `in-progress` list shown by the empty-arg case
- `dismiss <id>` → set that idea's status to `dismissed`, no implementation
- `done <id>` → set that idea's status to `done`, no implementation
- `reopen <id>` → set status back to `new`

## Steps

1. **Load the file**
   - Read the JSON, parse it. If parsing fails, show the user the offending line/bytes and stop — do not try to auto-repair.

2. **Handle bulk-mode args first** (`list`, `dismiss`, `done`, `reopen`)
   - For `list`: print a table: `# | id | status | category | title | submittedAt`. One line per idea, wrap titles at ~60 chars. Done.
   - For `dismiss <id>` / `done <id>` / `reopen <id>`: find the idea by id (exact match), update `status`, write the file back with the same formatting (2-space indent, trailing newline). Print a one-line confirmation. Done.

3. **Empty arg or specific pick**
   - If empty: filter to `status in {new, in-progress}`. If zero, report "No open ideas." and stop. Otherwise print a table and ask: "Which one should I work on? Reply with the index or id, or `dismiss <id>` to drop it."
   - If arg is an integer, resolve via the open-ideas list from the previous step. If out of range, report and stop.
   - If arg looks like an id (starts with `idea-`), match exactly. If not found, report and stop.

4. **Before implementing, set status to `in-progress`**
   - Update the status in the JSON and save. This way if the session ends, the next invocation knows work is in flight.
   - Print the idea's full body (title, category, affectedArea, description, problem, acceptance) so the user can see what Claude read.

5. **Scope the work**
   - Use `affectedArea` as a hint for which directory to start in:
     - `frontend` → `frontend/src/`
     - `dotnet-backend` → `Backend/`
     - `python-backend` → `AI/`
     - `cross-cutting` → expect to touch more than one
     - `infrastructure/docker` → `docker-compose.yml`, `*/Dockerfile*`, `frontend/nginx.conf`
     - `not sure` → ask the user where to start before touching code
   - Use `acceptance` as the definition of done. If it's empty, ask the user for one before writing code.

6. **Implement**
   - Small, focused changes. Follow conventions in `CLAUDE.md`. Don't add features the idea didn't ask for.
   - If you hit a fork in the road (two reasonable designs), stop and ask — don't guess.
   - Test as appropriate: `npm run build && npm run lint` for frontend changes, `dotnet build` for backend. Python changes: run `python -m py_compile <files>` at minimum, plus `AI/test.py` if it's relevant.
   - For UI changes, you cannot verify in a browser from here — say so explicitly rather than claiming it works.

7. **When done**
   - Do NOT auto-mark the idea as `done` or auto-commit. Leave status as `in-progress` and tell the user:
     - exactly what changed (files + one-line-per-file summary)
     - how to verify it meets the acceptance criteria
     - that they should run `/reported_idea done <id>` once they're happy with it, or `/reported_idea reopen <id>` to kick it back to `new`

## Notes for Claude

- The ideas file is gitignored (`ideas/`, `Backend/Ideas/`). Don't stage it or commit it. Status updates you make to it stay local.
- Preserve JSON formatting: 2-space indent, camelCase keys, ISO timestamps. Don't reorder fields — the backend writes them in a specific order and churn makes diffs noisy if the file ever does get committed.
- If multiple ideas match the same `affectedArea`, don't batch them without the user asking — one idea at a time.
- The backend endpoint is `POST /Idea/submit` (via nginx → `dotnet-backend:8080`). If the user reports that submission is failing, check that route first.
