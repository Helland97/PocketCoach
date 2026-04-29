"""
Offline training script for VAE models.

Usage:
    cd AI
    python -m mlp.train_vae --model stats_vae
    python -m mlp.train_vae --model lstm_vae
    python -m mlp.train_vae --model lstm_attention_vae

Training data should be placed in training_data/{exercise}/ as .npy landmark files.
Each .npy file should contain (T, 33, 4) MediaPipe landmarks from a good-form video.
"""

import os
import json
import argparse
import numpy as np
import torch
from torch.utils.data import DataLoader, TensorDataset

from Utils.utils.utils import (
    compute_angle_features_2d,
    smooth_angles,
    find_rep_boundaries,
    extract_rep_angles,
)
from process_landmarks.exercise_config import EXERCISE_CONFIGS, EXERCISE_INDEX
from mlp.feature_stats import compute_rep_stats
from mlp.model import StatsVAE, LSTMVAE, LSTMAttentionVAE, vae_loss

TRAINING_DATA_DIR = "training_data"
MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")


def load_training_reps():
    """
    Load all landmark files, extract reps, return per-rep data.

    Returns:
        List of dicts: {
            'angles': (T, 13) smoothed angles for this rep,
            'exercise': exercise name string,
            'exercise_idx': int index for one-hot,
        }
    """
    all_reps = []

    for exercise_dir in os.listdir(TRAINING_DATA_DIR):
        exercise_path = os.path.join(TRAINING_DATA_DIR, exercise_dir)
        if not os.path.isdir(exercise_path):
            continue

        exercise_idx = EXERCISE_INDEX.get(exercise_dir)
        if exercise_idx is None:
            print(f"  Skipping unknown exercise: {exercise_dir}")
            continue

        # Determine exercise config for rep detection
        if 'squat' in exercise_dir:
            config_key = 'heavy_squat'
        else:
            config_key = 'adaptive'
        exercise_config = EXERCISE_CONFIGS.get(config_key, EXERCISE_CONFIGS['heavy_squat'])

        npy_files = [f for f in os.listdir(exercise_path) if f.endswith('.npy')]
        print(f"  {exercise_dir}: {len(npy_files)} landmark files")

        for fname in npy_files:
            fpath = os.path.join(exercise_path, fname)
            landmarks = np.load(fpath)
            lm = landmarks[:, :, :3] if landmarks.shape[2] > 3 else landmarks

            angles = compute_angle_features_2d(lm)
            smooth = smooth_angles(angles)

            reps, _ = find_rep_boundaries(smooth, exercise_config)
            reps_data = extract_rep_angles(smooth, reps)

            for rep_angles in reps_data:
                all_reps.append({
                    'angles': rep_angles,
                    'exercise': exercise_dir,
                    'exercise_idx': exercise_idx,
                })

        print(f"  {exercise_dir}: {sum(1 for r in all_reps if r['exercise'] == exercise_dir)} reps extracted")

    return all_reps


def train_stats_vae(reps, epochs=200, lr=1e-3, batch_size=32, beta=0.5):
    """Train the Summary Statistics VAE."""
    print("\n=== Training Summary Statistics VAE ===")

    # Compute stats for each rep
    stats_list = []
    exercise_indices = []
    for rep in reps:
        stats = compute_rep_stats(rep['angles'])
        stats_list.append(stats)
        exercise_indices.append(rep['exercise_idx'])

    stats_array = np.array(stats_list, dtype=np.float32)
    exercise_array = np.array(exercise_indices, dtype=np.int64)

    # Normalize
    mean = stats_array.mean(axis=0)
    std = stats_array.std(axis=0) + 1e-8
    normalized = (stats_array - mean) / std

    # One-hot encode exercises
    n_exercises = len(EXERCISE_INDEX)
    exercise_oh = np.zeros((len(exercise_array), n_exercises), dtype=np.float32)
    for i, idx in enumerate(exercise_array):
        exercise_oh[i, idx] = 1.0

    # DataLoader
    dataset = TensorDataset(
        torch.tensor(normalized),
        torch.tensor(exercise_oh),
    )
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

    # Model
    model = StatsVAE()
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)

    # Training loop
    model.train()
    for epoch in range(epochs):
        total_loss = 0
        for batch_stats, batch_exercise in loader:
            reconstruction, mu, log_var = model(batch_stats, batch_exercise)
            loss, recon_loss, kl_loss = vae_loss(reconstruction, batch_stats, mu, log_var, beta)

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            total_loss += loss.item()

        if (epoch + 1) % 20 == 0:
            avg_loss = total_loss / len(loader)
            print(f"  Epoch {epoch+1}/{epochs} — loss: {avg_loss:.6f}")

    # Calibrate: compute reconstruction errors on training set
    model.eval()
    errors = []
    with torch.no_grad():
        for i in range(len(normalized)):
            s = torch.tensor(normalized[i]).unsqueeze(0)
            e = torch.tensor(exercise_oh[i]).unsqueeze(0)
            recon, _, _ = model(s, e)
            error = float(((s - recon) ** 2).mean())
            errors.append(error)

    errors = np.array(errors)
    median_error = float(np.median(errors))
    iqr = float(np.percentile(errors, 75) - np.percentile(errors, 25))

    # Compute average flexion from training data
    all_flexions = []
    for rep in reps:
        knee_inner = (rep['angles'][:, 2].min() + rep['angles'][:, 3].min()) / 2
        all_flexions.append(180.0 - knee_inner)
    training_avg_flexion = float(np.mean(all_flexions)) if all_flexions else 90.0

    # Save
    os.makedirs(MODELS_DIR, exist_ok=True)
    torch.save(model.state_dict(), os.path.join(MODELS_DIR, "stats_vae.pt"))
    np.savez(os.path.join(MODELS_DIR, "norm_stats.npz"), mean=mean, std=std)
    with open(os.path.join(MODELS_DIR, "config.json"), "w") as f:
        json.dump({
            "median_error": median_error,
            "iqr": iqr,
            "training_avg_flexion": training_avg_flexion,
            "n_training_reps": len(reps),
            "model_type": "stats_vae",
        }, f, indent=2)

    print(f"\n  Saved model to {MODELS_DIR}/")
    print(f"  Training reps: {len(reps)}")
    print(f"  Median error: {median_error:.6f}, IQR: {iqr:.6f}")
    print(f"  Training avg flexion: {training_avg_flexion:.1f} degrees")


def train_lstm_vae(reps, model_type="lstm_vae", epochs=200, lr=1e-3, beta=0.5):
    """Train LSTM VAE or LSTM+Attention VAE."""
    use_attention = (model_type == "lstm_attention_vae")
    print(f"\n=== Training {'LSTM+Attention' if use_attention else 'LSTM'} VAE ===")

    # Build sequences: (T-1, 29) per rep
    sequences = []
    exercise_indices = []
    for rep in reps:
        angles = rep['angles']
        T = angles.shape[0]
        velocity = np.diff(angles, axis=0)
        angles_trim = angles[:T - 1]
        knee_sym = (angles_trim[:, 2] - angles_trim[:, 3]).reshape(-1, 1)
        hip_sym = (angles_trim[:, 4] - angles_trim[:, 5]).reshape(-1, 1)
        depth = np.zeros((T - 1, 1), dtype=np.float32)
        seq = np.concatenate([angles_trim, velocity, knee_sym, hip_sym, depth], axis=1).astype(np.float32)
        sequences.append(seq)
        exercise_indices.append(rep['exercise_idx'])

    # Pad to max length for batching
    max_len = max(s.shape[0] for s in sequences)
    n_features = sequences[0].shape[1]  # 29
    padded = np.zeros((len(sequences), max_len, n_features), dtype=np.float32)
    lengths = []
    for i, seq in enumerate(sequences):
        padded[i, :seq.shape[0], :] = seq
        lengths.append(seq.shape[0])

    # One-hot
    n_exercises = len(EXERCISE_INDEX)
    exercise_oh = np.zeros((len(exercise_indices), n_exercises), dtype=np.float32)
    for i, idx in enumerate(exercise_indices):
        exercise_oh[i, idx] = 1.0

    # Model
    if use_attention:
        model = LSTMAttentionVAE()
        save_name = "lstm_attention_vae.pt"
    else:
        model = LSTMVAE()
        save_name = "lstm_vae.pt"

    optimizer = torch.optim.Adam(model.parameters(), lr=lr)

    # Simple training (full batch for small datasets, mini-batch for larger)
    padded_t = torch.tensor(padded)
    exercise_t = torch.tensor(exercise_oh)

    model.train()
    for epoch in range(epochs):
        if use_attention:
            reconstruction, mu, log_var, _ = model(padded_t, exercise_t)
        else:
            reconstruction, mu, log_var = model(padded_t, exercise_t)

        loss, recon_loss, kl_loss = vae_loss(reconstruction, padded_t, mu, log_var, beta)

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        if (epoch + 1) % 20 == 0:
            print(f"  Epoch {epoch+1}/{epochs} — loss: {loss.item():.6f} "
                  f"(recon: {recon_loss.item():.6f}, kl: {kl_loss.item():.6f})")

    # Calibrate
    model.eval()
    errors = []
    with torch.no_grad():
        for i in range(len(sequences)):
            x = torch.tensor(sequences[i]).unsqueeze(0)
            e = torch.tensor(exercise_oh[i]).unsqueeze(0)
            if use_attention:
                recon, _, _, _ = model(x, e)
            else:
                recon, _, _ = model(x, e)
            error = float(((x - recon) ** 2).mean())
            errors.append(error)

    errors = np.array(errors)
    median_error = float(np.median(errors))
    iqr = float(np.percentile(errors, 75) - np.percentile(errors, 25))

    all_flexions = []
    for rep in reps:
        knee_inner = (rep['angles'][:, 2].min() + rep['angles'][:, 3].min()) / 2
        all_flexions.append(180.0 - knee_inner)
    training_avg_flexion = float(np.mean(all_flexions)) if all_flexions else 90.0

    # Save
    os.makedirs(MODELS_DIR, exist_ok=True)
    torch.save(model.state_dict(), os.path.join(MODELS_DIR, save_name))
    with open(os.path.join(MODELS_DIR, "config.json"), "w") as f:
        json.dump({
            "median_error": median_error,
            "iqr": iqr,
            "training_avg_flexion": training_avg_flexion,
            "n_training_reps": len(reps),
            "model_type": model_type,
        }, f, indent=2)

    print(f"\n  Saved model to {MODELS_DIR}/{save_name}")
    print(f"  Training reps: {len(reps)}")
    print(f"  Median error: {median_error:.6f}, IQR: {iqr:.6f}")


def main():
    parser = argparse.ArgumentParser(description="Train VAE models for form analysis")
    parser.add_argument("--model", choices=["stats_vae", "lstm_vae", "lstm_attention_vae"],
                        default="stats_vae", help="Which model to train")
    parser.add_argument("--epochs", type=int, default=200)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--beta", type=float, default=0.5, help="KL divergence weight")
    args = parser.parse_args()

    print("Loading training data...")
    reps = load_training_reps()

    if not reps:
        print("\nNo training data found!")
        print(f"Place .npy landmark files in {TRAINING_DATA_DIR}/{{exercise}}/")
        print(f"Exercise folders should be named: {list(EXERCISE_INDEX.keys())}")
        return

    print(f"\nTotal training reps: {len(reps)}")

    if args.model == "stats_vae":
        train_stats_vae(reps, epochs=args.epochs, lr=args.lr, beta=args.beta)
    elif args.model in ("lstm_vae", "lstm_attention_vae"):
        train_lstm_vae(reps, model_type=args.model, epochs=args.epochs, lr=args.lr, beta=args.beta)


if __name__ == "__main__":
    main()
