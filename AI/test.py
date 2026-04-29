if __name__ == "__main__":


    from MediaPipe import MediaPipeVideoProcessor

    try:
        import os
        import traceback
        import numpy as np

        # ============================================================
        # CONFIGURATION
        # ============================================================
        input_video = "videos/back_angle_narrow.mp4"
        output_video = "back_angle_narrow.mp4"
        TEMPLATE_FILE = "front_narrow_template.npz"
        EXERCISE_TYPE = "heavy_squat"

        # ============================================================
        # Step 1: Process video with MediaPipe (skeleton + landmarks)
        # ============================================================
        processor = MediaPipeVideoProcessor()
        processor.process_video(input_video, output_video, all_landmarks=False, calculate_angle=True)
        print("Processing complete. Check:", output_video)

        # ============================================================
        # Step 2: Load the generated landmarks and run analysis
        # ============================================================
        from process_landmarks.create_embedding import create_embedding_from_landmarks
        from process_landmarks.create_template import load_template
        from process_landmarks.dtw_analysis import compare_rep_to_template
        from process_landmarks.verdict import analyze_user_video
        from process_landmarks.exercise_config import EXERCISE_CONFIGS
        from Utils.utils.utils import (
            find_rep_boundaries,
            extract_rep_angles,
        )

        # Derive landmarks path (same logic as MediaPipe.py)
        base_name = os.path.splitext(os.path.basename(output_video))[0]
        landmarks_path = os.path.join("MediaPipe_landmarks", base_name + "_landmarks.npy")
        template_path = os.path.join("templates", TEMPLATE_FILE)

        print(f"\n{'='*70}")
        print(f"Loading landmarks: {landmarks_path}")
        user_landmarks = np.load(landmarks_path)
        print(f"  Shape: {user_landmarks.shape}")

        print(f"Loading template: {template_path}")
        template, feature_names, core_features = load_template(template_path)
        print(f"  Template shape: {template.shape}")

        # Create embedding
        print(f"\n{'='*70}")
        print("Creating embedding from landmarks...")
        embedding, smooth, _ = create_embedding_from_landmarks(user_landmarks)
        print(f"  Embedding shape: {embedding.shape}")

        # Segment reps
        exercise_config = EXERCISE_CONFIGS[EXERCISE_TYPE]
        reps, knee_angle = find_rep_boundaries(smooth, exercise_config)
        reps_data = extract_rep_angles(smooth, reps)
        print(f"  Detected {len(reps_data)} reps")

        # ============================================================
        # Step 3: DTW analysis per rep
        # ============================================================
        print(f"\n{'='*70}")
        print("DTW ANALYSIS - Comparing each rep to template")
        print(f"{'='*70}")

        for i, rep in enumerate(reps_data):
            result = compare_rep_to_template(rep, template, feature_names, core_features)

            print(f"\nRep {i+1} ({rep.shape[0]} frames):")
            print(f"  Core similarity:    {result['core_similarity']:.2%}")
            print(f"  Overall similarity: {result['overall_similarity']:.2%}")
            print(f"  Depth: {result['user_flexion']:.1f} flexion "
                  f"(template: {result['template_flexion']:.1f})")
            print(f"  Hit parallel: {'Yes' if result['hit_parallel'] else 'No'}")
            print(f"  Depth score: {result['depth_score']:.0f}/100")

            print(f"\n  {'Feature':<16} {'Corr':>6} {'MAE':>7} {'Score':>7} {'Grade'}")
            print(f"  {'-'*50}")
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
                print(f"  {r['feature']:<16} {r['correlation']:>6.2f} "
                      f"{r['mae_degrees']:>6.1f} {score:>7.2%}  {grade}{marker}")

        # ============================================================
        # Step 4: Full verdict
        # ============================================================
        print(f"\n{'='*70}")
        print("VERDICT")
        print(f"{'='*70}")

        verdict = analyze_user_video(user_landmarks, template_path, EXERCISE_TYPE)

        print(f"\nTotal reps: {verdict['n_reps']}")
        print(f"Average core similarity: {verdict['average_core_similarity']:.2%}")
        print(f"Average depth score: {verdict['average_depth_score']:.0f}/100")

        for rep in verdict['reps']:
            print(f"\n{rep['feedback']}")

        print(f"\n{'='*70}")
        print("Done!")

    except Exception as e:
        print("An error occurred during processing:")
        print(e)
        traceback.print_exc()
