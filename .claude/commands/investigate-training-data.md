---
description: Investigate new files under AI/training_data/ and propose a prep plan for template/model training
argument-hint: [exercise]
allowed-tools: Agent
---

# Investigate training data

Launch the `training-data-investigator` subagent (defined in `.claude/agents/training-data-investigator.md`) to inventory new files under `AI/training_data/` and produce a prep proposal. The agent is read-only — it returns a written plan, it does not run the pipeline.

**Arguments**
- `$1` — optional exercise folder name (`back_squat`, `front_squat`, `deadlift`, `benchpress`, `military_press`). When provided, the agent focuses on that folder only. When empty, it sweeps every `AI/training_data/<exercise>/` subdirectory.

## Steps

1. Use the `Agent` tool with `subagent_type: training-data-investigator`.
2. Build the prompt:
   - If `$1` is empty: `"Investigate all subfolders under AI/training_data/ and produce the full prep report per your instructions."`
   - Otherwise: `"Investigate AI/training_data/$1/ only. Produce the prep report per your instructions, scoped to that exercise."`
3. Relay the agent's report to the user verbatim — do not re-summarize or re-format it. The agent already knows the required output structure.
4. After the report, ask the user which exercise (if any) they want to proceed with. Do not start running MediaPipe or `create_template_from_landmarks` until they say so.
