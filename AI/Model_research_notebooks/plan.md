# Plan: Add Camera-Angle-Invariant VAE Models with Research Notebooks and Developer-Side Model Switching

## Context

The current system uses DTW against a hardcoded template. We want to:
1. Build multiple model alternatives (Summary Stats VAE, LSTM VAE, LSTM+Attention VAE)
2. Experiment with them in Jupyter notebooks before integrating
3. Have a simple developer config to switch which model is active in production

---

## Part 1: Research Notebooks

Create an `AI/Model_research_notebooks/` folder with one notebook per model approach. Each notebook is self-contained: loads training data, trains the model, evaluates it, and visualizes results. This lets you iterate fast without touching production code.

### Notebooks to create

| Notebook | What it covers |
|----------|---------------|
| `01_summary_stats_vae.ipynb` | Summary Statistics VAE — compresses each rep into statistical features |
| `02_lstm_vae.ipynb` | LSTM VAE (without attention) and LSTM+Attention VAE — two versions in one notebook |

### What each notebook contains

**Common setup section** (same in both notebooks):
```python
# 1. Load landmark .npy files from AI/training_data/{exercise}/
# 2. Compute angles → smooth → find reps → extract rep data
# 3. Reuses existing utility functions (compute_angle_features_2d, smooth_angles, etc.)
# 4. Split into train/validation sets
# 5. Visualize: plot angle signals, rep boundaries, data distribution
```

**Model-specific sections**:
- Define the model architecture (PyTorch nn.Module)
- Training loop with loss curves
- Evaluation: run validation reps through model, compute reconstruction errors
- Score calibration: map errors to 0-1 similarity scores
- Camera angle test: if you have data from multiple angles, compare score consistency
- Export: save best model weights to `AI/mlp/models/`

### Notebook 1: Summary Stats VAE (`01_summary_stats_vae.ipynb`)

**Input construction**:
- Takes rep angle data `(T, 13)` where T varies per rep
- Computes 7 statistics per feature: mean, std, min, max, range, skewness, 25th percentile
- 13 features x 7 stats = 91 values
- Plus 4 symmetry stats + 2 depth stats = **97 values total**
- Add 5-dim exercise one-hot → **102-dim input**
- Works with any rep length since it's just computing statistics

**VAE architecture**:
```
Encoder: 102 → 256 (BatchNorm, ReLU, Dropout 0.2)
              → 128 (BatchNorm, ReLU, Dropout 0.2)
              → mu(32), log_var(32)

Decoder: 37 (32 latent + 5 exercise one-hot)
              → 128 (BatchNorm, ReLU, Dropout 0.2)
              → 256 (BatchNorm, ReLU, Dropout 0.2)
              → 97

Loss: MSE(input, reconstruction) + 0.5 * KL_divergence
```

**What it can detect**: Range of motion issues, asymmetry, wrong average positions, inconsistent movement. **What it misses**: Temporal patterns (bounce at bottom vs controlled pause).

---

### Notebook 2: LSTM VAE — Two Versions (`02_lstm_vae.ipynb`)

Both versions in this notebook process the rep frame-by-frame and handle variable-length reps natively.

#### Version A: LSTM VAE (no attention)

**Input**: Raw frame sequence `(T, 29)` — the existing 29-dim embedding per frame. T varies per rep.

**How it works**:
1. The LSTM encoder reads frame 1, then frame 2, ..., then frame T
2. After the last frame, the LSTM's hidden state summarizes the entire rep
3. This hidden state is compressed to a 32-dim latent vector
4. The decoder LSTM reconstructs the sequence frame by frame
5. Reconstruction error = how different the output is from the input

**Architecture**:
```
Encoder:
  LSTM(input=29, hidden=128, layers=2, bidirectional=False)
  → after T steps, final hidden state = 128-dim
  → Linear(128, 32) → mu
  → Linear(128, 32) → log_var

Decoder:
  Linear(37, 128) → initial hidden state  (37 = 32 latent + 5 exercise)
  LSTM(input=29, hidden=128, layers=2)
  → for each of T steps: Linear(128, 29) → reconstructed frame
```

**Variable length handling**: PyTorch `pack_padded_sequence` during training (batches of different-length reps). At inference, just feed one rep at a time — no padding needed.

**Limitation**: The encoder must compress the ENTIRE rep into one 128-dim hidden state after the last frame. For long reps, early frames are "forgotten" — the hidden state is dominated by recent frames. This is the classic LSTM bottleneck problem.

#### Version B: LSTM + Attention VAE

**The key improvement**: Instead of relying only on the final hidden state, the encoder saves ALL hidden states (one per frame) and uses an **attention mechanism** to create a weighted summary. The model learns which frames are most important for assessing form quality.

**How attention works here**:
1. LSTM encoder processes all T frames → produces T hidden states, each 128-dim
2. An attention layer scores each hidden state: "how important is this frame?"
3. A weighted sum of all hidden states produces the 128-dim summary
4. This summary → latent space (mu, log_var)

**Architecture**:
```
Encoder:
  LSTM(input=29, hidden=128, layers=2, bidirectional=True)
  → T hidden states, each 256-dim (128 forward + 128 backward)

  Attention:
    Linear(256, 64) → tanh → Linear(64, 1) → softmax over T frames
    → attention weights: (T,) — one weight per frame
    → context = weighted sum of hidden states → 256-dim

  Linear(256, 32) → mu
  Linear(256, 32) → log_var

Decoder:
  Linear(37, 256) → initial hidden state
  LSTM(input=29, hidden=256, layers=2)
  → for each of T steps: Linear(256, 29) → reconstructed frame
```

**What attention adds**:
- The model can focus on the bottom of the squat (most critical frame for depth) and the transition point (where form typically breaks down)
- You can visualize attention weights to see WHICH frames the model considers important — this is interpretable and useful for debugging
- Better at long reps — doesn't lose early frames like vanilla LSTM
- Bidirectional LSTM means it sees both "what comes before" and "what comes after" each frame

**Comparison section in the notebook**:
- Train both versions on the same data
- Compare: reconstruction loss convergence, validation scores, score consistency across camera angles
- Plot attention weights for sample reps — see if the model focuses on biomechanically meaningful moments

---

## Part 2: Developer-Side Model Switching (Production Integration)

Once you've experimented in notebooks and found a model you like, integrate it:

**`AI/process_landmarks/model_config.py`** (new file):
```python
# Change this to switch models. Options: "dtw", "stats_vae", "lstm_vae", "lstm_attention_vae"
ACTIVE_MODEL = "dtw"
```

**`AI/process_landmarks/verdict.py`** (modified):
- `_load_model()` reads `ACTIVE_MODEL` and instantiates the right class
- `analyze_user_video()` calls `model.score_rep()` instead of `compare_rep_to_template()`
- Signature stays the same — no downstream changes needed

Each model class implements `score_rep()` returning the exact same dict format as `compare_rep_to_template()` currently returns:
```python
{
    'per_feature': [...],        # list of per-joint results
    'overall_similarity': float, # 0-1
    'core_similarity': float,    # 0-1
    'template_flexion': float,
    'user_flexion': float,
    'hit_parallel': bool,
    'depth_score': float,        # 0-100
}
```

This means the .NET backend, the API, and the frontend all remain completely unchanged. You just flip `ACTIVE_MODEL` and rebuild.

---

## Part 3: Production Model Files

Once a model is trained and validated in notebooks, its production code lives here:

### Files to CREATE

| File | Purpose |
|------|---------|
| `AI/Model_research_notebooks/01_summary_stats_vae.ipynb` | Research notebook for Summary Stats VAE |
| `AI/Model_research_notebooks/02_lstm_vae.ipynb` | Research notebook for LSTM VAE + LSTM+Attention VAE |
| `AI/Model_research_notebooks/plan.md` | Copy of this implementation plan for reference |
| `AI/process_landmarks/model_config.py` | `ACTIVE_MODEL = "dtw"` — one-line switch |
| `AI/process_landmarks/dtw_model.py` | Wraps existing DTW in `score_rep()` interface |
| `AI/mlp/__init__.py` | Package init |
| `AI/mlp/model.py` | All three VAE architectures (Stats, LSTM, LSTM+Attention) |
| `AI/mlp/feature_stats.py` | `compute_rep_stats()` for the Summary Stats VAE |
| `AI/mlp/inference.py` | Model classes implementing `score_rep()` |
| `AI/mlp/train_vae.py` | Standalone training script (alternative to notebooks) |
| `AI/mlp/models/` | Saved model weights + normalization stats |
| `AI/training_data/{exercise}/` | Training landmark data organized by exercise |

### Files to MODIFY

| File | What changes |
|------|-------------|
| `AI/process_landmarks/verdict.py` | Add `_load_model()`. Replace `compare_rep_to_template()` with `model.score_rep()` |
| `AI/process_landmarks/exercise_config.py` | Add `EXERCISE_INDEX` for one-hot encoding. Expand `CORE_FEATURES` for all 5 exercises |
| `AI/requirements.txt` | Add `torch` (CPU), `scipy`, `jupyter` |

### Files NOT changed

- `dtw_analysis.py` — kept as-is, wrapped by `dtw_model.py`
- `main.py` (FastAPI) — no API changes
- `VideoController.cs` — no .NET changes
- `App.tsx` — no frontend changes

---

## Part 4: Implementation Order

1. **Create notebook infrastructure** — `AI/Model_research_notebooks/` folder, save plan, common data loading code
2. **Model switching** — `model_config.py`, `dtw_model.py`, refactor `verdict.py`. Verify DTW still works.
3. **Notebook 1** — Summary Stats VAE: build, train, evaluate
4. **Notebook 2** — LSTM VAE + LSTM+Attention VAE: build, train, compare
5. **Pick winner** — compare all three models' scores across camera angles
6. **Productionize** — move best model's code to `AI/mlp/`, set `ACTIVE_MODEL`, test end-to-end

## Part 5: Verification

1. After step 2: `docker compose up --build`, analyze video — DTW still works identically
2. After step 3-4: notebook outputs show training loss convergence + reasonable scores
3. After step 6: switch `ACTIVE_MODEL`, rebuild, verify frontend shows results
4. Switch back to `"dtw"` — verify nothing breaks
5. Compare scores across camera angles for each model
