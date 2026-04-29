---
description: Run the VAE training notebooks on a dataset and summarize results
argument-hint: <dataset-path> [stats|lstm|lstm-attention|all] [local|xavier]
allowed-tools: Bash, Read, Edit, Glob, Grep
---

# Train VAE models and summarize results

Run the research pipeline in `AI/Model_research_notebooks/` against a dataset, then report what the models learned.

**Arguments**
- `$1` — path to training data directory (e.g. `AI/training_data/squat_new/`). Expected to contain per-exercise subfolders of `.npy` landmark files. When `$3` is `xavier`, this is the LOCAL path — Claude rsyncs it to the Jetson.
- `$2` — which notebook to run: `stats` (01_summary_stats_vae.ipynb), `lstm` / `lstm-attention` (both in 02_lstm_vae.ipynb), or `all`. Defaults to `all` if empty.
- `$3` — training target: `local` (default — trains on the user's machine via the detached-session flow) or `xavier` (SSH into a Jetson Xavier NX and train there on its Volta GPU). `xavier` is the right choice when training should survive a full laptop power-off; it also runs faster than laptop CPU for these models.

## Prerequisites for `$3 = xavier`

Before this command can drive the Jetson, the user must have done this ONCE by hand. If any check fails, stop and tell the user exactly what's missing — do NOT try to install JetPack, CUDA, or PyTorch on the Jetson from here.

1. **SSH**: host alias `xavier` resolves and logs in without a password prompt (`ssh -o BatchMode=yes xavier true` exits 0). If not, user needs to add it to `~/.ssh/config` and install their pubkey on the Jetson.
2. **JetPack + CUDA**: `ssh xavier 'nvcc --version && nvidia-smi || tegrastats --help >/dev/null'` — confirm JetPack is installed. `tegrastats` is Jetson's `nvidia-smi` equivalent.
3. **Jetson-compatible PyTorch**: `ssh xavier 'python3 -c "import torch; print(torch.__version__, torch.cuda.is_available())"'` must print a version and `True`. If it prints `False` or ImportErrors, the user installed a generic `pip install torch` — tell them to uninstall and install the NVIDIA Jetson wheel matching their JetPack version from the NVIDIA developer forum. Do not try to auto-fix.
4. **Repo present**: `ssh xavier 'test -d ~/TempAISpotter/AI'` (or whatever `REMOTE_PROJECT_DIR` is set to). Venv at `~/TempAISpotter/AI/venv/` with `jupyter`, `scipy`, plus the Jetson torch wheel.
5. **Performance mode + fan**: recommend (don't require) `ssh xavier 'sudo nvpmodel -m 0 && sudo jetson_clocks'` before launching. This unlocks max clocks; without it training will be much slower and may thermal-throttle. Surface this to the user as a suggestion.

## Steps

1. **Validate inputs**
   - Confirm `$1` exists and contains `.npy` files. Use `Glob` with pattern `$1/**/*.npy`. If zero matches, stop and report.
   - Confirm `AI/Model_research_notebooks/plan.md` still describes the current architecture — if the notebooks have diverged, flag it before running.
   - Confirm the Python venv exists at `AI/venv/`. If not, tell the user to create it per `README.md` before proceeding.

2. **Prep the environment**
   - From `AI/`, activate the venv (`source venv/Scripts/activate` in bash-on-Windows).
   - Ensure `jupyter`, `torch`, `scipy` are installed (`pip list | grep -Ei 'jupyter|torch|scipy'`). If anything is missing, run `pip install -r requirements.txt` and report what was added.

3. **Point the pipeline at the new dataset**
   - The notebooks read from `AI/training_data/{exercise}/` by default. If `$1` is a different path, do NOT edit the notebook in place — instead set an env var `TRAINING_DATA_DIR=$1` before executing, and verify the notebook's data-loading cell honors it. If it doesn't, surface a code snippet the user should paste into the setup cell and stop.

4. **Set up a detached session so training survives terminal close**

   Training can run for hours. Always launch it inside a detached session so the user can close their terminal, disconnect SSH, or reboot the shell without killing the job.

   > **Important caveat to surface to the user up front**: tmux survives *closing the terminal*, but it does NOT survive a full power-off, and on most default configs it does NOT survive laptop sleep/suspend either. If the user literally wants to shut the machine down between starting and collecting results, tmux on their laptop is not enough — they need one of:
   > - a remote host they SSH into (where tmux on the remote keeps running regardless of their laptop state)
   > - a detached Docker container on an always-on machine (this project already uses Docker; `docker compose run -d --rm python-backend bash -c "<training command>"` is the project-native way)
   >
   > Confirm which scenario applies before picking a setup. If the user says "I'll close my laptop and reopen it later" → tmux is fine. If they say "I'll shut the computer off" → recommend the Docker or remote-host route instead.

   **Detect the environment and pick the right variant:**
   - `command -v tmux` → use tmux path below.
   - Otherwise, on Windows: tmux usually lives in WSL or Git Bash with the tmux package. If neither is available, fall back to `nohup ... &` + a log file, and tell the user reattaching won't be possible — they'll only get the log.

   **tmux setup (macOS, Linux, WSL, Git Bash with tmux):**
   ```
   # Start a named, detached session
   tmux new-session -d -s aispotter-train -c "$(pwd)/AI"

   # Activate the venv inside the session
   tmux send-keys -t aispotter-train \
     'source venv/bin/activate || source venv/Scripts/activate' C-m

   # (Commands from step 5 get sent into this session with tmux send-keys)
   ```
   Tell the user: **reattach with `tmux attach -t aispotter-train`** and detach again with `Ctrl-b d`.

   **iTerm2 equivalent (macOS only, nicer UX):**
   iTerm2's "tmux integration" mode renders tmux windows as native iTerm2 tabs. After the detached session exists, the user runs:
   ```
   tmux -CC attach -t aispotter-train
   ```
   That opens the session inside iTerm2's native UI — panes are tabs, scrollback is native, mouse works. Closing the iTerm2 window leaves tmux running in the background; reopening with the same command reattaches. If tmux isn't installed, iTerm2 integration isn't available — fall back to regular tmux or the Docker route.

   **Docker route (survives full host shutdown only if run on a different always-on host):**
   ```
   docker compose run -d --name aispotter-train --rm python-backend bash -c \
     "cd /app && jupyter nbconvert --to notebook --execute <notebook> ..."
   # Attach logs: docker logs -f aispotter-train
   ```
   Only suggest this when the user has said they want to power down *their* machine — otherwise it's overkill.

   **Jetson Xavier NX (`$3 = xavier`): remote tmux on the Jetson, laptop can fully power off**

   The Xavier NX is always-on at ~15W, has a CUDA-capable Volta GPU with Tensor Cores, and is ideal for these small VAEs. tmux runs on the Jetson, not the laptop — so powering off the laptop is fine.

   Once the prerequisites above are green:
   ```
   REMOTE_PROJECT_DIR=${REMOTE_PROJECT_DIR:-~/TempAISpotter}

   # 1. Sync the dataset from laptop → Jetson. Use a stable remote subpath so the
   #    notebooks find it via the same TRAINING_DATA_DIR env var as local runs.
   rsync -az --delete "$1/" xavier:"$REMOTE_PROJECT_DIR/AI/training_data/_remote_run/"

   # 2. Sync the notebooks (in case of local edits) — nothing else.
   rsync -az AI/Model_research_notebooks/*.ipynb \
             xavier:"$REMOTE_PROJECT_DIR/AI/Model_research_notebooks/"

   # 3. Start a named tmux session ON THE JETSON.
   ssh xavier "tmux has-session -t aispotter-train 2>/dev/null \
               || tmux new-session -d -s aispotter-train -c $REMOTE_PROJECT_DIR/AI"

   # 4. Activate venv + export training data path inside the remote session.
   ssh xavier "tmux send-keys -t aispotter-train \
     'source venv/bin/activate && \
      export TRAINING_DATA_DIR=$REMOTE_PROJECT_DIR/AI/training_data/_remote_run && \
      export CUDA_VISIBLE_DEVICES=0' C-m"
   ```
   Tell the user: **reattach from anywhere with `ssh -t xavier tmux attach -t aispotter-train`**. Detach with `Ctrl-b d`. The laptop can be fully shut down between reattaches.

   Monitor GPU usage (separate SSH session): `ssh xavier tegrastats --interval 2000` or `ssh xavier jtop` if installed.

5. **Execute the notebook(s) inside the session**

   The command is identical for both targets — only the *transport* changes. Define a `TMUX_SEND` prefix once based on `$3`, then reuse it.

   ```
   TS=$(date +%Y%m%d-%H%M%S)

   # Local:  send keys to the local tmux
   # Xavier: send keys into the tmux running on the Jetson via SSH
   if [ "$3" = "xavier" ]; then
     TMUX_SEND='ssh xavier tmux send-keys -t aispotter-train'
   else
     TMUX_SEND='tmux send-keys -t aispotter-train'
   fi

   $TMUX_SEND \
     "jupyter nbconvert --to notebook --execute \
        AI/Model_research_notebooks/01_summary_stats_vae.ipynb \
        --output 01_summary_stats_vae.run-$TS.ipynb \
        --ExecutePreprocessor.timeout=14400 \
        2>&1 | tee AI/Model_research_notebooks/run-$TS.log ; \
      echo EXIT=\$? > AI/Model_research_notebooks/run-$TS.done" C-m
   ```
   - Same pattern for `02_lstm_vae.ipynb` when `$2` is `lstm`, `lstm-attention`, or `all`.
   - The `run-$TS.done` sentinel file lets you poll for completion without attaching. Use `Bash` with `run_in_background: true` and a until-loop on the sentinel file; do NOT busy-wait in the foreground.
     - Local: `until [ -f AI/Model_research_notebooks/run-$TS.done ]; do sleep 30; done`
     - Xavier: `until ssh xavier "test -f $REMOTE_PROJECT_DIR/AI/Model_research_notebooks/run-$TS.done"; do sleep 30; done`
   - If execution fails (non-zero EXIT in the sentinel file), read the traceback from the output notebook and the log, summarize the root cause, and stop — do NOT retry blindly.
   - On `xavier`, record the session is alive across disconnects. If the user says "I'm going to shut my laptop" — that is fine, the Jetson keeps training. On reconnect, re-poll the sentinel or reattach.

6. **Extract results**
   - If `$3 = xavier`, rsync the run artifacts back to the laptop first so the rest of the flow is identical:
     ```
     rsync -az xavier:"$REMOTE_PROJECT_DIR/AI/Model_research_notebooks/run-$TS.*" \
               AI/Model_research_notebooks/
     rsync -az xavier:"$REMOTE_PROJECT_DIR/AI/Model_research_notebooks/*.run-$TS.ipynb" \
               AI/Model_research_notebooks/
     rsync -az xavier:"$REMOTE_PROJECT_DIR/AI/mlp/models/" AI/mlp/models/
     ```
   - Read the executed notebook JSON and pull, per model:
     - final training loss + validation loss
     - reconstruction error distribution on validation reps
     - camera-angle consistency (std of scores across angles for the same rep, if the notebook computed it)
     - attention weights visualization summary (LSTM+Attention only) — note which frame indices got the highest weights
   - If any model didn't converge (loss still trending down or NaN'd), call it out explicitly.
   - If `$3 = xavier`, note in the summary that weights were trained on Jetson GPU. PyTorch weight files are architecture-portable (ARM64 → x86_64 works fine) — no special handling needed for inference on the Docker backend.

7. **Produce the summary**
   Report in this shape, keeping it terse:
   ```
   Dataset: <path>, N reps: <count>, exercises: <list>
   
   Per model
   - Summary Stats VAE:   train <loss>, val <loss>, angle-consistency <score>
   - LSTM VAE:            train <loss>, val <loss>, angle-consistency <score>
   - LSTM+Attention VAE:  train <loss>, val <loss>, angle-consistency <score>
                          top-attended frames: <indices>
   
   Recommendation
   - Winner: <model>, reason: <one line>
   - Suggested AI/process_landmarks/model_config.py: ACTIVE_MODEL = "<value>"
   - Caveats: <anything the user should verify before flipping the switch>
   ```

8. **Do NOT auto-flip `ACTIVE_MODEL`.** The switch in `AI/process_landmarks/model_config.py` is a production-affecting change — suggest the one-line edit and let the user make it.

## Notes for Claude

- `AI/Model_research_notebooks/` and `AI/templates/` are gitignored. Don't commit generated `.run-*.ipynb` files or any new `.npz` templates produced during training.
- Model weights saved by the notebooks land in `AI/mlp/models/` — those are also gitignored. Mention the exact paths in the summary so the user can find them.
- Training can take hours. The tmux setup in step 4 is the primary mechanism for surviving a closed terminal. Poll for the `run-$TS.done` sentinel file with a `Bash run_in_background` until-loop — do NOT block the session, and do NOT use nested `sleep` without the `until` pattern.
- If the user wants *live* progress mid-run, point them at `tmux attach -t aispotter-train` (or `tmux -CC attach` in iTerm2). Don't try to mirror notebook output into the main chat.
- Never retrain on top of existing weights silently; if `AI/mlp/models/` already has files, note them in the summary and ask before overwriting.
