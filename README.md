# AI Spotter

AI-powered exercise form analysis. Upload a video of yourself performing a lift, and AI Spotter compares your form against a professional template using pose estimation and Dynamic Time Warping (DTW).

Currently supports squat variations with multiple camera angles.

## How It Works

1. **Select your exercise** and the camera angle used in the recording
2. **Upload a video** of yourself performing the lift
3. **MediaPipe** detects body landmarks frame-by-frame
4. **DTW analysis** compares your movement pattern against a pro template
5. **Get a verdict** with per-rep grades, depth scores, and improvement tips

## Quick Start (Docker)

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- At least **6 GB free RAM** (4 GB reserved for AI processing)
- At least **10 GB free disk space**

### 1. Clone the repository

```bash
git clone <repository-url>
cd TempAISpotter
```

### 2. Build and start

```bash
docker-compose up --build
```

The first build takes a few minutes (downloads Python ML libraries, .NET SDK, Node modules). Subsequent starts are much faster.

### 3. Open the app

Navigate to **http://localhost** in your browser.

### 4. Stop the app

Press `Ctrl+C` in the terminal, then:

```bash
docker-compose down
```

## Architecture

Three containers communicate over a Docker bridge network:

```
Browser (:80)
   |
   nginx (reverse proxy)
   |
   +-- /Video/*  -->  .NET Backend (:8080)  -->  Python Backend (:8000)
   +-- /progress -->  Python Backend (:8000)
   +-- /*        -->  React static files
```

| Service | Tech | Role |
|---------|------|------|
| **frontend** | React 19 + Vite + nginx | UI and reverse proxy |
| **dotnet-backend** | ASP.NET Core 9 | API gateway, video management |
| **python-backend** | FastAPI + MediaPipe | Pose estimation, DTW analysis |

Shared Docker volumes persist uploaded videos, processed videos (with skeleton overlay), and landmark data between containers.

## Docker Commands

```bash
# Start in background
docker-compose up -d

# View logs (all services)
docker-compose logs -f

# View logs (single service)
docker-compose logs -f python-backend

# Rebuild after code changes
docker-compose up --build

# Rebuild from scratch (no cache)
docker-compose build --no-cache
docker-compose up -d

# Stop and remove containers
docker-compose down

# Stop and remove containers + volumes (clears all data)
docker-compose down -v

# Check service status
docker-compose ps
```

## Local Development (Without Docker)

If you prefer to run each service directly for development:

### Prerequisites

- Python 3.11+
- .NET 9 SDK
- Node.js 20+

### Terminal 1 - Python Backend

```bash
cd AI/OlympicAi
python -m venv venv

# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
uvicorn backend.main:app --reload
```

### Terminal 2 - .NET Backend

```bash
cd AI/OlympicAi/backend
dotnet run
```

### Terminal 3 - Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend dev server runs at **http://localhost:5173** with hot reload.

## Configuration

### Port Conflicts

If ports 80, 5246, or 8000 are already in use, edit `docker-compose.yml`:

```yaml
services:
  frontend:
    ports:
      - "3000:80"     # change 80 to 3000
```

### Memory

If the Python backend crashes during analysis, increase the memory limit in `docker-compose.yml`:

```yaml
python-backend:
  deploy:
    resources:
      limits:
        memory: 8G    # increase from 4G
```

### Video Processing Timeout

Long videos may exceed the default 10-minute proxy timeout. Edit `frontend/nginx.conf`:

```nginx
proxy_read_timeout 1200s;   # increase from 600s
```

Then rebuild: `docker-compose build frontend && docker-compose up -d frontend`

## Project Structure

```
TempAISpotter/
+-- docker-compose.yml          # Container orchestration
+-- frontend/                   # React + TypeScript + Vite
|   +-- src/App.tsx             # Main UI component
|   +-- nginx.conf              # Reverse proxy config
|   +-- Dockerfile
+-- AI/OlympicAi/
|   +-- AI/
|   |   +-- MediaPipe.py        # Pose estimation processor
|   |   +-- process_landmarks/
|   |   |   +-- exercise_config.py   # Exercise definitions
|   |   |   +-- create_template.py   # Template builder
|   |   |   +-- create_embedding.py  # Embedding pipeline
|   |   |   +-- dtw_analysis.py      # DTW comparison
|   |   |   +-- verdict.py           # Feedback generator
|   |   +-- templates/          # Pro reference templates (.npz)
|   |   +-- MediaPipe_landmarks/# Saved landmark data (.npy)
|   +-- Utils/                  # Shared utilities
|   +-- backend/                # .NET API gateway
|   |   +-- Controllers/VideoController.cs
|   |   +-- Dockerfile.dotnet
|   +-- Dockerfile.python
|   +-- requirements.txt
|   +-- test.py                 # End-to-end test script
+-- DOCKER_SETUP.md             # Extended Docker documentation
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `ModuleNotFoundError: No module named 'dtw'` | Rebuild with no cache: `docker-compose build --no-cache` |
| Python backend OOM crash | Increase memory limit in `docker-compose.yml` (see above) |
| Video upload fails | Check `client_max_body_size` in `nginx.conf` (default 500 MB) |
| Frontend shows no verdict | Check `docker-compose logs python-backend` for errors |
| Port already in use | Change the host port in `docker-compose.yml` (see above) |
| `--no-cache` flag error | Use `docker-compose build --no-cache` then `docker-compose up -d` (not `docker-compose up --build --no-cache`) |

## Tech Stack

- **Frontend:** React 19, TypeScript, Vite, CSS Modules, nginx
- **API Gateway:** ASP.NET Core 9, C#
- **AI Backend:** Python 3.11, FastAPI, MediaPipe, OpenCV, NumPy, SciPy, dtw-python
- **Infrastructure:** Docker, Docker Compose
