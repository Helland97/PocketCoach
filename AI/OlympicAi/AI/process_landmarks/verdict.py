import numpy as np

from Utils.utils.utils import (
    ANGLE_NAMES,
    compute_angle_features_2d,
    smooth_angles,
    find_rep_boundaries,
    extract_rep_angles,
)
from AI.process_landmarks.exercise_config import EXERCISE_CONFIGS, CORE_FEATURES
from AI.process_landmarks.create_template import load_template
from AI.process_landmarks.create_embedding import build_embedding
from AI.process_landmarks.dtw_analysis import compare_rep_to_template


def generate_feedback(rep_result, rep_number):
    """
    Generate actionable feedback based on rep comparison results.
    """
    feedback = []
    feedback.append(f"REP {rep_number} ANALYSIS")
    feedback.append("=" * 40)

    core_score = rep_result['core_similarity']

    if core_score > 0.95:
        overall_grade = "Excellent!"
    elif core_score > 0.90:
        overall_grade = "Great form!"
    elif core_score > 0.80:
        overall_grade = "Good, minor adjustments needed"
    elif core_score > 0.70:
        overall_grade = "Needs improvement"
    else:
        overall_grade = "Significant form issues"

    feedback.append(f"Overall: {overall_grade} (score: {core_score:.2%})")
    feedback.append("")

    problems = []
    for r in rep_result['per_feature']:
        if not r['is_core']:
            continue

        corr = r['correlation']
        mae = r['mae_degrees']
        feature = r['feature']

        if corr < 0.85 or mae > 10:
            problems.append({
                'feature': feature,
                'correlation': corr,
                'mae': mae
            })

    if problems:
        feedback.append("Areas to improve:")
        for p in sorted(problems, key=lambda x: x['correlation']):
            feat = p['feature']

            if 'knee' in feat:
                if p['mae'] > 15:
                    advice = "Knee angle differs significantly - check squat depth"
                else:
                    advice = "Knee tracking slightly off - focus on knee-over-toe alignment"
            elif 'hip' in feat:
                advice = "Hip hinge pattern differs - practice hip mobility"
            elif 'trunk_lean' in feat:
                advice = "Trunk angle differs - focus on keeping chest up"
            else:
                advice = "Movement pattern differs from pro"

            feedback.append(f"  - {feat}: {advice} (MAE: {p['mae']:.1f} degrees)")
    else:
        feedback.append("All core movements match the pro template well!")

    return "\n".join(feedback)


def analyze_user_video(landmarks, template_path, exercise_type='heavy_squat'):
    """
    Full analysis pipeline: user landmarks -> per-rep comparison -> verdict.

    Args:
        landmarks: (T, 33, 3) or (T, 33, 4) numpy array of user MediaPipe landmarks.
        template_path: path to the saved .npz template file.
        exercise_type: key into EXERCISE_CONFIGS for rep detection.

    Returns:
        dict with n_reps, average_score, and per-rep results + feedback.
    """
    template, feature_names, core_features = load_template(template_path)

    # Use only x,y,z (ignore visibility if present)
    lm = landmarks[:, :, :3] if landmarks.shape[2] > 3 else landmarks

    angles = compute_angle_features_2d(lm)
    smooth = smooth_angles(angles)

    # Build the biomechanical embedding (angles + velocity + symmetry + depth)
    embedding, emb_feature_names = build_embedding(smooth, lm)

    exercise_config = EXERCISE_CONFIGS[exercise_type]
    reps, _ = find_rep_boundaries(smooth, exercise_config)
    reps_data = extract_rep_angles(smooth, reps)

    results = []
    for i, rep in enumerate(reps_data):
        result = compare_rep_to_template(rep, template, feature_names, core_features)
        feedback = generate_feedback(result, i + 1)
        results.append({
            'rep_number': i + 1,
            'core_similarity': result['core_similarity'],
            'overall_similarity': result['overall_similarity'],
            'depth_score': result['depth_score'],
            'user_flexion': result['user_flexion'],
            'template_flexion': result['template_flexion'],
            'hit_parallel': result['hit_parallel'],
            'per_feature': result['per_feature'],
            'feedback': feedback,
        })

    avg_core = np.mean([r['core_similarity'] for r in results]) if results else 0
    avg_depth = np.mean([r['depth_score'] for r in results]) if results else 0

    return {
        'n_reps': len(results),
        'average_core_similarity': float(avg_core),
        'average_depth_score': float(avg_depth),
        'reps': results,
        'embedding': embedding,
        'embedding_feature_names': emb_feature_names,
    }
