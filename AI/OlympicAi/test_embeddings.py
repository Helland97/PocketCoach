if __name__ == "__main__":

    import os
    import numpy as np
    import traceback

    # ============================================================
    # CONFIGURATION - Change these to switch videos / templates
    # ============================================================
    USER_LANDMARK_FILE = "back_angle_narrow_landmarks.npy"
    TEMPLATE_FILE = "front_narrow_template.npz"
    EXERCISE_TYPE = "heavy_squat"

    # ============================================================
    # Available files (for reference)
    # ============================================================
    LANDMARKS_DIR = "AI/MediaPipe_landmarks"
    TEMPLATES_DIR = "AI/templates"

    print("Available landmark files:")
    for f in sorted(os.listdir(LANDMARKS_DIR)):
        marker = "  <-- SELECTED" if f == USER_LANDMARK_FILE else ""
        print(f"  {f}{marker}")

    print(f"\nAvailable template files:")
    for f in sorted(os.listdir(TEMPLATES_DIR)):
        marker = "  <-- SELECTED" if f == TEMPLATE_FILE else ""
        print(f"  {f}{marker}")

    # ============================================================
    # Run pipeline
    # ============================================================
    try:
        from AI.process_landmarks.create_embedding import create_embedding_from_landmarks
        from AI.process_landmarks.create_template import load_template
        from AI.process_landmarks.dtw_analysis import compare_rep_to_template
        from AI.process_landmarks.verdict import generate_feedback, analyze_user_video
        from AI.process_landmarks.exercise_config import EXERCISE_CONFIGS
        from Utils.utils.utils import (
            smooth_angles,
            find_rep_boundaries,
            extract_rep_angles,
            ANGLE_NAMES,
        )

        user_path = os.path.join(LANDMARKS_DIR, USER_LANDMARK_FILE)
        template_path = os.path.join(TEMPLATES_DIR, TEMPLATE_FILE)

        print(f"\n{'='*70}")
        print(f"Loading user landmarks: {user_path}")
        user_landmarks = np.load(user_path)
        print(f"  Shape: {user_landmarks.shape}")

        print(f"\nLoading template: {template_path}")
        template, feature_names, core_features = load_template(template_path)
        print(f"  Template shape: {template.shape}")
        print(f"  Features: {feature_names}")
        print(f"  Core features: {core_features}")

        # --- Step 1: Create embedding ---
        print(f"\n{'='*70}")
        print("Step 1: Creating embedding from user landmarks...")
        embedding, smooth, emb_feature_names = create_embedding_from_landmarks(user_landmarks)
        print(f"  Embedding shape: {embedding.shape}")
        print(f"  Smoothed angles shape: {smooth.shape}")

        # --- Step 2: Segment reps ---
        print(f"\n{'='*70}")
        print(f"Step 2: Detecting reps (exercise_type={EXERCISE_TYPE})...")
        exercise_config = EXERCISE_CONFIGS[EXERCISE_TYPE]
        reps, knee_angle = find_rep_boundaries(smooth, exercise_config)
        reps_data = extract_rep_angles(smooth, reps)
        print(f"  Detected {len(reps_data)} reps")
        for i, rep in enumerate(reps_data):
            print(f"    Rep {i+1}: {rep.shape[0]} frames")

        # --- Step 3: DTW analysis per rep ---
        print(f"\n{'='*70}")
        print("Step 3: Comparing each rep to template (DTW analysis)...")
        for i, rep in enumerate(reps_data):
            result = compare_rep_to_template(rep, template, feature_names, core_features)

            print(f"\n  Rep {i+1}:")
            print(f"    Core similarity:  {result['core_similarity']:.2%}")
            print(f"    Overall similarity: {result['overall_similarity']:.2%}")
            print(f"    Depth: {result['user_flexion']:.1f}° flexion "
                  f"(template: {result['template_flexion']:.1f}°)")
            print(f"    Hit parallel: {'Yes' if result['hit_parallel'] else 'No'}")
            print(f"    Depth score: {result['depth_score']:.0f}/100")

            print(f"\n    {'Feature':<16} {'Corr':>6} {'MAE':>7} {'Score':>7} {'Grade'}")
            print(f"    {'-'*50}")
            for r in result['per_feature']:
                score = r['combined_score']
                if np.isnan(score):
                    grade = "N/A"
                elif score > 0.80:
                    grade = "A"
                elif score > 0.60:
                    grade = "B"
                elif score > 0.40:
                    grade = "C"
                elif score > 0.20:
                    grade = "D"
                else:
                    grade = "F"
                marker = " ***" if r['is_core'] else ""
                print(f"    {r['feature']:<16} {r['correlation']:>6.2f} "
                      f"{r['mae_degrees']:>6.1f}° {score:>7.2%}  {grade}{marker}")

        # --- Step 4: Full verdict ---
        print(f"\n{'='*70}")
        print("Step 4: Full verdict (via analyze_user_video)...")
        verdict = analyze_user_video(user_landmarks, template_path, EXERCISE_TYPE)

        print(f"\n  Total reps: {verdict['n_reps']}")
        print(f"  Average core similarity: {verdict['average_core_similarity']:.2%}")
        print(f"  Average depth score: {verdict['average_depth_score']:.0f}/100")

        for rep in verdict['reps']:
            print(f"\n{rep['feedback']}")

        print(f"\n{'='*70}")
        print("Done!")

    except Exception as e:
        print(f"\nAn error occurred:")
        print(e)
        traceback.print_exc()
