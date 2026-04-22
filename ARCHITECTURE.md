# AI Spotter - Architecture & Codebase Documentation

Deep documentation of every file, folder, and module in the AI Spotter project.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Root Directory](#root-directory)
3. [Frontend (`frontend/`)](#frontend)
4. [.NET API Gateway (`AI/backend/`)](#net-api-gateway)
5. [Python AI Backend (`AI/`)](#python-ai-backend)
6. [AI Processing Pipeline (`AI/`)](#ai-processing-pipeline)
7. [Utilities (`AI/Utils/`)](#utilities)
8. [Data Files](#data-files)
9. [Docker Infrastructure](#docker-infrastructure)
10. [Request Flow](#request-flow)
11. [Data Flow & Pipeline](#data-flow--pipeline)

---

## Project Overview

AI Spotter is a full-stack web application for AI-powered exercise form analysis. A user uploads a video of themselves performing a lift. The system uses MediaPipe pose estimation to extract body landmarks, then compares the user's movement pattern against a professional reference template using Dynamic Time Warping (DTW). The result is a per-rep grade with actionable coaching feedback.

### Three-Service Architecture

| Service | Language | Framework | Port | Role |
|---------|----------|-----------|------|------|
| Frontend | TypeScript | React 19 + Vite | 80 (nginx) | UI, reverse proxy |
| API Gateway | C# | ASP.NET Core 9 | 8080 (Docker) / 5246 (local) | Video management, orchestration |
| AI Backend | Python 3.11 | FastAPI | 8000 | Pose estimation, DTW analysis |

---

## Root Directory

```
TempAISpotter/
+-- .git/
+-- .gitignore
+-- README.md
+-- ARCHITECTURE.md          <-- this file
+-- DOCKER_SETUP.md
+-- docker-compose.yml
+-- package.json
+-- package-lock.json
+-- AI/
|   +-- AI/ Python + .NET backends
+-- frontend/                 # React frontend
```

### `.gitignore`

Ignores Python virtualenvs, `__pycache__`, `node_modules`, IDE files, .NET `bin/`/`obj/`, and all video files (`*.mp4`, `*.mov`, `*.avi`, `*.mkv`). Also ignores `AI/backend/Videos/`.

### `package.json` (root)

Root-level npm configuration with React 19 and TypeScript type definitions. Used for IDE type support; the frontend has its own `package.json` for building.

```
Dependencies: react ^19.2.0, react-dom ^19.2.0
DevDependencies: @types/css-modules, @types/react, @types/react-dom, typescript ~5.9.3
```

### `DOCKER_SETUP.md`

Extended Docker guide with cloud deployment instructions (Azure, AWS, Kubernetes), SSL/HTTPS setup, scaling, performance optimization, and a production security checklist.

---

## Frontend

```
frontend/
+-- .dockerignore             # Excludes node_modules, dist, .git, .env from image
+-- .gitignore                # Standard Vite/React ignores
+-- Dockerfile                # Two-stage: Node build -> nginx serve
+-- eslint.config.js          # ESLint 9 flat config (TS + React Hooks + React Refresh)
+-- index.html                # HTML shell, favicon: squat.png, title: "AI Spotter"
+-- nginx.conf                # Production reverse proxy configuration
+-- package.json              # Frontend dependencies and scripts
+-- package-lock.json
+-- tsconfig.json             # Base TS config: ES2022, strict, react-jsx
+-- tsconfig.app.json         # App-specific TS config (extends base)
+-- tsconfig.node.json        # Node-specific TS config (for Vite)
+-- vite.config.ts            # Vite build config with dev proxies
+-- public/                   # Static assets served directly
+-- src/
    +-- main.tsx              # React entry point (StrictMode + createRoot)
    +-- index.css             # Global styles: purple gradient background, body reset
    +-- App.tsx               # Main application component (~600 lines)
    +-- App.module.css        # All component styles (~800 lines)
    +-- vite-env.d.ts         # Vite TypeScript client types
    +-- assets/               # Application assets (images, etc.)
```

### `src/App.tsx`

The single-page application component. Contains all UI logic, state management, and API interaction.

**TypeScript Types:**
- `Video` — `{ id, path?, name?, originalName? }`
- `Exercise` — union of `"back_squat" | "front_squat" | "deadlift" | "benchpress" | "military_press"`
- `CameraAngle` — union of `"front" | "back" | "left_side" | "right_side" | "45_front_left" | "45_front_right"`
- `FeatureResult` — `{ feature, correlation, mae_degrees, combined_score, is_core }`
- `RepResult` — `{ rep_number, core_similarity, depth_score, user_flexion, template_flexion, hit_parallel, per_feature[], feedback }`
- `AnalysisResult` — `{ n_reps, average_core_similarity, average_depth_score, reps[] }`

**Helper Functions:**
- `gradeFor(score)` — Maps a 0-1 score to a letter grade (A/B/C/D/F) and CSS class name
- `formatFeatureName(name)` — Converts `"left_knee"` to `"Left Knee"`
- `getImprovementTips(rep)` — Generates coaching tips from per-feature scores. Looks at core features below 0.80 combined score and produces body-part-specific advice (knee tracking, hip hinge, trunk lean). Also checks parallel and depth.

**State Variables:**
- `exercise` / `cameraAngle` — User selections (step 1 & 2)
- `video` / `videoUrl` / `processedVideoPath` — Upload tracking
- `busy` / `analyzing` / `progress` — Loading states (progress polls `/progress` every 500ms)
- `analysis` — The DTW analysis result from the backend
- `expandedReps` — `Set<number>` tracking which rep cards are expanded for detail view

**UI Flow (3 steps):**
1. **Exercise selection** — Grid of exercise buttons
2. **Camera angle selection** — Grid of angle buttons with descriptions
3. **Upload & Analysis** — File upload, video preview, "Do Analysis" button, progress bar, verdict display

**Verdict Display:**
- Summary row: Core Similarity %, Depth Score, Reps Detected
- Per-rep cards with letter grade badges (A-F, color-coded)
- Core features table (Joint, Score, Grade)
- Expandable "In-Depth Analysis" per rep: improvement tips, all joint metrics table, depth comparison

**API Calls:**
- `POST /Video` — Upload video file, returns `Video` object
- `POST /Video/upload` — Combined upload + MediaPipe + DTW, returns `{ mediapipe, analysis }`
- `GET /progress` — Polls processing progress
- `POST /Video/cleanup` — Deletes uploaded and processed videos

### `src/App.module.css`

CSS Modules scoped styles. Key sections:
- **Layout** — Centered flex column, dark theme
- **Steps** — Step indicator with active/done/pending states
- **Selection** — Card grid for exercise and camera angle selection
- **Upload** — Drag-style upload area with cloud icon
- **Video** — Video player card with header
- **Progress** — Gradient progress bar with percentage text
- **Verdict** — Summary cards, rep cards, feature tables, grade badges
- **In-Depth Analysis** — Expandable detail toggle, tips container with bullet dots, core row highlights, depth comparison
- **Grades** — Color system: A=green, B=blue, C=yellow, D=orange, F=red

### `nginx.conf`

Production reverse proxy configuration:
- **Port 80** — Serves built React files
- **Gzip** — Enabled for text, CSS, JS, JSON
- **Security headers** — X-Frame-Options, X-Content-Type-Options, X-XSS-Protection
- **Static caching** — 1 year for JS, CSS, images, fonts
- **Proxy rules:**
  - `/Video/*` -> `dotnet-backend:8080` (10-minute timeout, 500MB body limit)
  - `/progress` -> `python-backend:8000`
  - `/view_processed/*` -> `python-backend:8000` (buffered for video streaming)
- **Health check** — `/health` returns 200

### `vite.config.ts`

Development server configuration:
- React plugin enabled
- Dev proxy rules mirror nginx but point to `localhost:5246` (.NET) and `localhost:8000` (Python)

### `Dockerfile`

Two-stage build:
1. **Builder** — `node:20-alpine`, installs deps, runs `npm run build`
2. **Runtime** — `nginx:alpine`, copies `dist/` and `nginx.conf`

---

## .NET API Gateway

```
AI/backend/
+-- AI-spotter.csproj         # .NET 9 project file
+-- AI-spotter.http           # HTTP test file (for VS REST Client)
+-- Program.cs                # Application entry point
+-- Dockerfile.dotnet         # Three-stage Docker build
+-- appsettings.json          # Production config
+-- appsettings.Development.json  # Dev config
+-- Controllers/
|   +-- VideoController.cs    # Main API controller (all endpoints)
|   +-- UploadController.cs   # Legacy upload endpoint
+-- Models/
|   +-- Video.cs              # Video data model
+-- Services/
|   +-- VideoService.cs       # In-memory video store
+-- PublicClasses/
|   +-- UploadHandler.cs      # File validation and saving
+-- Properties/
|   +-- launchSettings.json   # Local launch profiles (ports 5246/7105)
+-- Videos/                   # Uploaded video files (UUID-named .mp4)
```

### `AI-spotter.csproj`

```xml
TargetFramework: net9.0
Nullable: enable
ImplicitUsings: enable
RootNamespace: AI_spotter
```

**NuGet packages:**
- `Microsoft.AspNetCore.OpenApi` 9.0.7 — OpenAPI/Swagger generation
- `Scalar.AspNetCore` 2.6.1 — API documentation UI (accessible at `/scalar`)

### `Program.cs`

Application bootstrap:
1. Registers `IAiClientConnect` / `AiClientConnect` as typed HttpClient with 10-minute timeout
2. Adds controller support and OpenAPI
3. Maps Scalar API reference (dev only)
4. Maps controllers, enables HTTPS redirection

### `Controllers/VideoController.cs`

**Interface: `IAiClientConnect`**

Defines the contract for communicating with the Python backend:
- `Connect(path)` — Calls `GET /verdict?path={path}` (MediaPipe processing)
- `Analyze(path, exerciseType, template)` — Calls `GET /analyze?path={path}&exercise_type={type}&template={file}` (DTW analysis)

**Class: `AiClientConnect`**

Implementation of `IAiClientConnect`. Reads `PythonBackendUrl` from configuration (defaults to `http://localhost:8000`). Both methods make HTTP GET calls and return the JSON response body as a string.

**Class: `VideoController`**

REST API controller routed at `/Video`. Endpoints:

| Method | Route | Description |
|--------|-------|-------------|
| `GET` | `/Video` | List all videos |
| `GET` | `/Video/{id}` | Get video by ID |
| `GET` | `/Video/aiApi/{aiMethod}/{id}` | Trigger MediaPipe processing on a video |
| `POST` | `/Video` | Upload a video file (saves to `Videos/` with UUID name) |
| `POST` | `/Video/upload` | **Main endpoint** — Upload + MediaPipe + DTW analysis pipeline |
| `POST` | `/Video/cleanup` | Delete original + processed video files |
| `PUT` | `/Video/{id}` | Replace a video file |
| `DELETE` | `/Video/{id}` | Delete video by ID |
| `DELETE` | `/Video/path/{path}` | Delete video by file path |

**`POST /Video/upload` (UploadAndVerdict) — Main Pipeline:**
1. Uploads the video (calls `Create` internally)
2. Calls Python `/verdict` (MediaPipe pose estimation)
3. Calls Python `/analyze` (DTW comparison)
4. Merges both JSON responses into `{ mediapipe: {...}, analysis: {...} }`
5. Returns the combined result

### `Controllers/UploadController.cs`

Legacy upload endpoint at `POST /api/upload/uploadvideo`. Delegates to `UploadHandler.Upload()`.

### `Models/Video.cs`

```csharp
public class Video {
    public int Id { get; set; }
    public string? Path { get; set; }
    public string? Name { get; set; }        // UUID filename
    public string? OriginalName { get; set; } // User's original filename
}
```

### `Services/VideoService.cs`

In-memory video store using a static `List<Video>`. Provides CRUD operations: `GetAll()`, `Get(id)`, `Add(video)`, `Update(video)`, `Delete(id)`. Auto-increments ID starting from 3 (two placeholder entries pre-loaded).

### `PublicClasses/UploadHandler.cs`

File upload validation and disk persistence:
- **Valid extensions:** `.mp4`, `.gif`
- **Max file size:** 100 MB
- **Storage:** Saves to `Videos/` directory with `Guid.NewGuid()` filename
- **Returns:** `(bool IsSuccess, string Response)` tuple

### `appsettings.json`

```json
{
  "AllowedHosts": "*",
  "PythonBackendUrl": "http://localhost:8000"
}
```

In Docker, `PythonBackendUrl` is overridden via environment variable to `http://python-backend:8000`.

### `Dockerfile.dotnet`

Three-stage build:
1. **Build** — `dotnet/sdk:9.0`, restores and builds the project
2. **Publish** — Creates release publish output
3. **Runtime** — `dotnet/aspnet:9.0`, copies published files, creates `Videos/` and `ProcessedVideos/` directories

---

## Python AI Backend

```
AI/
+-- .gitignore                # Ignores videos/, ProcessedVideos/, landmarks, embeddings, templates
+-- Dockerfile.python         # Python 3.11-slim + system deps + pip install
+-- # .sln file removed in refactor             # Visual Studio solution file (references backend/AI-spotter.csproj)
+-- README.md                 # Python backend documentation
+-- requirements.txt          # Python dependencies
+-- test.py                   # End-to-end test script
+-- test_embeddings.py        # Embeddings/DTW test script
+-- AI/                       # AI processing modules
+-- Utils/                    # Shared utility modules
+-- backend/                  # .NET API gateway (see above)
+-- ProcessedVideos/          # Output videos with skeleton overlay
+-- videos/                   # Source test videos
```

### `requirements.txt`

```
numpy==1.26.4
opencv-contrib-python==4.11.0.86
mediapipe==0.10.21
protobuf==4.25.8
fastapi==0.115.14
uvicorn[standard]==0.35.0
python-multipart==0.0.6
scipy==1.11.4
dtw-python==1.5.3
pydantic==2.11.7
```

### `backend/main.py` (FastAPI Application)

The Python FastAPI server. All endpoints:

| Method | Route | Description |
|--------|-------|-------------|
| `POST` | `/uploadfile/` | Return uploaded filename (no processing) |
| `POST` | `/upload/` | Save video to `uploaded/` directory |
| `POST` | `/upload_in_memory/` | Store video in RAM (BytesIO) |
| `POST` | `/process_in_memory/{filename}` | Process in-memory video with MediaPipe |
| `POST` | `/process_video/` | Upload + process + return processed video stream |
| `GET` | `/verdict?path=` | **Main endpoint** — Run MediaPipe on video, save landmarks, return result |
| `GET` | `/analyze?path=&exercise_type=&template=` | Load landmarks, run DTW analysis, return verdict |
| `GET` | `/progress` | Return processing progress `{ active, frame, total_frames, percent }` |
| `GET` | `/watch/{filename}` | Serve HTML page with embedded video player |
| `GET` | `/view_in_memory/{filename}` | Stream in-memory video |
| `GET` | `/view_processed/{filename}` | Serve processed video file from disk |

**Key endpoints in production flow:**

`GET /verdict` — Called by .NET backend. Receives a video file path, instantiates `MediaPipeVideoProcessor`, runs `process_video()`, and returns the result JSON. Uses `def` (not `async def`) since MediaPipe is CPU-bound.

`GET /analyze` — Called by .NET backend after `/verdict`. Derives the landmarks path from the video path (`{basename}_landmarks.npy`), loads the numpy array, calls `analyze_user_video()`, and returns the DTW verdict JSON. Also uses `def` for CPU-bound work.

### `test.py`

End-to-end test script. Configurable at the top: `input_video`, `output_video`, `TEMPLATE_FILE`, `EXERCISE_TYPE`. Runs the full pipeline:
1. Process video with MediaPipe (saves skeleton overlay + landmarks)
2. Load generated landmarks
3. Create embedding, segment into reps
4. Run DTW comparison against template for each rep
5. Print feedback and verdict

### `test_embeddings.py`

Standalone DTW analysis test. Lists available landmark and template files, selects configurable ones, then runs:
1. Load landmarks from `.npy` file
2. Create embedding
3. Load template, segment reps
4. Compare each rep via DTW
5. Print detailed per-rep results

### `Dockerfile.python`

Single-stage build on `python:3.11-slim`:
1. Installs system dependencies: `libgl1`, `libglib2.0-0`, `libgomp1`, `ffmpeg`, `libx264-dev`, `libsm6`, `libxext6`, `libxrender1`
2. Installs Python packages from `requirements.txt`
3. Copies `AI/`, `Utils/`, and `backend/main.py`
4. Creates `Videos/`, `ProcessedVideos/`, `MediaPipe_landmarks/` directories
5. Runs `uvicorn backend.main:app --host 0.0.0.0 --port 8000`

---

## AI Processing Pipeline

```
AI/
+-- __init__.py                         # Empty package marker
+-- MediaPipe.py                        # Pose estimation video processor
+-- embedding/                          # Pre-computed embedding .npy files
+-- MediaPipe_landmarks/                # Pre-computed landmark .npy files
+-- templates/                          # Pro reference templates .npz files
+-- process_landmarks/
    +-- __init__.py                     # Empty package marker
    +-- exercise_config.py              # Exercise type definitions
    +-- create_embedding.py             # Embedding pipeline
    +-- create_template.py              # Template creation and I/O
    +-- dtw_analysis.py                 # DTW comparison engine
    +-- verdict.py                      # Feedback generator + analysis entry point
    +-- improved_embedding_pipeline.ipynb  # Jupyter notebook (research/development)
```

### `MediaPipe.py`

**Class: `MediaPipeVideoProcessor`**

Core video processor using Google MediaPipe Pose.

**Module-level state:**
```python
processing_progress = {"active": False, "frame": 0, "total_frames": 0, "percent": 0}
```
This dict is shared with the FastAPI `/progress` endpoint for real-time progress polling.

**Methods:**
- `__init__()` — Initializes `mp.solutions.pose.Pose()` and `mp.solutions.drawing_utils`
- `draw_pose(frame, results, all_landmarks, calculate_angle)` — Draws skeleton overlay on a video frame. Can filter to specific landmarks and optionally overlay angle calculations.
- `process_video(input_path, output_path, all_landmarks, calculate_angle)` — Main pipeline:
  1. Opens video with OpenCV
  2. Iterates frame-by-frame, running MediaPipe Pose
  3. Extracts 33 landmarks per frame (x, y, z, visibility) -> `(T, 33, 4)` numpy array
  4. Draws skeleton overlay on each frame
  5. Writes processed video to output path
  6. Saves landmarks as `.npy` file in `MediaPipe_landmarks/`
  7. Updates `processing_progress` each frame
  8. Returns `{ path: output_path }` dict

**Imports from Utils:** Joint coordinate extraction, angle calculation, exercise counters.

### `process_landmarks/exercise_config.py`

**`EXERCISE_CONFIGS`** — Dictionary of exercise type configurations:

| Key | min_distance | prominence | Description |
|-----|-------------|------------|-------------|
| `heavy_squat` | 100 (~3.3s @30fps) | 25 | Heavy barbell squats, slow controlled |
| `bodyweight_squat` | 45 (~1.5s @30fps) | 15 | Bodyweight/goblet squats, moderate |
| `jump_squat` | 25 (~0.8s @30fps) | 10 | Plyometric squats, fast explosive |
| `adaptive` | (dynamic) | (dynamic) | Auto-detect from signal |

`min_distance` is the minimum frames between rep peaks. `prominence` is the required angle change amplitude for peak detection.

**`CORE_FEATURES`** — Per-exercise feature importance:
```python
'squat': ['left_knee', 'right_knee', 'left_hip', 'right_hip', 'trunk_lean']
```
These are the joints that matter most for scoring and feedback.

### `process_landmarks/create_embedding.py`

Converts raw landmarks into a feature embedding vector per frame.

**`build_embedding(smooth_angles_data, landmarks)`**

Concatenates 29 features per frame:
- 13 smoothed joint angles
- 13 angle velocities (frame-to-frame differences)
- 1 knee symmetry (left_knee - right_knee)
- 1 hip symmetry (left_hip - right_hip)
- 1 squat depth (hip vs knee vertical distance)

Returns `(T-1, 29)` embedding array.

**`normalize_embedding(embedding, ref_mean, ref_std)`**

Z-score normalization using reference (pro) statistics. If no reference provided, computes from the embedding itself.

**`create_embedding_from_landmarks(landmarks)`**

Full pipeline: landmarks `(T, 33, 3+)` -> angle extraction -> Savitzky-Golay smoothing -> embedding build. Returns `(embedding, smooth_angles, feature_names)`.

**`save_embedding(embedding, ref_mean, ref_std, embedding_path, stats_path)`**

Saves embedding as `.npy` and normalization stats as `.npz`.

### `process_landmarks/create_template.py`

Creates a reference template from a professional's video landmarks.

**`create_template_rep(pro_reps_angles, target_length, method, core_feature_indices)`**

Three methods for template creation:
- `'first'` — Uses the first rep as-is (raw frames, no resampling)
- `'best'` — Scores each rep by quality (smoothness + consistency on core features), selects highest
- `'average'` — Resamples all reps to `target_length` frames, then averages them

Returns `(template, info)` where template is `(T, D)` array.

**`create_template_from_landmarks(landmarks, exercise_type, method, target_length, core_features_list)`**

Full pipeline: landmarks -> angles -> smooth -> find rep boundaries -> extract reps -> create template.

**`save_template(template, template_info, save_path, ref_name, exercise, core_features_list)`**

Saves as `.npz` file containing: template array, feature_names, core_features, metadata.

**`load_template(template_path)`**

Loads `.npz` file, returns `(template, feature_names, core_features)`.

### `process_landmarks/dtw_analysis.py`

Dynamic Time Warping comparison between user reps and the pro template.

**`per_feature_dtw_similarity(ref_angles, user_angles, feature_names)`**

Runs DTW independently on each 1D angle signal. After alignment, computes:
- Pearson correlation (pattern similarity)
- Mean Absolute Error in degrees (magnitude difference)

Returns list of `{ feature, correlation, mae_degrees }` dicts.

**`compare_rep_to_template(user_rep_angles, template, feature_names, core_features)`**

Per-feature DTW with specialized scoring:

For **knee angles**: Uses depth penalty based on how much shallower the user squats compared to the template. `depth_penalty = exp(-shortfall / 20)`. Matching or exceeding template depth scores 1.0.

For **other joints**: Uses MAE penalty via exponential decay: `mae_penalty = exp(-mae_degrees / 30)`.

Both are combined with correlation: `combined_score = correlation * penalty`.

**Depth analysis:**
- Computes template and user max knee flexion (average of both knees)
- Converts inner angle to flexion angle
- Checks if user hit parallel (inner angle <= 90 degrees)
- Depth score: 100 if matching/deeper, penalized by 2 points per degree of shortfall

Returns dict with `per_feature`, `overall_similarity`, `core_similarity`, `template_flexion`, `user_flexion`, `hit_parallel`, `depth_score`.

### `process_landmarks/verdict.py`

Generates human-readable feedback and orchestrates the full analysis.

**`generate_feedback(rep_result, rep_number)`**

Produces text feedback per rep:
- Overall grade based on `core_similarity`: >0.95 Excellent, >0.90 Great, >0.80 Good, >0.70 Needs improvement, else Significant issues
- Lists problem areas (core features with correlation <0.85 or MAE >10 degrees)
- Body-part-specific advice: knee depth/tracking, hip hinge pattern, trunk angle

**`analyze_user_video(landmarks, template_path, exercise_type)`**

Full analysis entry point. Pipeline:
1. Load template from `.npz` file
2. Extract angles from user landmarks (x,y,z only)
3. Smooth with Savitzky-Golay filter
4. Find rep boundaries using exercise config
5. Extract angle data per rep
6. For each rep: run DTW comparison, generate feedback
7. Compute averages across reps

Returns JSON-serializable dict:
```python
{
    'n_reps': int,
    'average_core_similarity': float,
    'average_depth_score': float,
    'reps': [
        {
            'rep_number': int,
            'core_similarity': float,
            'overall_similarity': float,
            'depth_score': float,
            'user_flexion': float,
            'template_flexion': float,
            'hit_parallel': bool,
            'per_feature': [{ 'feature', 'correlation', 'mae_degrees', 'penalty', 'combined_score', 'is_core' }],
            'feedback': str
        }
    ]
}
```

### `process_landmarks/improved_embedding_pipeline.ipynb`

Jupyter notebook used during development to prototype the embedding and DTW pipeline. The production code in the `process_landmarks/` Python files was extracted from this notebook.

---

## Utilities

```
AI/Utils/
+-- __init__.py               # Empty package marker
+-- utils/
|   +-- __init__.py           # Empty package marker
|   +-- utils.py              # Core utility functions (15 functions + constants)
+-- counters/
    +-- __init__.py           # Empty package marker
    +-- exercise_counter.py   # Abstract base class
    +-- squat_counter.py      # Squat rep counter
```

### `utils/utils.py`

Central utility module. Contains all mathematical and signal processing functions used by the pipeline.

**MediaPipe Joint Index Constants (19):**

```
HIP_L=23   HIP_R=24   KNEE_L=25  KNEE_R=26  ANKLE_L=27  ANKLE_R=28
HEEL_L=29  HEEL_R=30  TOE_L=31   TOE_R=32   SHOULDER_L=11  SHOULDER_R=12
ELBOW_L=13 ELBOW_R=14 WRIST_L=15 WRIST_R=16 PINKY_L=17  PINKY_R=18
NOSE=0
```

**`ANGLE_NAMES`** — 13 angle feature names:
```
left_ankle, right_ankle, left_knee, right_knee, left_hip, right_hip,
left_shoulder, right_shoulder, left_elbow, right_elbow, left_wrist, right_wrist,
trunk_lean
```

**Functions:**

| Function | Purpose |
|----------|---------|
| `get_joint_coords(landmarks, joint_name)` | Extract hip/knee/ankle coordinates for a named joint |
| `calculate_angle(p1, p2, p3)` | 2D angle at vertex p2 using `atan2` |
| `calculate_angle_flexion(p1, p2, p3)` | Flexion-style angle variant |
| `calculate_angle_3d(p1, p2, p3)` | 3D angle using dot product |
| `compute_angle_2d(p1, p2, p3)` | 2D inner angle using x,y only (degrees) |
| `compute_trunk_lean_2d(landmarks)` | Forward trunk lean from shoulder/hip midpoints vs vertical |
| `compute_angle_features_2d(landmarks)` | Extract all 13 angle features for all frames -> `(T, 13)` |
| `inner_to_flexion(inner_angle)` | Convert MediaPipe inner angle to anatomical flexion: `180 - inner` |
| `smooth_angles(angles, window, polyorder)` | Savitzky-Golay filter (default window=11, polyorder=3) |
| `resample_to_length(signal, target_length)` | Linear interpolation to fixed frame count |
| `compute_squat_depth(landmarks)` | Hip-to-knee vertical distance, normalized by torso length |
| `estimate_adaptive_params(smooth_angles, fps)` | Auto-detect rep timing parameters from the knee signal |
| `find_rep_boundaries(smooth_angles, exercise_config)` | Detect rep start/end frames using peak detection (`scipy.signal.find_peaks`) |
| `extract_rep_angles(smooth_angles, reps)` | Slice angle array into per-rep segments |
| `score_rep_quality(rep_angles, core_feature_indices)` | Score a rep's quality (smoothness + consistency) |

**Key design:** `find_rep_boundaries` takes an `exercise_config` dict as parameter (not a global lookup), keeping it decoupled from the config module.

### `counters/exercise_counter.py`

**Abstract base class: `ExerciseCounter`**

```python
class ExerciseCounter(ABC):
    name: str
    total_reps: int
    valid_reps: int
    invalid_reps: int

    @abstractmethod
    def update(self, landmarks): pass

    def get_results(self) -> dict: ...
```

### `counters/squat_counter.py`

**Class: `SquatCounter(ExerciseCounter)`**

Real-time rep counter that tracks the right knee angle (hip-knee-ankle). State machine with `"up"` and `"down"` states:
- Descent detected when anatomical angle increases by >3 degrees
- Rep complete when angle returns within ~6 degrees of starting position
- Tracks deepest angle during each squat
- Classifies as valid if deepest angle exceeds `min_angle` threshold (default 90 degrees)

---

## Data Files

### Templates (`templates/`)

Pro reference templates saved as `.npz` (NumPy compressed archive):

| File | Size | Description |
|------|------|-------------|
| `front_narrow_template.npz` | 18 KB | Front camera, narrow stance squat |
| `squat_template.npz` | 18 KB | General squat template |

Each `.npz` contains: `template` array (T, 13), `feature_names`, `core_features`, creation metadata.

### Landmarks (`MediaPipe_landmarks/`)

Pre-processed pose landmarks saved as `.npy` (NumPy array):

| File | Size | Shape |
|------|------|-------|
| `back_angle_narrow_landmarks.npy` | 321 KB | (T, 33, 4) |
| `back_squat_back_landmarks.npy` | 303 KB | (T, 33, 4) |
| `back_squat_front_landmarks.npy` | 63 KB | (T, 33, 4) |
| `front_narrow_landmarks.npy` | 328 KB | (T, 33, 4) |
| `front_wide_landmarks.npy` | 240 KB | (T, 33, 4) |
| `squat_back_new_landmarks.npy` | 588 KB | (T, 33, 4) |
| `squat_back_res_bob_landmarks.npy` | 330 KB | (T, 33, 4) |
| `squat_back_res_bobby_landmarks.npy` | 330 KB | (T, 33, 4) |

Each array has shape `(frames, 33_joints, 4_values)` where values are `(x, y, z, visibility)`.

### Embeddings (`AI/embedding/`)

Pre-computed embedding vectors (15 files). Used for research/testing, not in the production flow.

Notable files:
- `front_narrow_embedding.npy` / `ref_improved_embedding.npy` — Reference embeddings
- `user_improved_embedding.npy` / `front_wide_embedding.npy` — User embeddings
- `normalization_stats.npz` / `front_narrow_normalization_stats.npz` — Mean/std for z-score normalization

### Source Videos (`videos/`)

Test videos in MP4 format (converted from MOV originals):
- Various camera angles: front narrow, front wide, back angle, back squat
- Multiple test subjects: standard, bob, bobby
- Sizes range from 1.4 MB to 28 MB (MP4), originals up to 90 MB (MOV)

### Processed Videos (`ProcessedVideos/`)

Output videos with MediaPipe skeleton overlay drawn on each frame. 9 files, sizes 12-33 MB.

---

## Docker Infrastructure

### `docker-compose.yml`

Orchestrates three services on a bridge network (`app-network`):

**Shared volumes:**
- `video-storage` — Mounted at `/app/Videos` on both backends
- `processed-storage` — Mounted at `/app/ProcessedVideos` on both backends
- `landmarks-storage` — Mounted at `/app/MediaPipe_landmarks` on Python backend

**Resource limits:**
- Python backend: 4 GB memory limit, 2 GB reserved

**Port mapping:**

| Service | Container Port | Host Port |
|---------|---------------|-----------|
| frontend | 80 | 80 |
| dotnet-backend | 8080 | 5246 |
| python-backend | 8000 | 8000 |

**Startup order:** python-backend -> dotnet-backend -> frontend

### Container Communication

Inside Docker, services reference each other by service name:
- Frontend nginx proxies to `dotnet-backend:8080` and `python-backend:8000`
- .NET backend calls `http://python-backend:8000` (configured via `PythonBackendUrl` env var)

---

## Request Flow

### Video Analysis (Production)

```
Browser
  |
  | POST /Video/upload (FormData: video, exercise, camera_angle)
  v
nginx (:80)
  |
  | proxy_pass
  v
.NET Backend (:8080)
  |
  | 1. Save video to Videos/ (UUID name)
  | 2. GET /verdict?path={video_path}
  v
Python Backend (:8000)
  |
  | MediaPipe processes video frame-by-frame
  | Saves landmarks to MediaPipe_landmarks/{name}_landmarks.npy
  | Saves processed video to ProcessedVideos/
  | Returns { path: "ProcessedVideos/..." }
  |
  v
.NET Backend
  |
  | 3. GET /analyze?path={video_path}&exercise_type=heavy_squat&template=front_narrow_template.npz
  v
Python Backend
  |
  | Loads landmarks .npy
  | Runs angle extraction + smoothing
  | Segments into reps
  | DTW comparison per rep against template
  | Generates feedback
  | Returns { n_reps, average_core_similarity, average_depth_score, reps: [...] }
  |
  v
.NET Backend
  |
  | 4. Merges both responses
  | Returns { mediapipe: {...}, analysis: {...} }
  v
nginx -> Browser
  |
  | Renders verdict UI: grades, depth scores, improvement tips
```

### Progress Polling (During Analysis)

```
Browser (every 500ms)
  |
  | GET /progress
  v
nginx -> Python Backend
  |
  | Returns { active, frame, total_frames, percent }
  v
Browser updates progress bar
```

---

## Data Flow & Pipeline

### From Video to Verdict

```
Video file (.mp4)
  |
  | MediaPipe Pose (frame-by-frame)
  v
Raw Landmarks (T, 33, 4) -- x, y, z, visibility per joint
  |
  | compute_angle_features_2d()
  v
Joint Angles (T, 13) -- 12 joint angles + trunk lean
  |
  | smooth_angles() -- Savitzky-Golay filter
  v
Smoothed Angles (T, 13)
  |
  | find_rep_boundaries() -- peak detection on knee signal
  v
Rep Boundaries [(start1, end1), (start2, end2), ...]
  |
  | extract_rep_angles()
  v
Per-Rep Angles [(T1, 13), (T2, 13), ...]
  |
  | compare_rep_to_template() -- per-feature DTW
  v
Per-Rep Results { correlation, mae, penalty, combined_score } x 13 features
  |
  | generate_feedback() + scoring
  v
Verdict { n_reps, grades, depth_scores, improvement_tips }
```

### The 13 Angle Features

Extracted for every frame from 33 MediaPipe landmarks:

| Index | Name | Joints (vertex in bold) |
|-------|------|------------------------|
| 0 | left_ankle | knee - **ankle** - toe |
| 1 | right_ankle | knee - **ankle** - toe |
| 2 | left_knee | hip - **knee** - ankle |
| 3 | right_knee | hip - **knee** - ankle |
| 4 | left_hip | shoulder - **hip** - knee |
| 5 | right_hip | shoulder - **hip** - knee |
| 6 | left_shoulder | elbow - **shoulder** - hip |
| 7 | right_shoulder | elbow - **shoulder** - hip |
| 8 | left_elbow | shoulder - **elbow** - wrist |
| 9 | right_elbow | shoulder - **elbow** - wrist |
| 10 | left_wrist | elbow - **wrist** - pinky |
| 11 | right_wrist | elbow - **wrist** - pinky |
| 12 | trunk_lean | midpoint(shoulders) vs midpoint(hips) vs vertical |

### Scoring System

**Per-feature combined score** = `correlation * penalty`

- **Correlation**: Pearson correlation between DTW-aligned template and user signals (0 to 1)
- **Penalty** (knees): `exp(-depth_shortfall / 20)` — penalizes shallower squats
- **Penalty** (other joints): `exp(-mae_degrees / 30)` — penalizes angular deviation

**Core similarity** = average combined score across core features only (knees, hips, trunk)

**Depth score** = 100 if matching/deeper than template, minus 2 points per degree of shortfall

**Letter grades** (frontend):
- A: > 80% combined score
- B: > 60%
- C: > 40%
- D: > 20%
- F: <= 20%
