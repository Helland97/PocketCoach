import numpy as np
from scipy import stats as scipy_stats


def compute_rep_stats(rep_angles):
    """
    Convert a variable-length rep into a fixed-size statistics vector.

    Args:
        rep_angles: (T, 13) smoothed angle features for one rep.
                    T can be any length (fast rep = 30 frames, slow rep = 150 frames).

    Returns:
        numpy array of shape (97,):
            - 13 features x 7 stats = 91 values
            - 4 symmetry stats (knee + hip mean/std)
            - 2 depth stats (min left/right knee angles)
    """
    n_features = rep_angles.shape[1]  # 13
    stats = []

    for feature_idx in range(n_features):
        signal = rep_angles[:, feature_idx]
        stats.extend([
            np.mean(signal),
            np.std(signal),
            np.min(signal),
            np.max(signal),
            np.max(signal) - np.min(signal),               # range of motion
            float(scipy_stats.skew(signal)),                # time distribution
            np.percentile(signal, 25),                      # captures descent phase
        ])

    # Symmetry stats: index 2 = left_knee, 3 = right_knee, 4 = left_hip, 5 = right_hip
    knee_sym = rep_angles[:, 2] - rep_angles[:, 3]
    hip_sym = rep_angles[:, 4] - rep_angles[:, 5]
    stats.extend([
        np.mean(knee_sym), np.std(knee_sym),
        np.mean(hip_sym), np.std(hip_sym),
    ])

    # Depth stats: minimum knee angles (left and right)
    stats.extend([
        np.min(rep_angles[:, 2]),
        np.min(rep_angles[:, 3]),
    ])

    return np.array(stats, dtype=np.float32)


# Total stats dimension: 13 * 7 + 4 + 2 = 97
STATS_DIM = 97
