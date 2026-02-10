import numpy as np
import mediapipe as mp
from scipy.signal import savgol_filter, find_peaks

# Access PoseLandmark through mediapipe module due to packaging structure
PoseLandmark = mp.solutions.pose.PoseLandmark


# Dictionary of joint indices for easy access
JOINTS = {
    "right_knee": {
        "hip": PoseLandmark.RIGHT_HIP.value,
        "knee": PoseLandmark.RIGHT_KNEE.value,
        "ankle": PoseLandmark.RIGHT_ANKLE.value,
    },
    "left_knee": {
        "hip": PoseLandmark.LEFT_HIP.value,
        "knee": PoseLandmark.LEFT_KNEE.value,
        "ankle": PoseLandmark.LEFT_ANKLE.value,
    },
    # Add more joints as needed
}


def get_joint_coords(landmarks, joint_name):
    """
    Returns the coordinates (x, y, z) for the specified joint.
    Args:
        landmarks: List of pose landmarks from MediaPipe.
        joint_name: Name of the joint as in JOINTS.
    Returns:
        Tuple of (hip, knee, ankle) coordinates for the joint.
    """
    joint = JOINTS[joint_name]
    hip = [landmarks[joint["hip"]].x, landmarks[joint["hip"]].y, landmarks[joint["hip"]].z]
    knee = [landmarks[joint["knee"]].x, landmarks[joint["knee"]].y, landmarks[joint["knee"]].z]
    ankle = [landmarks[joint["ankle"]].x, landmarks[joint["ankle"]].y, landmarks[joint["ankle"]].z]
    return hip, knee, ankle


def calculate_angle(p1, p2, p3):
    """
    Calculate the angle between three points in 2D (x, y) space.
    Args:
        p1, p2, p3: Points in (x, y) format.
    Returns:
        Angle in degrees.
    """
    a = np.array([p1[0] - p2[0], p1[1] - p2[1]])
    b = np.array([p3[0] - p2[0], p3[1] - p2[1]])
    cosine_angle = np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
    # Clamp value to avoid numerical errors
    cosine_angle = np.clip(cosine_angle, -1.0, 1.0)
    angle = np.arccos(cosine_angle)
    return np.degrees(angle)



def calculate_angle_flexion(p1, p2, p3):
    """
    Calculate the angle between three points in 2D (x, y) space.
    Args:
        p1, p2, p3: Points in (x, y) format.
    Returns:
        Angle in degrees.
    """
    a = np.array([p1[0] - p2[0], p1[1] - p2[1]])
    b = np.array([p3[0] - p2[0], p3[1] - p2[1]])
    cosine_angle = np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
    # Clamp value to avoid numerical errors
    cosine_angle = np.clip(cosine_angle, -1.0, 1.0)
    inner_angle = np.degrees(np.arccos(cosine_angle))

    # Convert to flexion angle
    flexion_angle = 180.0 - inner_angle
    return flexion_angle



def calculate_angle_3d(p1, p2, p3):
    """
    Calculate the angle between three points in 3D space.
    Args:
        p1, p2, p3: Points in (x, y, z) format.
    Returns:
        Angle in degrees.
    """
    # Create 3D vectors
    a = np.array([p1[0] - p2[0], p1[1] - p2[1], p1[2] - p2[2]])
    b = np.array([p3[0] - p2[0], p3[1] - p2[1], p3[2] - p2[2]])

    # Compute cosine using dot product formula
    cosine_angle = np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

    # Clamp value to prevent numerical drift outside [-1, 1]
    cosine_angle = np.clip(cosine_angle, -1.0, 1.0)

    # Angle in degrees
    angle = np.arccos(cosine_angle)
    return np.degrees(angle)


# ============================================================
# MediaPipe Joint Indices
# ============================================================
HIP_L = 23
HIP_R = 24
KNEE_L = 25
KNEE_R = 26
ANKLE_L = 27
ANKLE_R = 28
HEEL_L = 29
HEEL_R = 30
TOE_L = 31
TOE_R = 32

SHOULDER_L = 11
SHOULDER_R = 12
ELBOW_L = 13
ELBOW_R = 14
WRIST_L = 15
WRIST_R = 16
PINKY_L = 17
PINKY_R = 18

NOSE = 0

# Feature names for interpretability
ANGLE_NAMES = [
    "left_ankle", "right_ankle",
    "left_knee", "right_knee",
    "left_hip", "right_hip",
    "left_shoulder", "right_shoulder",
    "left_elbow", "right_elbow",
    "left_wrist", "right_wrist",
    "trunk_lean",
]


# ============================================================
# 2D Angle Computation
# ============================================================

def compute_angle_2d(p1, p2, p3):
    """
    Compute angle at p2 using only x,y coordinates (ignoring unreliable z).
    Returns inner angle in degrees.
    """
    a = np.array([p1[0] - p2[0], p1[1] - p2[1]])
    b = np.array([p3[0] - p2[0], p3[1] - p2[1]])

    cos_angle = np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8)
    cos_angle = np.clip(cos_angle, -1.0, 1.0)
    return np.degrees(np.arccos(cos_angle))


def compute_trunk_lean_2d(landmarks):
    """
    Compute trunk lean angle relative to vertical using 2D (x,y only).
    0 = perfectly upright, higher = more forward lean.
    """
    pelvis = (landmarks[:, HIP_L, :2] + landmarks[:, HIP_R, :2]) / 2.0
    neck = (landmarks[:, SHOULDER_L, :2] + landmarks[:, SHOULDER_R, :2]) / 2.0

    torso_vec = neck - pelvis  # (T, 2)
    vertical = np.array([0, -1])

    dot = np.einsum('ij,j->i', torso_vec, vertical)
    norms = np.linalg.norm(torso_vec, axis=1) + 1e-8
    cos_angle = np.clip(dot / norms, -1.0, 1.0)

    return np.degrees(np.arccos(cos_angle))  # (T,)


def compute_angle_features_2d(landmarks):
    """
    Compute joint angles using only x,y coordinates (2D).
    This is MORE ACCURATE than 3D because MediaPipe's z-estimate
    from monocular video is unreliable.

    Returns: (T, 13) array -- 12 joint angles + trunk lean
    """
    T = landmarks.shape[0]
    features = []

    for f in range(T):
        lm = landmarks[f]

        left_ankle    = compute_angle_2d(lm[KNEE_L],     lm[ANKLE_L],    lm[TOE_L])
        right_ankle   = compute_angle_2d(lm[KNEE_R],     lm[ANKLE_R],    lm[TOE_R])
        left_knee     = compute_angle_2d(lm[HIP_L],      lm[KNEE_L],     lm[ANKLE_L])
        right_knee    = compute_angle_2d(lm[HIP_R],      lm[KNEE_R],     lm[ANKLE_R])
        left_hip      = compute_angle_2d(lm[SHOULDER_L], lm[HIP_L],      lm[KNEE_L])
        right_hip     = compute_angle_2d(lm[SHOULDER_R], lm[HIP_R],      lm[KNEE_R])
        left_shoulder = compute_angle_2d(lm[ELBOW_L],    lm[SHOULDER_L], lm[HIP_L])
        right_shoulder= compute_angle_2d(lm[ELBOW_R],    lm[SHOULDER_R], lm[HIP_R])
        left_elbow    = compute_angle_2d(lm[SHOULDER_L], lm[ELBOW_L],    lm[WRIST_L])
        right_elbow   = compute_angle_2d(lm[SHOULDER_R], lm[ELBOW_R],    lm[WRIST_R])
        left_wrist    = compute_angle_2d(lm[ELBOW_L],    lm[WRIST_L],    lm[PINKY_L])
        right_wrist   = compute_angle_2d(lm[ELBOW_R],    lm[WRIST_R],    lm[PINKY_R])

        features.append([
            left_ankle, right_ankle,
            left_knee, right_knee,
            left_hip, right_hip,
            left_shoulder, right_shoulder,
            left_elbow, right_elbow,
            left_wrist, right_wrist,
        ])

    angles = np.array(features)  # (T, 12)
    trunk_lean = compute_trunk_lean_2d(landmarks)  # (T,)
    angles = np.column_stack([angles, trunk_lean])  # (T, 13)

    return angles


def inner_to_flexion(inner_angle):
    """
    Convert MediaPipe inner knee angle to flexion angle.
    - Inner angle: ~180 when standing, ~90 at parallel
    - Flexion angle: 0 when standing, 90 at parallel, >90 below parallel
    """
    return 180.0 - inner_angle


# ============================================================
# Signal Processing
# ============================================================

def smooth_angles(angles, window=11, polyorder=3):
    """Savitzky-Golay filter. Adjust window to video FPS if needed."""
    w = min(window, angles.shape[0])
    if w % 2 == 0:
        w -= 1  # must be odd
    return savgol_filter(angles, window_length=w, polyorder=polyorder, axis=0)


def resample_to_length(signal, target_length):
    """
    Resample a 1D or 2D signal to a target length using linear interpolation.
    signal: (T,) or (T, D)

    Only needed for:
    - 'average' template method (must match lengths before averaging)
    - Visualization (plotting signals of different lengths side by side)
    NOT needed before DTW (DTW handles different lengths natively).
    """
    if signal.ndim == 1:
        signal = signal.reshape(-1, 1)

    T, D = signal.shape
    x_old = np.linspace(0, 1, T)
    x_new = np.linspace(0, 1, target_length)

    resampled = np.zeros((target_length, D))
    for d in range(D):
        resampled[:, d] = np.interp(x_new, x_old, signal[:, d])

    return resampled.squeeze() if D == 1 else resampled


# ============================================================
# Squat Depth & Rep Segmentation
# ============================================================

def compute_squat_depth(landmarks):
    """
    Hip Y minus Knee Y (normalized by pelvis-neck distance).
    Positive = hips above knees. Negative = hips below knees (deep squat).
    """
    pelvis = (landmarks[:, HIP_L, :] + landmarks[:, HIP_R, :]) / 2.0
    neck = (landmarks[:, SHOULDER_L, :] + landmarks[:, SHOULDER_R, :]) / 2.0

    scale = np.linalg.norm(neck - pelvis, axis=1, keepdims=True) + 1e-8

    hip_y = pelvis[:, 1:2]
    knee_y = ((landmarks[:, KNEE_L, 1:2] + landmarks[:, KNEE_R, 1:2]) / 2.0)

    depth = (hip_y - knee_y) / scale
    return depth  # (T, 1)


def estimate_adaptive_params(smooth_angles, fps=30):
    """
    Automatically estimate rep detection parameters from the signal.

    Looks at the knee angle signal to estimate:
    - Average rep duration (for min_distance)
    - Average angle drop (for prominence)
    """
    knee_angle = (smooth_angles[:, 2] + smooth_angles[:, 3]) / 2.0

    bottoms, props = find_peaks(-knee_angle, distance=15, prominence=5)

    if len(bottoms) < 2:
        print("  Adaptive: Not enough peaks found, using heavy_squat defaults")
        return 100, 25

    avg_distance = np.mean(np.diff(bottoms))

    min_distance = int(avg_distance * 0.6)

    median_prominence = np.median(props['prominences'])
    prominence = max(5, median_prominence * 0.5)

    print(f"  Adaptive: detected ~{len(bottoms)} potential reps")
    print(f"  Adaptive: avg rep distance = {avg_distance:.0f} frames ({avg_distance/fps:.1f}s)")
    print(f"  Adaptive: min_distance = {min_distance}, prominence = {prominence:.1f}")

    return min_distance, prominence


def find_rep_boundaries(smooth_angles, exercise_config):
    """
    Find squat rep boundaries by detecting knee angle minima (bottom of squat).
    Uses average of left + right knee for a more stable signal.

    Args:
        smooth_angles: (T, D) smoothed angle features
        exercise_config: dict with 'min_distance', 'prominence', and 'description' keys.
                         For adaptive mode, only 'description' is needed.

    Returns:
        reps: list of (start, end) frame indices for each rep
        knee_angle: the averaged knee angle signal used for detection
    """
    description = exercise_config.get('description', '')
    print(f"  Exercise config: {description}")

    if 'min_distance' not in exercise_config:
        # Adaptive mode
        min_distance, prominence = estimate_adaptive_params(smooth_angles)
    else:
        min_distance = exercise_config['min_distance']
        prominence = exercise_config['prominence']

    print(f"  Parameters: min_distance={min_distance}, prominence={prominence}")

    knee_angle = (smooth_angles[:, 2] + smooth_angles[:, 3]) / 2.0

    bottoms, properties = find_peaks(-knee_angle, distance=min_distance, prominence=prominence)

    print(f"  Detected {len(bottoms)} squat bottoms at frames: {bottoms}")
    print(f"  Knee angles at bottoms: {[f'{knee_angle[b]:.1f}' for b in bottoms]}")

    if len(bottoms) < 1:
        print("  WARNING: Could not detect any reps. Using full video.")
        return [(0, len(knee_angle) - 1)], knee_angle

    boundaries = [0]
    for i in range(len(bottoms) - 1):
        mid = (bottoms[i] + bottoms[i+1]) // 2
        boundaries.append(mid)
    boundaries.append(len(knee_angle) - 1)

    reps = []
    for i in range(len(boundaries) - 1):
        reps.append((boundaries[i], boundaries[i+1]))

    return reps, knee_angle


def extract_rep_angles(smooth_angles, reps):
    """Extract angle data for each rep as a list of arrays."""
    rep_data = []
    for start, end in reps:
        rep_angles = smooth_angles[start:end+1]
        if len(rep_angles) >= 5:  # minimum viable rep length
            rep_data.append(rep_angles)
    return rep_data


def score_rep_quality(rep_angles, core_feature_indices):
    """
    Score a rep's quality based on smoothness and range of motion.
    Higher score = better rep (smoother movement, good range of motion).
    Only used for 'best' template method.
    """
    velocity = np.diff(rep_angles, axis=0)
    smoothness = -np.mean(np.var(velocity[:, core_feature_indices], axis=0))

    rom = np.mean(np.ptp(rep_angles[:, core_feature_indices], axis=0))

    score = smoothness * 0.3 + rom * 0.7
    return score
