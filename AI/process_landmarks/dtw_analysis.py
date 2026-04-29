import numpy as np
from dtw import dtw

from Utils.utils.utils import inner_to_flexion


def per_feature_dtw_similarity(ref_angles, user_angles, feature_names):
    """
    Run DTW independently on each feature (1D signal).
    After alignment, compute Pearson correlation and mean absolute error.

    Returns list of dicts with per-feature results.
    """
    n_features = ref_angles.shape[1]
    results = []

    for i in range(n_features):
        ref_signal = ref_angles[:, i]
        user_signal = user_angles[:, i]

        alignment = dtw(ref_signal, user_signal)

        idx_r = alignment.index1
        idx_u = alignment.index2

        ref_aligned = ref_signal[idx_r]
        user_aligned = user_signal[idx_u]

        correlation = np.corrcoef(ref_aligned, user_aligned)[0, 1]

        mae_degrees = np.mean(np.abs(ref_aligned - user_aligned))

        results.append({
            'feature': feature_names[i],
            'correlation': correlation,
            'mae_degrees': mae_degrees,
        })

    return results


def compare_rep_to_template(user_rep_angles, template, feature_names, core_features):
    """
    Compare a single user rep to the pro template using per-feature DTW.

    Scoring:
    - Knee angles: penalizes shallower depth, rewards matching or exceeding
    - Other joints: penalizes MAE via exponential decay
    - Both combined with pattern correlation

    Returns dict with per-feature results, similarity scores, and depth analysis.
    """
    results = []

    for i, name in enumerate(feature_names):
        template_signal = template[:, i]
        user_signal = user_rep_angles[:, i]

        alignment = dtw(template_signal, user_signal)

        idx_template = alignment.index1
        idx_user = alignment.index2
        template_aligned = template_signal[idx_template]
        user_aligned = user_signal[idx_user]

        correlation = np.corrcoef(template_aligned, user_aligned)[0, 1]
        if np.isnan(correlation):
            correlation = 0

        mae_degrees = np.mean(np.abs(template_aligned - user_aligned))

        if 'knee' in name:
            template_min = template_signal.min()
            user_min = user_signal.min()

            if user_min <= template_min:
                depth_penalty = 1.0
            else:
                depth_shortfall = user_min - template_min
                depth_penalty = np.exp(-depth_shortfall / 20.0)

            combined_score = correlation * depth_penalty
        else:
            mae_penalty = np.exp(-mae_degrees / 30.0)
            combined_score = correlation * mae_penalty
            depth_penalty = mae_penalty

        results.append({
            'feature': name,
            'correlation': float(correlation),
            'mae_degrees': float(mae_degrees),
            'penalty': float(depth_penalty),
            'combined_score': float(combined_score),
            'is_core': name in core_features
        })

    all_combined = [r['combined_score'] for r in results if not np.isnan(r['combined_score'])]
    core_combined = [r['combined_score'] for r in results if r['is_core'] and not np.isnan(r['combined_score'])]

    # Depth analysis
    template_knee_inner = (template[:, 2].min() + template[:, 3].min()) / 2
    user_knee_inner = (user_rep_angles[:, 2].min() + user_rep_angles[:, 3].min()) / 2

    template_flexion = inner_to_flexion(template_knee_inner)
    user_flexion = inner_to_flexion(user_knee_inner)

    hit_parallel = user_knee_inner <= 90.0

    if user_knee_inner <= template_knee_inner:
        depth_score = 100.0
    else:
        shortfall = user_knee_inner - template_knee_inner
        depth_score = max(0, 100 - shortfall * 2)

    return {
        'per_feature': results,
        'overall_similarity': float(np.mean(all_combined)) if all_combined else 0,
        'core_similarity': float(np.mean(core_combined)) if core_combined else 0,
        'template_flexion': float(template_flexion),
        'user_flexion': float(user_flexion),
        'template_inner': float(template_knee_inner),
        'user_inner': float(user_knee_inner),
        'hit_parallel': bool(hit_parallel),
        'depth_score': float(depth_score),
    }
