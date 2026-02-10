import os
import numpy as np

from Utils.utils.utils import (
    ANGLE_NAMES,
    compute_angle_features_2d,
    compute_squat_depth,
    smooth_angles,
)


def build_embedding(smooth_angles_data, landmarks):
    """
    Build the full embedding from smoothed angles and raw landmarks.
    All derived features use smoothed angles for consistency.

    Returns: (T-1, D) embedding array and list of feature names.
    """
    velocity = np.diff(smooth_angles_data, axis=0)

    T = velocity.shape[0]
    angles_trimmed = smooth_angles_data[:T]

    # Symmetry: index 2 = left_knee, 3 = right_knee, 4 = left_hip, 5 = right_hip
    knee_symmetry = (angles_trimmed[:, 2] - angles_trimmed[:, 3]).reshape(-1, 1)
    hip_symmetry = (angles_trimmed[:, 4] - angles_trimmed[:, 5]).reshape(-1, 1)

    depth = compute_squat_depth(landmarks)[:T]  # (T, 1)

    embedding = np.concatenate([
        angles_trimmed,     # 13 smoothed angles
        velocity,           # 13 velocity features
        knee_symmetry,      # 1
        hip_symmetry,       # 1
        depth,              # 1
    ], axis=1)

    feature_names = (
        [f"angle_{n}" for n in ANGLE_NAMES] +
        [f"vel_{n}" for n in ANGLE_NAMES] +
        ["knee_symmetry", "hip_symmetry", "squat_depth"]
    )

    return embedding, feature_names


def normalize_embedding(embedding, ref_mean=None, ref_std=None):
    """
    Normalize embedding using reference (pro) statistics.
    If ref_mean/ref_std are None, computes them from the embedding itself.

    Returns: normalized embedding, mean, std
    """
    if ref_mean is None:
        ref_mean = embedding.mean(axis=0)
    if ref_std is None:
        ref_std = embedding.std(axis=0) + 1e-8

    normalized = (embedding - ref_mean) / (ref_std + 1e-8)
    return normalized, ref_mean, ref_std


def create_embedding_from_landmarks(landmarks):
    """
    Full pipeline: landmarks -> angles -> smooth -> embedding.

    Args:
        landmarks: (T, 33, 3) or (T, 33, 4) numpy array of MediaPipe landmarks.

    Returns:
        embedding: (T-1, D) numpy array
        smooth: (T, 13) smoothed angle features
        feature_names: list of feature name strings
    """
    # Use only x,y,z (ignore visibility if present)
    lm = landmarks[:, :, :3] if landmarks.shape[2] > 3 else landmarks

    angles = compute_angle_features_2d(lm)
    smooth = smooth_angles(angles)
    embedding, feature_names = build_embedding(smooth, lm)

    return embedding, smooth, feature_names


def save_embedding(embedding, ref_mean, ref_std, embedding_path, stats_path):
    """Save embedding and normalization stats to disk."""
    os.makedirs(os.path.dirname(embedding_path), exist_ok=True)
    np.save(embedding_path, embedding)
    np.savez(stats_path, mean=ref_mean, std=ref_std)
