from Utils.utils.utils import *


# MediaPipe joint indices
HIP_L = 23
KNEE_L = 25
ANKLE_L = 27

HIP_R = 24
KNEE_R = 26
ANKLE_R = 28

SHOULDER_L = 11
ELBOW_L = 13
WRIST_L = 15



def compute_angle_features(landmarks):
    frames, joints, dims = landmarks.shape
    features = []

    for f in range(frames):
        lm = landmarks[f]

        # Example angles
        left_knee = calculate_angle(lm[HIP_L], lm[KNEE_L], lm[ANKLE_L])
        right_knee = calculate_angle(lm[HIP_R], lm[KNEE_R], lm[ANKLE_R])

        left_elbow = calculate_angle(lm[SHOULDER_L], lm[ELBOW_L], lm[WRIST_L])

        # Add more angles if you want a richer embedding

        features.append([
            left_knee,
            right_knee,
            left_elbow,
        ])

    return np.array(features)
