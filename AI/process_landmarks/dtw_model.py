from process_landmarks.create_template import load_template
from process_landmarks.dtw_analysis import compare_rep_to_template


class DTWModel:
    """Wraps existing DTW comparison in the common score_rep() interface."""

    def __init__(self, template_path="templates/front_narrow_template.npz"):
        self.template, self.feature_names, self.core_features = load_template(template_path)

    def score_rep(self, user_rep_angles, feature_names, core_features, exercise_type):
        return compare_rep_to_template(
            user_rep_angles, self.template, feature_names, core_features
        )
