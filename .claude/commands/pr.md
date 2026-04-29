---
description: Run pre-flight checks across all three stacks, then commit, push, and open a PR using the repo template
---

# /pr — open a PR for the current branch

## Step 1: Pre-flight checks (mandatory)

Run all three in parallel. **If any check fails, STOP — report the failure and do not commit, push, or open a PR. Fix the issue first.**

1. `npm run lint` in `frontend/` — eslint must be clean
2. `ruff check AI/` — must report "All checks passed!"
3. `dotnet build Backend/ --nologo -v quiet` — errors fail the check; warnings are fine

These are the same checks the PostToolUse / Stop hooks run, but executed against the full current state of the branch.

## Step 2: Gather PR context

Run in parallel:

- `git status` — what's uncommitted
- `git log main..HEAD --oneline` — commits already on this branch
- `git diff main...HEAD` — full diff this PR will represent
- `gh pr view --json url,state 2>/dev/null || true` — is there already an open PR for this branch?

If the working tree is clean **and** `git log main..HEAD` is empty, report "nothing to PR" and stop.

## Step 3: Commit (only if working tree is dirty)

Look at the diff. If the changes split into unrelated themes (e.g., hooks wiring + ruff cleanup), propose a split into multiple commits. Otherwise propose one commit.

Draft a commit message focused on the *why*, not just the *what*. Confirm scope and message with the user before running `git commit`. Use a HEREDOC and include the trailer:

```
Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

Stage specific files (`git add <paths>`), don't blanket `git add -A` — there may be untracked files (like local templates, `.env`, `aispotter.db`) that shouldn't be committed.

## Step 4: Push

- If the branch has no upstream: `git push -u origin HEAD`
- Otherwise: `git push`
- **Never push to `main` directly.**

## Step 5: Open (or update) the PR

If `gh pr view` in step 2 returned a URL, the PR already exists. Don't call `gh pr create`. Just report:

> Pushed N new commit(s) to existing PR: \<url\>

If no PR exists, open one with `gh pr create --base main`. Pass the body inline so no editor opens — fill out the four sections from `.github/pull_request_template.md`:

- **What** — 1-2 sentences. The change.
- **Why** — the motivation. What problem does this solve?
- **How tested** — include the *actual* results from step 1 (e.g., "`npm run lint` clean, `ruff check AI/` reported all passed, `dotnet build Backend/` succeeded with 0 errors"). If a stack wasn't touched, say so ("frontend not modified — lint run as a regression check"). "Not tested — config-only change" is valid for non-code changes.
- **Notes** — follow-ups, known limitations, things reviewers should look at twice. Delete the section if empty.

Use a HEREDOC for the body:

```bash
gh pr create --base main --title "<short title, <70 chars>" --body "$(cat <<'EOF'
## What
...
EOF
)"
```

Report the PR URL when done.

## Constraints

- Never use `--no-verify` to skip hooks, never bypass the pre-flight checks. If something fails, fix the underlying issue.
- Never push to `main`.
- Don't include AI artifacts (templates, `.env`, `aispotter.db`, `MediaPipe_landmarks/*.npy`) in the commit even if they show up in `git status` — these are gitignored or local-only by convention.
- If the user passes arguments to `/pr` (e.g., `/pr draft`), respect them: `draft` → add `--draft`, `web` → use `--web` instead of inline body.
