import os
import json
import numpy as np
import torch

from mlp.model import StatsVAE, LSTMVAE, LSTMAttentionVAE
from mlp.feature_stats import compute_rep_stats, STATS_DIM
from process_landmarks.exercise_config import EXERCISE_INDEX, NUM_EXERCISES
from Utils.utils.utils import inner_to_flexion

MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")


def _exercise_one_hot(exercise_type):
    """Convert exercise type string to one-hot numpy array."""
    one_hot = np.zeros(NUM_EXERCISES, dtype=np.float32)
    # Map exercise configs like 'heavy_squat' to exercise index keys like 'back_squat'
    exercise_map = {
        'heavy_squat': 'back_squat',
        'bodyweight_squat': 'back_squat',
        'jump_squat': 'back_squat',
    }
    key = exercise_map.get(exercise_type, exercise_type)
    if key in EXERCISE_INDEX:
        one_hot[EXERCISE_INDEX[key]] = 1.0
    return one_hot


def sigmoid_calibrate(error, median, iqr):
    """Map reconstruction error to a 0-1 similarity score."""
    scale = max(iqr * 2, 1e-6)
    return float(1.0 / (1.0 + np.exp((error - median * 1.5) / scale)))


def _depth_analysis(user_rep_angles, training_avg_flexion=None):
    """Compute depth score from raw angles (model-independent)."""
    user_knee_inner = (user_rep_angles[:, 2].min() + user_rep_angles[:, 3].min()) / 2
    hit_parallel = bool(user_knee_inner <= 90.0)
    user_flexion = float(inner_to_flexion(user_knee_inner))

    if user_knee_inner <= 90.0:
        depth_score = 100.0
    else:
        shortfall = user_knee_inner - 90.0
        depth_score = max(0.0, 100.0 - shortfall * 2)

    template_flexion = float(training_avg_flexion) if training_avg_flexion else 90.0

    return {
        'user_flexion': user_flexion,
        'template_flexion': template_flexion,
        'hit_parallel': hit_parallel,
        'depth_score': float(depth_score),
    }


class _BaseVAEModel:
    """Shared loading and scoring logic for all VAE models."""

    def _load_calibration(self):
        config_path = os.path.join(MODELS_DIR, "config.json")
        if os.path.exists(config_path):
            with open(config_path) as f:
                config = json.load(f)
            self.median_error = config.get("median_error", 0.01)
            self.iqr = config.get("iqr", 0.005)
            self.training_avg_flexion = config.get("training_avg_flexion", 90.0)
        else:
            self.median_error = 0.01
            self.iqr = 0.005
            self.training_avg_flexion = 90.0

    def _load_norm_stats(self):
        stats_path = os.path.join(MODELS_DIR, "norm_stats.npz")
        if os.path.exists(stats_path):
            data = np.load(stats_path)
            self.norm_mean = data["mean"]
            self.norm_std = data["std"]
        else:
            self.norm_mean = None
            self.norm_std = None

    def _normalize(self, stats):
        if self.norm_mean is not None:
            return (stats - self.norm_mean) / (self.norm_std + 1e-8)
        return stats


# ---------------------------------------------------------------------------
# Summary Statistics VAE Model
# ---------------------------------------------------------------------------

class StatsVAEModel(_BaseVAEModel):
    """Production wrapper for Summary Statistics VAE."""

    def __init__(self, model_path=None):
        model_path = model_path or os.path.join(MODELS_DIR, "stats_vae.pt")
        self._load_calibration()
        self._load_norm_stats()

        self.model = StatsVAE()
        if os.path.exists(model_path):
            self.model.load_state_dict(torch.load(model_path, map_location="cpu"))
            print(f"[StatsVAE] Loaded weights from {model_path}")
        else:
            print(f"[StatsVAE] WARNING: No weights found at {model_path}, using random weights")
        self.model.eval()

    def score_rep(self, user_rep_angles, feature_names, core_features, exercise_type):
        # 1. Compute summary statistics (works with any rep length)
        stats = compute_rep_stats(user_rep_angles)
        normalized = self._normalize(stats).astype(np.float32)

        # 2. Exercise one-hot
        exercise_oh = _exercise_one_hot(exercise_type)

        # 3. Run through VAE
        with torch.no_grad():
            stats_t = torch.tensor(normalized).unsqueeze(0)
            exercise_t = torch.tensor(exercise_oh).unsqueeze(0)
            reconstruction, mu, log_var = self.model(stats_t, exercise_t)
            reconstructed = reconstruction.squeeze(0).numpy()

        # 4. Per-feature scores (each feature has 7 stats)
        per_feature = []
        for i, name in enumerate(feature_names):
            feat_slice = slice(i * 7, (i + 1) * 7)
            feat_error = float(np.mean((normalized[feat_slice] - reconstructed[feat_slice]) ** 2))
            feat_score = sigmoid_calibrate(feat_error, self.median_error, self.iqr)
            per_feature.append({
                'feature': name,
                'correlation': feat_score,
                'mae_degrees': float(feat_error * (self.norm_std[i * 7] if self.norm_std is not None else 1.0)),
                'penalty': 1.0,
                'combined_score': feat_score,
                'is_core': name in core_features,
            })

        # 5. Overall scores
        total_error = float(np.mean((normalized[:STATS_DIM] - reconstructed) ** 2))
        overall_similarity = sigmoid_calibrate(total_error, self.median_error, self.iqr)

        core_scores = [r['combined_score'] for r in per_feature if r['is_core']]
        core_similarity = float(np.mean(core_scores)) if core_scores else overall_similarity

        # 6. Depth analysis
        depth = _depth_analysis(user_rep_angles, self.training_avg_flexion)

        return {
            'per_feature': per_feature,
            'overall_similarity': overall_similarity,
            'core_similarity': core_similarity,
            **depth,
        }


# ---------------------------------------------------------------------------
# LSTM VAE Model
# ---------------------------------------------------------------------------

class LSTMVAEModel(_BaseVAEModel):
    """Production wrapper for LSTM VAE (no attention)."""

    def __init__(self, model_path=None):
        model_path = model_path or os.path.join(MODELS_DIR, "lstm_vae.pt")
        self._load_calibration()
        self._load_norm_stats()

        self.model = LSTMVAE()
        if os.path.exists(model_path):
            self.model.load_state_dict(torch.load(model_path, map_location="cpu"))
            print(f"[LSTMVAE] Loaded weights from {model_path}")
        else:
            print(f"[LSTMVAE] WARNING: No weights found at {model_path}, using random weights")
        self.model.eval()

    def score_rep(self, user_rep_angles, feature_names, core_features, exercise_type):
        return _score_rep_sequence(
            self.model, user_rep_angles, feature_names, core_features,
            exercise_type, self.median_error, self.iqr, self.training_avg_flexion,
            has_attention=False
        )


# ---------------------------------------------------------------------------
# LSTM + Attention VAE Model
# ---------------------------------------------------------------------------

class LSTMAttentionVAEModel(_BaseVAEModel):
    """Production wrapper for LSTM + Attention VAE."""

    def __init__(self, model_path=None):
        model_path = model_path or os.path.join(MODELS_DIR, "lstm_attention_vae.pt")
        self._load_calibration()
        self._load_norm_stats()

        self.model = LSTMAttentionVAE()
        if os.path.exists(model_path):
            self.model.load_state_dict(torch.load(model_path, map_location="cpu"))
            print(f"[LSTMAttentionVAE] Loaded weights from {model_path}")
        else:
            print(f"[LSTMAttentionVAE] WARNING: No weights found at {model_path}, using random weights")
        self.model.eval()

    def score_rep(self, user_rep_angles, feature_names, core_features, exercise_type):
        return _score_rep_sequence(
            self.model, user_rep_angles, feature_names, core_features,
            exercise_type, self.median_error, self.iqr, self.training_avg_flexion,
            has_attention=True
        )


# ---------------------------------------------------------------------------
# Shared scoring for LSTM-based models
# ---------------------------------------------------------------------------

def _score_rep_sequence(model, user_rep_angles, feature_names, core_features,
                        exercise_type, median_error, iqr, training_avg_flexion,
                        has_attention=False):
    """Score a rep using an LSTM-based VAE. Works with variable-length sequences."""
    # Build the 29-dim embedding per frame (angles + velocities + symmetry + depth)
    # For LSTM models we use the raw angle data directly since that's what the model expects
    T = user_rep_angles.shape[0]

    # Compute velocities
    velocity = np.diff(user_rep_angles, axis=0)  # (T-1, 13)
    angles_trimmed = user_rep_angles[:T - 1]      # (T-1, 13)

    # Symmetry
    knee_sym = (angles_trimmed[:, 2] - angles_trimmed[:, 3]).reshape(-1, 1)
    hip_sym = (angles_trimmed[:, 4] - angles_trimmed[:, 5]).reshape(-1, 1)

    # Simple depth proxy
    depth = np.zeros((T - 1, 1), dtype=np.float32)

    # Build sequence: (T-1, 29)
    sequence = np.concatenate([angles_trimmed, velocity, knee_sym, hip_sym, depth], axis=1)
    sequence = sequence.astype(np.float32)

    # Exercise one-hot
    exercise_oh = _exercise_one_hot(exercise_type)

    # Run through model
    with torch.no_grad():
        x = torch.tensor(sequence).unsqueeze(0)           # (1, T-1, 29)
        exercise_t = torch.tensor(exercise_oh).unsqueeze(0)  # (1, 5)

        if has_attention:
            reconstruction, mu, log_var, attn_weights = model(x, exercise_t)
        else:
            reconstruction, mu, log_var = model(x, exercise_t)

        reconstructed = reconstruction.squeeze(0).numpy()  # (T-1, 29)

    # Per-feature scores (first 13 dims are angles)
    per_feature = []
    for i, name in enumerate(feature_names):
        if i < reconstructed.shape[1]:
            feat_error = float(np.mean((sequence[:, i] - reconstructed[:, i]) ** 2))
            feat_score = sigmoid_calibrate(feat_error, median_error, iqr)
        else:
            feat_score = 0.5
            feat_error = 0.0

        per_feature.append({
            'feature': name,
            'correlation': feat_score,
            'mae_degrees': feat_error,
            'penalty': 1.0,
            'combined_score': feat_score,
            'is_core': name in core_features,
        })

    # Overall
    total_error = float(np.mean((sequence - reconstructed) ** 2))
    overall_similarity = sigmoid_calibrate(total_error, median_error, iqr)

    core_scores = [r['combined_score'] for r in per_feature if r['is_core']]
    core_similarity = float(np.mean(core_scores)) if core_scores else overall_similarity

    # Depth
    depth_result = _depth_analysis(user_rep_angles, training_avg_flexion)

    return {
        'per_feature': per_feature,
        'overall_similarity': overall_similarity,
        'core_similarity': core_similarity,
        **depth_result,
    }
