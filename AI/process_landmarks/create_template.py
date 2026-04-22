import os
import numpy as np

from Utils.utils.utils import (
    ANGLE_NAMES,
    resample_to_length,
    score_rep_quality,
    find_rep_boundaries,
    extract_rep_angles,
    compute_angle_features_2d,
    smooth_angles,
)
from process_landmarks.exercise_config import EXERCISE_CONFIGS, CORE_FEATURES


def create_template_rep(pro_reps_angles, target_length=100, method='average',
                        core_feature_indices=None):
    """
    Create a template rep from pro video reps.

    For 'first' and 'best': returns the raw rep data (no resampling).
    For 'average': resamples all reps to target_length, then averages.

    Args:
        pro_reps_angles: list of (T_i, D) arrays, one per rep
        target_length: number of frames in the template (only used for 'average')
        method: 'average', 'first', or 'best'
        core_feature_indices: indices of core features (for 'best' method)

    Returns:
        template: (T, D) template rep
        info: dict with metadata
    """
    if len(pro_reps_angles) == 0:
        raise ValueError("No pro reps provided")

    n_features = pro_reps_angles[0].shape[1]
    info = {'method': method, 'n_reps_available': len(pro_reps_angles)}

    if method == 'first':
        template = pro_reps_angles[0]
        info['rep_used'] = 1
        print(f"Template created from FIRST rep (rep #1, {template.shape[0]} frames)")

    elif method == 'best':
        if core_feature_indices is None:
            core_feature_indices = list(range(n_features))

        scores = []
        for i, rep in enumerate(pro_reps_angles):
            score = score_rep_quality(rep, core_feature_indices)
            scores.append(score)
            print(f"  Rep {i+1} quality score: {score:.4f}")

        best_idx = np.argmax(scores)
        template = pro_reps_angles[best_idx]
        info['rep_used'] = best_idx + 1
        info['rep_scores'] = scores
        print(f"Template created from BEST rep (rep #{best_idx + 1}, {template.shape[0]} frames)")

    elif method == 'average':
        resampled_reps = []
        for rep in pro_reps_angles:
            resampled = resample_to_length(rep, target_length)
            resampled_reps.append(resampled)

        stacked = np.stack(resampled_reps, axis=0)  # (n_reps, target_length, D)
        template = np.mean(stacked, axis=0)  # (target_length, D)
        info['n_reps_averaged'] = len(pro_reps_angles)
        print(f"Template created by AVERAGING {len(pro_reps_angles)} reps "
              f"(resampled to {target_length} frames)")

    else:
        raise ValueError(f"Unknown method: {method}. Use 'average', 'first', or 'best'")

    print(f"Template shape: {template.shape}")
    return template, info


def create_template_from_landmarks(landmarks, exercise_type='heavy_squat',
                                   method='first', target_length=100,
                                   core_features_list=None):
    """
    Full pipeline: landmarks -> angles -> smooth -> segment reps -> create template.

    Args:
        landmarks: (T, 33, 3) or (T, 33, 4) numpy array
        exercise_type: key into EXERCISE_CONFIGS
        method: 'average', 'first', or 'best'
        target_length: frames for 'average' method
        core_features_list: list of feature name strings for 'best' scoring

    Returns:
        template: (T, D) template rep
        info: dict with metadata
    """
    lm = landmarks[:, :, :3] if landmarks.shape[2] > 3 else landmarks

    angles = compute_angle_features_2d(lm)
    smooth = smooth_angles(angles)

    exercise_config = EXERCISE_CONFIGS[exercise_type]
    reps, _ = find_rep_boundaries(smooth, exercise_config)
    reps_data = extract_rep_angles(smooth, reps)

    if core_features_list is None:
        core_features_list = CORE_FEATURES.get('squat', [])

    core_indices = [i for i, n in enumerate(ANGLE_NAMES) if n in core_features_list]

    template, info = create_template_rep(
        reps_data,
        target_length=target_length,
        method=method,
        core_feature_indices=core_indices,
    )
    return template, info


def save_template(template, template_info, save_path, ref_name,
                  exercise='squat', core_features_list=None):
    """Save template to disk as .npz file."""
    os.makedirs(os.path.dirname(save_path), exist_ok=True)

    if core_features_list is None:
        core_features_list = CORE_FEATURES.get('squat', [])

    template_data = {
        'template': template,
        'feature_names': ANGLE_NAMES,
        'core_features': core_features_list,
        'template_length': template.shape[0],
        'exercise': exercise,
        'source_video': ref_name,
        'creation_method': template_info['method'],
        'n_reps_available': template_info['n_reps_available'],
    }

    if template_info['method'] == 'average':
        template_data['n_reps_averaged'] = template_info.get('n_reps_averaged', 0)
    elif template_info['method'] in ['first', 'best']:
        template_data['rep_used'] = template_info.get('rep_used', 1)
    if 'rep_scores' in template_info:
        template_data['rep_scores'] = template_info['rep_scores']

    np.savez(save_path, **template_data)
    print(f"Template saved to {save_path}")


def load_template(template_path):
    """
    Load a saved template from disk.

    Returns:
        template: (T, D) numpy array
        feature_names: list of strings
        core_features: list of strings
    """
    data = np.load(template_path, allow_pickle=True)
    template = data['template']
    feature_names = list(data['feature_names'])
    core_features = list(data['core_features'])
    return template, feature_names, core_features
