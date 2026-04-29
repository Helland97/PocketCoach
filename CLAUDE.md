# AI Spotter — Claude Guide

AI-powered exercise form analysis: upload a lift video, MediaPipe extracts
pose landmarks, DTW compares them against a pro template, and the user gets
per-rep grades + feedback. Currently scoped to squat variations.

For deep context see `README.md`, `ARCHITECTURE.md`, and `DOCKER_SETUP.md`.
This file is for Claude — keep it short and task-oriented.

## Stack

| Service          | Tech                                               | Dir         | Port |
|------------------|----------------------------------------------------|-------------|------|
| frontend         | React 19 + TypeScript + Vite + CSS Modules, nginx  | `frontend/` | 80   |
| dotnet-backend   | ASP.NET Core 9 (net9.0), EF Core + SQLite, Scalar  | `Backend/`  | 5246 |
| python-backend   | Python 3.11, FastAPI, MediaPipe, dtw-python        | `AI/`       | 8000 |

nginx (in the frontend container) is the single public entrypoint. It serves
React static files and reverse-proxies `/Video/*` to the .NET backend and
`/progress` to the Python backend. Browser talks only to port 80.

## Run / build / test

**Docker (preferred, full stack):**
```
docker-compose up --build      # first run or after code changes
docker-compose up -d           # detached
docker-compose logs -f <svc>   # frontend | dotnet-backend | python-backend
docker-compose down            # stop; add -v to wipe volumes (videos, db)
docker-compose build --no-cache && docker-compose up -d   # clean rebuild
```
App at http://localhost. Python backend needs ~4 GB RAM (see compose limits).

**Local dev (hot reload, three terminals):**
```
# Python
cd AI && python -m venv venv && venv\Scripts\activate   # bash: source venv/bin/activate
pip install -r requirements.txt
uvicorn api.main:app --reload                # :8000

# .NET
cd Backend && dotnet run                     # :5246, appsettings.json points to :8000
dotnet ef migrations add <Name>              # EF Core migrations live in Backend/Migrations
dotnet ef database update

# Frontend
cd frontend && npm install
npm run dev         # :5173, hot reload
npm run build       # tsc -b && vite build
npm run lint        # eslint .
```

**Tests:** there is no formal test suite. `AI/test.py` and
`AI/test_embeddings.py` are ad-hoc end-to-end scripts — run them manually
from `AI/` with the venv active. Don't invent a test runner; if you need
checks, add a script alongside those.

## Repo layout (what lives where)

```
frontend/src/           React app — App.tsx is the main UI, CSS Modules only
Backend/
  Controllers/          UploadController.cs, VideoController.cs (REST endpoints)
  Services/             VideoService.cs (business logic; keep controllers thin)
  Models/               EF entities: Session, Video, LandmarkData, Analysis
  Data/AppDbContext.cs  DbContext (SQLite, file at Data/aispotter.db)
  Migrations/           EF Core migrations — never hand-edit
  PublicClasses/        DTOs exchanged with Python backend
  Program.cs            DI + pipeline wiring
AI/
  api/main.py           FastAPI app — entry is api.main:app
  MediaPipe.py          Pose estimation processor
  process_landmarks/
    exercise_config.py  Exercise definitions (add new lifts here)
    model_config.py     ACTIVE_MODEL switch — picks DTW vs MLP/VAE path
    create_template.py  Build pro reference templates (.npz)
    create_embedding.py Embedding pipeline
    dtw_analysis.py     DTW comparison core
    verdict.py          Feedback generator
  mlp/                  Alternative models (Stats, LSTM, LSTM+Attention)
  templates/            Pro reference .npz files — gitignored, local only
  MediaPipe_landmarks/  Runtime landmark cache (.npy) — not user-edited
  Model_research_notebooks/   Jupyter experiments — gitignored, do not import from app code
```

## Shared state across containers (docker-compose.yml volumes)

- `video-storage` → uploaded originals (.NET writes, Python reads)
- `processed-storage` → skeleton-overlay outputs (Python writes)
- `landmarks-storage` → landmark `.npy` files (Python writes, .NET read-only)
- `sqlite-data` → `aispotter.db` (.NET only)

When changing file paths in either backend, verify both sides agree — paths
are hard-wired to these mount points.

## Conventions

**Frontend**
- TypeScript strict; ESLint flat config (`eslint.config.js`) with
  `typescript-eslint`, `react-hooks`, `react-refresh`. Run `npm run lint`
  before reporting a frontend task done.
- Styling is CSS Modules (`*.module.css`) — no Tailwind, no styled-components,
  no global stylesheets beyond `index.css`.
- API calls go through the nginx proxy paths (`/Video/...`, `/progress`),
  never directly to `:5246` or `:8000`.

**.NET backend**
- `Nullable` and `ImplicitUsings` are enabled; root namespace is `AI_spotter`.
- Controllers stay thin — push logic into `Services/`.
- Any schema change needs an EF Core migration; don't edit the DB by hand.
- `PythonBackendUrl` comes from config (`appsettings.json` locally,
  env var in Docker) — never hardcode the URL.
- OpenAPI is exposed via Scalar in Development.

**Python backend**
- Entry point is `api.main:app`; uvicorn is launched from the `AI/` directory
  so relative paths (`templates/`, `MediaPipe_landmarks/`) resolve correctly.
- To add an exercise or camera angle, edit `process_landmarks/exercise_config.py`
  and drop a matching template into `templates/`.
- To swap the analysis model, change `ACTIVE_MODEL` in
  `process_landmarks/model_config.py` — don't branch on it in callers.
- Notebooks in `Model_research_notebooks/` are scratch; do not import them
  from production code.

## Execution notes for Claude

- Shell is bash on Windows — use Unix syntax (forward slashes, `source`,
  `/dev/null`). Avoid PowerShell-isms.
- After editing Docker images (Dockerfiles, requirements.txt, .csproj,
  package.json), the containers need a rebuild — point the user at
  `docker-compose up --build`, don't claim the change is live.
- Don't run `docker-compose down -v` casually — it wipes uploaded videos
  and the SQLite DB.
- The repo is small and single-author; no PR templates or commit-message
  conventions to follow beyond the existing `git log` style.
