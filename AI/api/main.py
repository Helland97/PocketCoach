import os
import re
import base64
import json
from io import BytesIO
from fastapi import FastAPI, File, UploadFile,  HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, HTMLResponse, FileResponse, JSONResponse
from MediaPipe import MediaPipeVideoProcessor, processing_progress
from process_landmarks.verdict import analyze_user_video
from process_landmarks.exercise_config import EXERCISE_MAPPING, DEFAULT_EXERCISE
import numpy as np
import time
import tempfile
import traceback


app = FastAPI()

# CORS — this service is only reached through nginx on the internal Docker
# network. Restrict to the in-cluster origins so a browser cannot call the
# Python backend directly even if the port were ever exposed.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost",
        "http://localhost:80",
        "http://frontend",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Dictionary to store uploaded videos in memory (filename -> BytesIO buffer)
video_store = {}

# Allowed roots for path-bound endpoints. Anything outside these is rejected.
# Resolved at import time relative to the working directory uvicorn was launched
# from (AI/ in dev, /app in the container).
_ALLOWED_VIDEO_ROOTS = (
    os.path.realpath("Videos"),
    os.path.realpath("ProcessedVideos"),
)
_ALLOWED_LANDMARK_ROOT = os.path.realpath("MediaPipe_landmarks")
_ALLOWED_TEMPLATE_ROOT = os.path.realpath("templates")
_ALLOWED_PROCESSED_ROOT = os.path.realpath("ProcessedVideos")
_ALLOWED_UPLOAD_ROOT = os.path.realpath("uploaded")

# Filenames stored on disk are GUIDs from .NET (lowercase hex with dashes,
# optional .mp4/.gif extension). Anything else is rejected.
_SAFE_FILENAME_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def _safe_filename(name: str) -> str:
    """Return name if it is a plain filename with no path components, else 400."""
    if not name or "\x00" in name:
        raise HTTPException(status_code=400, detail="Invalid filename")
    base = os.path.basename(name)
    if base != name or base in ("", ".", ".."):
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not _SAFE_FILENAME_RE.match(base):
        raise HTTPException(status_code=400, detail="Invalid filename")
    return base


def _resolve_within(root: str, candidate: str) -> str:
    """Resolve candidate and ensure it lives under root. Raises 400 otherwise."""
    full = os.path.realpath(candidate)
    root_real = os.path.realpath(root)
    if full != root_real and not full.startswith(root_real + os.sep):
        raise HTTPException(status_code=400, detail="Path escapes allowed root")
    return full


def _resolve_within_any(roots, candidate: str) -> str:
    full = os.path.realpath(candidate)
    for root in roots:
        root_real = os.path.realpath(root)
        if full == root_real or full.startswith(root_real + os.sep):
            return full
    raise HTTPException(status_code=400, detail="Path escapes allowed root")


# POST ----------------------------------------------------------------------


# 📤 Endpoint to upload a file using FastAPI's UploadFile.
# This method is more efficient for large files, as it streams the data.
# Only the filename is returned in the response.
@app.post("/uploadfile/")
async def create_upload_file(file: UploadFile):
    safe = _safe_filename(file.filename or "")
    return {"filename": safe}


# 📤 POST endpoint to upload a video without any processing.
# The uploaded video is saved to the 'uploaded/' directory on disk.
# The filename is returned in the response.
@app.post("/upload/")
async def upload_video(file: UploadFile):
    upload_dir = "uploaded"
    os.makedirs(upload_dir, exist_ok=True)  # Create folder if it doesn't exist
    safe = _safe_filename(file.filename or "")
    file_path = _resolve_within(upload_dir, os.path.join(upload_dir, safe))

    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())

    return {"filename": safe, "status": "uploaded"}


# 📤 POST endpoint to upload a video and store it in memory.
# The video file is read fully into RAM and saved inside a BytesIO buffer.
# This means the video only lives as long as the app is running.
# Returns the filename and status confirmation.
@app.post("/upload_in_memory/")
async def upload_in_memory(file: UploadFile):
    safe = _safe_filename(file.filename or "")
    content = await file.read()
    video_store[safe] = BytesIO(content)
    return {"filename": safe, "status": "stored in memory"}



@app.post("/process_in_memory/{filename}")
async def process_in_memory(filename: str):
    # 1. Get the uploaded video from memory
    safe = _safe_filename(filename)
    video = video_store.get(safe)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found in memory")
    video.seek(0)

    # 2. Create temp files for input and output
    with tempfile.NamedTemporaryFile(suffix=".mp4") as temp_in, \
         tempfile.NamedTemporaryFile(suffix=".mp4") as temp_out:

        # Write the in-memory video to temp input file
        temp_in.write(video.read())
        temp_in.flush()

        # 3. Process the video using MediaPipeVideoProcessor
        processor = MediaPipeVideoProcessor()
        processor.process_video(temp_in.name, temp_out.name)

        # 4. Read the processed video into a BytesIO buffer
        temp_out.seek(0)
        processed_bytes = temp_out.read()
        processed_buffer = BytesIO(processed_bytes)

    # 5. Return the processed video as a streaming response
    processed_buffer.seek(0)
    return StreamingResponse(processed_buffer, media_type="video/mp4")


@app.get("/verdict", response_class=JSONResponse)
def get_verdict(path: str):

    start_time = time.time()
    try:
        # Constrain to the shared video volumes (Videos/ or ProcessedVideos/).
        safe_path = _resolve_within_any(_ALLOWED_VIDEO_ROOTS, path)
        print(f"[{time.time()-start_time:.2f}s] Received verdict request for path: {safe_path}")
        print(f"Current working directory: {os.getcwd()}")

        # Check if file exists
        if not os.path.exists(safe_path):
            print(f"ERROR: File not found at path: {safe_path}")
            raise HTTPException(status_code=404, detail="Video file not found")

        file_size_mb = os.path.getsize(safe_path) / (1024 * 1024)
        print(f"[{time.time()-start_time:.2f}s] File exists ({file_size_mb:.2f} MB), starting processing...")

        processor = MediaPipeVideoProcessor()
        result = processor.process_video(safe_path, safe_path)

        print(f"[{time.time()-start_time:.2f}s] Processing complete. Total time: {time.time()-start_time:.2f}s")
        print(f"Result: {result}")
        return result
    except HTTPException:
        raise
    except Exception as e:
        # Log full detail server-side, but do not leak it to the caller.
        print(f"ERROR in get_verdict after {time.time()-start_time:.2f}s: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/analyze", response_class=JSONResponse)
def analyze_landmarks(path: str, exercise: str = DEFAULT_EXERCISE):
    """
    Runs after /verdict. Takes the same video path, loads the landmarks
    that MediaPipe saved, creates an embedding, runs DTW analysis against
    the template for the requested exercise, and returns the verdict.
    """

    start_time = time.time()
    try:
        # Validate exercise against the static mapping rather than trusting input.
        if exercise not in EXERCISE_MAPPING:
            raise HTTPException(status_code=400, detail="Unknown exercise")
        mapping = EXERCISE_MAPPING[exercise]
        template_filename = mapping['template']

        # Reduce the incoming path to a basename, validate it, then rebuild
        # within trusted roots.
        raw_basename = os.path.basename(path)
        if not raw_basename or "\x00" in raw_basename or ".." in raw_basename:
            raise HTTPException(status_code=400, detail="Invalid path")
        base_name = os.path.splitext(raw_basename)[0]
        if not _SAFE_FILENAME_RE.match(base_name):
            raise HTTPException(status_code=400, detail="Invalid path")
        landmarks_path = _resolve_within(
            _ALLOWED_LANDMARK_ROOT,
            os.path.join("MediaPipe_landmarks", base_name + "_landmarks.npy"),
        )
        template_path = _resolve_within(
            _ALLOWED_TEMPLATE_ROOT,
            os.path.join("templates", _safe_filename(template_filename)),
        )

        print(f"[Analyze] Received request - video basename: {base_name}")
        print(f"[Analyze] Exercise: {exercise} -> template: {template_filename}, tempo: {mapping['tempo']}")

        if not os.path.exists(landmarks_path):
            raise HTTPException(status_code=404, detail="Landmarks not found")
        if not os.path.exists(template_path):
            raise HTTPException(status_code=404, detail="Template not found for exercise")

        landmarks = np.load(landmarks_path)
        print(f"[Analyze] [{time.time()-start_time:.2f}s] Loaded landmarks: {landmarks.shape}")

        result = analyze_user_video(landmarks, template_path, exercise)

        # Extract the embedding numpy array, encode as base64 for JSON transport
        embedding = result.pop('embedding')
        emb_feature_names = result.pop('embedding_feature_names')

        emb_bytes = embedding.astype(np.float64).tobytes()
        result['embedding_base64'] = base64.b64encode(emb_bytes).decode('ascii')
        result['embedding_shape'] = ','.join(str(d) for d in embedding.shape)
        result['embedding_feature_names'] = json.dumps(emb_feature_names)
        result['landmarks_shape'] = ','.join(str(d) for d in landmarks.shape)

        print(f"[Analyze] [{time.time()-start_time:.2f}s] Analysis complete. "
              f"{result['n_reps']} reps, avg similarity: {result['average_core_similarity']:.2%}, "
              f"embedding shape: {embedding.shape}")
        return result

    except HTTPException:
        raise
    except Exception as e:
        # Log full detail server-side, but return a generic message.
        print(f"[Analyze] ERROR after {time.time()-start_time:.2f}s: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/process_video/")
async def process_video(file: UploadFile = File(...)):
    # Save uploaded file to a temp file
    with tempfile.NamedTemporaryFile(suffix=".mp4") as temp_in, \
         tempfile.NamedTemporaryFile(suffix=".mp4") as temp_out:
        temp_in.write(await file.read())
        temp_in.flush()

        # Process video
        processor = MediaPipeVideoProcessor()
        processor.process_video(temp_in.name, temp_out.name)

        # Return processed video as a stream
        temp_out.seek(0)
        return StreamingResponse(BytesIO(temp_out.read()), media_type="video/mp4")


#@app.post("/verdict/")
#async def get_verdict(input_path: str):
#    return MediaPipeVideoProcessor.verdict(input_path)


# GET ----------------------------------------------------------------------


@app.get("/progress", response_class=JSONResponse)
async def get_progress():
    """Returns current frame-processing progress as {active, frame, total_frames, percent}."""
    return processing_progress


# 🌐 GET endpoint to serve a basic HTML page that embeds the uploaded video.
# This can be used to visually test whether the uploaded video is viewable in the browser.
@app.get("/watch/{filename}", response_class=HTMLResponse)
def watch_video_page(filename: str):
    # Validate before reflecting into HTML to prevent XSS via filename.
    safe = _safe_filename(filename)
    return f"""
    <html>
        <body>
            <h2>Watching: {safe}</h2>
            <video width="640" height="480" controls>
                <source src="/view/{safe}" type="video/mp4">
                Your browser does not support the video tag.
            </video>
        </body>
    </html>
    """


# 📺 GET endpoint to stream a video stored in memory by filename.
# Looks up the video BytesIO buffer in the in-memory store and streams it back.
# Raises 404 error if the video is not found in memory.
@app.get("/view_in_memory/{filename}")
def stream_in_memory(filename: str):
    safe = _safe_filename(filename)
    video = video_store.get(safe)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found in memory")
    video.seek(0)  # Reset read pointer to start
    return StreamingResponse(video, media_type="video/mp4")



@app.get("/view_processed/{filename:path}")
def view_processed_file(filename: str):
    # The frontend passes a relative path like "ProcessedVideos/<guid>.mp4".
    # Strip the directory portion and rebuild within the ProcessedVideos root.
    base = _safe_filename(os.path.basename(filename))
    full_path = _resolve_within(
        _ALLOWED_PROCESSED_ROOT,
        os.path.join(_ALLOWED_PROCESSED_ROOT, base),
    )
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(full_path, media_type="video/mp4")



# PUT ----------------------------------------------------------------------



# PATCH ----------------------------------------------------------------------



# DELETE ----------------------------------------------------------------------



# OPTIONS ----------------------------------------------------------------------



# HEAD ----------------------------------------------------------------------
