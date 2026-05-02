namespace AI_spotter.Controllers;

using AI_spotter.Models;
using AI_spotter.Data;
using AI_spotter.Services;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using AI_spotter.PublicClasses;
using System.Net.Http;
using System.Text.Json;

public interface IAiClientConnect{
    HttpClient AiClient {get;}
    Task<string?> Connect(string path);
    Task<(int StatusCode, string Body)> Analyze(string path, string exercise = "back_squat");
}

public class AiClientConnect : IAiClientConnect{
    public HttpClient AiClient {get;}
    private readonly string _pythonBackendUrl;

    public AiClientConnect(HttpClient client, IConfiguration configuration){
        AiClient = client;
        _pythonBackendUrl = configuration["PythonBackendUrl"] ?? "http://localhost:8000";
    }
//    public static async Task<VideoController> Create(){
//        var controller = new VideoController();
//        await controller.ConnectAiClient();
//        return controller;
//    }
    public async Task<string?> Connect(string path){
        try{
            using HttpResponseMessage response = await AiClient.GetAsync($"{_pythonBackendUrl}/verdict?path={path}");
            response.EnsureSuccessStatusCode();
            string responseBody = await response.Content.ReadAsStringAsync();
            Console.WriteLine(responseBody);
            return responseBody;
        }
        catch (HttpRequestException e){
            Console.WriteLine("\nException caught");
            Console.WriteLine("Exception message: {0}", e.Message);
            return null;
        }
    }

    public async Task<(int StatusCode, string Body)> Analyze(string path, string exercise = "back_squat"){
        try{
            var url = $"{_pythonBackendUrl}/analyze?path={Uri.EscapeDataString(path)}&exercise={Uri.EscapeDataString(exercise)}";
            Console.WriteLine($"[.NET] Calling analyze endpoint: {url}");
            using HttpResponseMessage response = await AiClient.GetAsync(url);
            string responseBody = await response.Content.ReadAsStringAsync();
            Console.WriteLine($"[.NET] Analyze response: {(int)response.StatusCode}");
            return ((int)response.StatusCode, responseBody);
        }
        catch (HttpRequestException e){
            Console.WriteLine($"[.NET] Analyze network exception: {e.Message}");
            return (502, $"Python backend unreachable: {e.Message}");
        }
    }
}

[ApiController]
[Route("[controller]")]
public class VideoController : ControllerBase{
    private readonly IAiClientConnect AiClient;
    private readonly AppDbContext _db;
    UploadHandler handleHerVideo = new UploadHandler();

    public VideoController(IAiClientConnect aiClient, AppDbContext db){
        AiClient = aiClient;
        _db = db;
    }


    [HttpGet]
    public ActionResult<List<Video>> GetAll() => VideoService.GetAll();


    [HttpGet("{id}")]
    public ActionResult<Video> Get(int id){
        var video = VideoService.Get(id);
        if (video == null){
            return NotFound();
        }
        return video;
    }

    [HttpGet("aiApi/{aiMethod}/{id}")]
    public async Task<IActionResult> GetAI(string aiMethod, int id){
        try{
            var path = VideoService.Get(id)?.Path;
            if (path == null){
                throw new NullReferenceException("id or path is null");
            }

            // Defence in depth: confirm the stored path is inside the Videos/
            // root before forwarding to the Python backend. VideoService is
            // an in-memory list, but a future caller of VideoService.Add
            // could insert an attacker-controlled Path; this check guarantees
            // we never hand an out-of-tree path to the AI service.
            var videosRoot = Path.GetFullPath(Path.Combine(Directory.GetCurrentDirectory(), "Videos"));
            var resolvedPath = Path.GetFullPath(path);
            if (!resolvedPath.StartsWith(videosRoot + Path.DirectorySeparatorChar, StringComparison.Ordinal)
                && resolvedPath != videosRoot){
                Console.WriteLine($"[.NET] Refusing to forward path outside Videos root: {resolvedPath}");
                return BadRequest("Invalid video path.");
            }

            string? result = await AiClient.Connect(path);
            if (result != null){
                return Ok(result);
            }
            else{
                return StatusCode(500, "Python backend returned no content");
            }
        }
        catch (HttpRequestException e){
            Console.WriteLine($"[.NET] GetAI HttpRequestException: {e.Message}");
            return StatusCode(500, "Internal Server Error");
        }
    }

    [HttpPost]
    public IActionResult Create(IFormFile video){
        (bool IsSuccess, string response) videoResponse = handleHerVideo.Upload(video);
        if (!videoResponse.IsSuccess){
            return BadRequest(videoResponse.response);
        }
        Video returnedVideo = new Video(){Id = -1, Name = videoResponse.response, 
                Path = Path.Combine(Path.Combine(Directory.GetCurrentDirectory(), "Videos"), videoResponse.response)};
        VideoService.Add(returnedVideo);
        return CreatedAtAction(nameof(Get), new { id = returnedVideo.Id }, returnedVideo);
    }

    [HttpPut("{id}")]
    public IActionResult Update(IFormFile newVideo, int id){
        Video? video = VideoService.Get(id);
        if (video == null){
            return NotFound();
        }
        (bool IsSuccess, string response) result = handleHerVideo.Upload(newVideo, video.Name);
        if (!result.IsSuccess){
            return BadRequest(result.response);
        }
        return CreatedAtAction(nameof(Get), new {id = id}, video);
    }
    
    [HttpDelete("{id}")]
    public IActionResult Delete(int id){
        Video? video = VideoService.Get(id);
        if (video is null){
            return NotFound();
        }
        if (System.IO.File.Exists(video.Path)){
            System.IO.File.Delete(video.Path);
            VideoService.Delete(id);
            return NoContent();
        }
        return StatusCode(500);
    }

    [HttpDelete("path/{path}")]
    public IActionResult DeletePath(string path){
        // Constrain deletion to the ProcessedVideos directory.
        // Reject any client-supplied directory traversal or absolute paths.
        if (string.IsNullOrWhiteSpace(path)){
            return BadRequest("Path is required.");
        }

        // Strip any directory components the client tried to include.
        var fileName = Path.GetFileName(path);
        if (string.IsNullOrEmpty(fileName) || fileName != path.Replace('\\', '/').Split('/').Last()){
            return BadRequest("Invalid path.");
        }

        // Reject NUL bytes and traversal sequences.
        if (fileName.Contains('\0') || fileName.Contains("..")){
            return BadRequest("Invalid path.");
        }

        // Allow only video files.
        var ext = Path.GetExtension(fileName).ToLowerInvariant();
        if (ext != ".mp4" && ext != ".gif"){
            return BadRequest("Unsupported file type.");
        }

        var processedRoot = Path.GetFullPath(Path.Combine(Directory.GetCurrentDirectory(), "ProcessedVideos"));
        var fullPath = Path.GetFullPath(Path.Combine(processedRoot, fileName));

        // Ensure the resolved path is still within ProcessedVideos (defence in depth).
        if (!fullPath.StartsWith(processedRoot + Path.DirectorySeparatorChar, StringComparison.Ordinal)
            && fullPath != processedRoot){
            return BadRequest("Invalid path.");
        }

        if (System.IO.File.Exists(fullPath)){
            System.IO.File.Delete(fullPath);
            return NoContent();
        }
        return NotFound();
    }

    [HttpPost("upload")]
    public async Task<IActionResult> UploadAndVerdict(
        [FromForm] int? videoId,
        IFormFile? video,
        [FromForm] string exercise = "back_squat",
        [FromForm] string camera_angle = "front_narrow",
        [FromForm] string consent = "false"){
        bool userConsented = consent.Equals("true", StringComparison.OrdinalIgnoreCase);
        var startTime = DateTime.Now;
        try {
            Console.WriteLine($"[.NET] Starting UploadAndVerdict (exercise={exercise}, camera={camera_angle}, videoId={videoId?.ToString() ?? "<none>"})");

            Video? videoReference;

            // 1. Resolve the video. Prefer an existing videoId (set by a prior
            //    POST /Video upload) so we don't re-transfer the bytes. Fall
            //    back to the legacy multipart path for backwards compatibility.
            if (videoId.HasValue){
                videoReference = VideoService.Get(videoId.Value);
                if (videoReference == null){
                    return NotFound($"Video {videoId.Value} not found");
                }
                if (string.IsNullOrEmpty(videoReference.Path)
                    || !System.IO.File.Exists(videoReference.Path)){
                    return StatusCode(410, "Video file is no longer available; please re-upload.");
                }
                // Defence in depth: confirm the stored path is inside the
                // Videos/ root before forwarding it to the Python backend.
                var videosRoot = Path.GetFullPath(Path.Combine(Directory.GetCurrentDirectory(), "Videos"));
                var resolvedPath = Path.GetFullPath(videoReference.Path);
                if (!resolvedPath.StartsWith(videosRoot + Path.DirectorySeparatorChar, StringComparison.Ordinal)
                    && resolvedPath != videosRoot){
                    Console.WriteLine($"[.NET] Refusing to analyze path outside Videos root: {resolvedPath}");
                    return BadRequest("Invalid video path.");
                }
            } else {
                if (video == null){
                    return BadRequest("Either videoId or a multipart video upload is required.");
                }
                var uploadStart = DateTime.Now;
                var upload = this.Create(video) as ObjectResult;
                var uploadTime = (DateTime.Now - uploadStart).TotalSeconds;
                Console.WriteLine($"[.NET] Upload completed in {uploadTime:F2}s");

                if (upload?.StatusCode != 201){
                    return StatusCode(upload?.StatusCode ?? 500, "Upload failed");
                }
                videoReference = (Video?)upload.Value;
                if (videoReference == null){
                    return StatusCode(500, "Video reference is null");
                }
            }

            Console.WriteLine($"[.NET] Analysis target path: {videoReference.Path}");

            // 2. Retrieve verdict (MediaPipe pose estimation)
            var aiStart = DateTime.Now;
            Console.WriteLine($"[.NET] Calling Python backend for AI processing...");
            var verdict = await this.GetAI("", videoReference.Id) as ObjectResult;
            var aiTime = (DateTime.Now - aiStart).TotalSeconds;
            Console.WriteLine($"[.NET] AI processing completed in {aiTime:F2}s");

            if (verdict?.StatusCode != 200){
                var errorMsg = verdict?.Value?.ToString() ?? "Unknown error";
                Console.WriteLine($"[.NET] GetAI failed: {errorMsg}");
                return StatusCode(verdict?.StatusCode ?? 500, errorMsg);
            }

            // 3. Run DTW analysis on the generated landmarks
            var analyzeStart = DateTime.Now;
            Console.WriteLine($"[.NET] Calling Python backend for DTW analysis...");
            var (analyzeStatus, analyzeBody) = await AiClient.Analyze(videoReference.Path!, exercise);
            var analyzeTime = (DateTime.Now - analyzeStart).TotalSeconds;
            Console.WriteLine($"[.NET] DTW analysis completed in {analyzeTime:F2}s");

            if (analyzeStatus < 200 || analyzeStatus >= 300){
                Console.WriteLine($"[.NET] Analyze failed ({analyzeStatus}): {analyzeBody}");
                return StatusCode(analyzeStatus, analyzeBody);
            }

            var totalTime = (DateTime.Now - startTime).TotalSeconds;
            Console.WriteLine($"[.NET] Total UploadAndVerdict time: {totalTime:F2}s");

            // 4. Parse results
            string verdictJson = verdict?.Value?.ToString() ?? "{}";
            string analysisJson = analyzeBody;

            var verdictObj = JsonSerializer.Deserialize<JsonElement>(verdictJson);
            var analysisObj = JsonSerializer.Deserialize<JsonElement>(analysisJson);

            // 5. Data handling based on user consent
            if (userConsented)
            {
                try {
                    int sessionId = await PersistToDatabase(videoReference, exercise, camera_angle, analysisObj);
                    // ---------------------------------------------------------------
                    // FUTURE: Send data to remote database before deleting locally.
                    // await SendToRemoteDatabase(sessionId);
                    // ---------------------------------------------------------------
                    await DeleteSessionData(sessionId);
                    Console.WriteLine($"[.NET] Consent=true: data saved, sent (future), and cleaned up");
                } catch (Exception dbEx) {
                    Console.WriteLine($"[.NET] Data handling warning: {dbEx.Message}");
                }
            }
            else
            {
                Console.WriteLine($"[.NET] Consent=false: no data persisted");
            }

            // 6. Strip embedding fields from response (frontend doesn't need them)
            var analysisDict = JsonSerializer.Deserialize<Dictionary<string, JsonElement>>(analysisJson)
                ?? new Dictionary<string, JsonElement>();
            analysisDict.Remove("embedding_base64");
            analysisDict.Remove("embedding_shape");
            analysisDict.Remove("embedding_feature_names");
            analysisDict.Remove("landmarks_shape");

            var combined = new {
                mediapipe = verdictObj,
                analysis = JsonSerializer.Deserialize<JsonElement>(JsonSerializer.Serialize(analysisDict))
            };

            return Ok(JsonSerializer.Serialize(combined));
        } catch (Exception ex) {
            var totalTime = (DateTime.Now - startTime).TotalSeconds;
            Console.WriteLine($"[.NET] Error in UploadAndVerdict after {totalTime:F2}s: {ex.Message}");
            Console.WriteLine($"[.NET] Stack trace: {ex.StackTrace}");
            // Don't leak exception messages or stack traces to the client.
            return StatusCode(500, "Internal server error");
        }
    }

    private async Task<int> PersistToDatabase(Video videoReference, string exercise, string cameraAngle, JsonElement analysisObj)
    {
        // Read raw landmark .npy file from the shared volume
        var baseName = Path.GetFileNameWithoutExtension(videoReference.Name);
        var landmarkPath = Path.Combine("/app/Landmarks", baseName + "_landmarks.npy");

        byte[] landmarkBytes = [];
        string landmarkShape = "";
        if (System.IO.File.Exists(landmarkPath))
        {
            landmarkBytes = await System.IO.File.ReadAllBytesAsync(landmarkPath);
            Console.WriteLine($"[.NET] Read landmark file: {landmarkPath} ({landmarkBytes.Length} bytes)");
        }
        else
        {
            Console.WriteLine($"[.NET] Landmark file not found: {landmarkPath}");
        }
        if (analysisObj.TryGetProperty("landmarks_shape", out var lmShape))
        {
            landmarkShape = lmShape.GetString() ?? "";
        }

        // Extract embedding from analysis response
        byte[] embeddingBytes = [];
        string embeddingShape = "";
        string featureNames = "";
        if (analysisObj.TryGetProperty("embedding_base64", out var embB64))
        {
            embeddingBytes = Convert.FromBase64String(embB64.GetString() ?? "");
        }
        if (analysisObj.TryGetProperty("embedding_shape", out var embShape))
        {
            embeddingShape = embShape.GetString() ?? "";
        }
        if (analysisObj.TryGetProperty("embedding_feature_names", out var embNames))
        {
            featureNames = embNames.GetString() ?? "";
        }

        // Get rep count from analysis
        int nReps = 0;
        if (analysisObj.TryGetProperty("n_reps", out var nRepsEl))
        {
            nReps = nRepsEl.GetInt32();
        }

        // Build comparison result JSON (strip embedding fields)
        var comparisonDict = JsonSerializer.Deserialize<Dictionary<string, JsonElement>>(analysisObj.GetRawText())
            ?? new Dictionary<string, JsonElement>();
        comparisonDict.Remove("embedding_base64");
        comparisonDict.Remove("embedding_shape");
        comparisonDict.Remove("embedding_feature_names");
        comparisonDict.Remove("landmarks_shape");
        string comparisonJson = JsonSerializer.Serialize(comparisonDict);

        // Create entities
        var session = new Session
        {
            ExerciseType = exercise,
            CameraAngle = cameraAngle,
            NReps = nReps,
            CreatedAt = DateTime.UtcNow.ToString("o")
        };

        var landmark = new LandmarkData
        {
            Data = landmarkBytes,
            Shape = landmarkShape,
            Session = session
        };

        var analysisEntity = new Analysis
        {
            BiomechanicalData = embeddingBytes,
            BiomechanicalShape = embeddingShape,
            FeatureNames = featureNames,
            ComparisonResult = comparisonJson,
            Session = session
        };

        _db.Sessions.Add(session);
        _db.Landmarks.Add(landmark);
        _db.Analyses.Add(analysisEntity);
        await _db.SaveChangesAsync();

        Console.WriteLine($"[.NET] Saved session {session.Id} to database (exercise={exercise}, reps={nReps})");
        return session.Id;
    }

    private async Task DeleteSessionData(int sessionId)
    {
        var analysisEntity = await _db.Analyses.FirstOrDefaultAsync(a => a.SessionId == sessionId);
        if (analysisEntity != null) _db.Analyses.Remove(analysisEntity);

        var landmarkEntity = await _db.Landmarks.FirstOrDefaultAsync(l => l.SessionId == sessionId);
        if (landmarkEntity != null) _db.Landmarks.Remove(landmarkEntity);

        var session = await _db.Sessions.FindAsync(sessionId);
        if (session != null) _db.Sessions.Remove(session);

        await _db.SaveChangesAsync();
        Console.WriteLine($"[.NET] Deleted session {sessionId} data from local database");
    }

    // ---------------------------------------------------------------
    // FUTURE: Implement this when you have a remote PostgreSQL server.
    // private async Task SendToRemoteDatabase(int sessionId)
    // {
    //     var session = await _db.Sessions.FindAsync(sessionId);
    //     var landmark = await _db.Landmarks
    //         .FirstOrDefaultAsync(l => l.SessionId == sessionId);
    //     var analysis = await _db.Analyses
    //         .FirstOrDefaultAsync(a => a.SessionId == sessionId);
    //
    //     // POST to your remote server:
    //     // var payload = new { session, landmark, analysis };
    //     // await _httpClient.PostAsJsonAsync("https://your-server.com/api/data", payload);
    // }
    // ---------------------------------------------------------------

    [HttpPost("cleanup")]
    public IActionResult CleanupVideos([FromBody] JsonElement data){
        // Clean up both original and processed videos
        try{
            if (data.TryGetProperty("videoId", out JsonElement videoIdElement)){
                int videoId = videoIdElement.GetInt32();
                var deleteOriginal = this.Delete(videoId);
            }

            if (data.TryGetProperty("processedPath", out JsonElement pathElement)){
                string? path = pathElement.GetString();
                if (path != null){
                    // Always reduce to a bare filename — DeletePath enforces the ProcessedVideos root.
                    var safeName = Path.GetFileName(path);
                    if (!string.IsNullOrEmpty(safeName)){
                        var deleteProcessed = this.DeletePath(safeName);
                    }
                }
            }
            return NoContent();
        }
        catch (Exception e){
            Console.WriteLine($"[.NET] CleanupVideos exception: {e.Message}");
            return StatusCode(500, "Internal server error");
        }
    }
}