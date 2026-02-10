EXERCISE_CONFIGS = {
    'heavy_squat': {
        'min_distance': 100,   # ~3.3s at 30fps - heavy squats are slow
        'prominence': 25,      # large angle change required
        'description': 'Heavy barbell squats (slow, controlled reps)'
    },
    'bodyweight_squat': {
        'min_distance': 45,    # ~1.5s at 30fps - faster reps
        'prominence': 15,      # smaller range of motion possible
        'description': 'Bodyweight or goblet squats (moderate speed)'
    },
    'jump_squat': {
        'min_distance': 25,    # ~0.8s at 30fps - explosive reps
        'prominence': 10,      # quick, shallow dips count
        'description': 'Jump squats or plyometric squats (fast, explosive)'
    },
    'adaptive': {
        'description': 'Auto-detect tempo from the knee angle signal'
        # min_distance and prominence computed dynamically
    }
}

# Core features per exercise type (which joints matter most for comparison)
CORE_FEATURES = {
    'squat': ['left_knee', 'right_knee', 'left_hip', 'right_hip', 'trunk_lean'],
}
