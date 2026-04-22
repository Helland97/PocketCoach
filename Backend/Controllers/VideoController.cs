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
    Task<string?> Analyze(string path, string exerciseType = "heavy_squat", string template = "front_narrow_template.npz");
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

    public async Task<string?> Analyze(string path, string exerciseType = "heavy_squat", string template = "front_narrow_template.npz"){
        try{
            var url = $"{_pythonBackendUrl}/analyze?path={Uri.EscapeDataString(path)}&exercise_type={exerciseType}&template={template}";
            Console.WriteLine($"[.NET] Calling analyze endpoint: {url}");
            using HttpResponseMessage response = await AiClient.GetAsync(url);
            response.EnsureSuccessStatusCode();
            string responseBody = await response.Content.ReadAsStringAsync();
            Console.WriteLine($"[.NET] Analyze response received");
            return responseBody;
        }
        catch (HttpRequestException e){
            Console.WriteLine($"[.NET] Analyze exception: {e.Message}");
            return null;
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
            string? result = await AiClient.Connect(path);
            if (result != null){
                return Ok(result);
            }
            else{
                return StatusCode(500, "Python backend returned no content");
            }
        }
        catch (HttpRequestException e){
            return (StatusCode(500, ("Internal Server Error {0}", e)));
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
        path = System.IO.Directory.GetParent(System.IO.Directory.GetCurrentDirectory()) + "/" + path;
        if (System.IO.File.Exists(path)){
            System.IO.File.Delete(path);
            return NoContent();
        }
        return StatusCode(500);
    }

    [HttpPost("upload")]
    public async Task<IActionResult> UploadAndVerdict(
        IFormFile video,
        [FromForm] string exercise = "heavy_squat",
        [FromForm] string camera_angle = "front_narrow",
        [FromForm] string consent = "false"){
        bool userConsented = consent.Equals("true", StringComparison.OrdinalIgnoreCase);
        var startTime = DateTime.Now;
        try {
            Console.WriteLine($"[.NET] Starting UploadAndVerdict (exercise={exercise}, camera={camera_angle})");

            // 1. Upload the video
            var uploadStart = DateTime.Now;
            var upload = this.Create(video) as ObjectResult;
            var uploadTime = (DateTime.Now - uploadStart).TotalSeconds;
            Console.WriteLine($"[.NET] Upload completed in {uploadTime:F2}s");

            // Ensure the upload was a success
            if (upload?.StatusCode != 201){
                return StatusCode(upload?.StatusCode ?? 500, "Upload failed");
            }
            Video? videoReference = (Video?)upload.Value;
            if (videoReference == null){
                return StatusCode(500, "Video reference is null");
            }

            Console.WriteLine($"[.NET] Uploaded video path: {videoReference.Path}");

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
            string? analysis = await AiClient.Analyze(videoReference.Path);
            var analyzeTime = (DateTime.Now - analyzeStart).TotalSeconds;
            Console.WriteLine($"[.NET] DTW analysis completed in {analyzeTime:F2}s");

            var totalTime = (DateTime.Now - startTime).TotalSeconds;
            Console.WriteLine($"[.NET] Total UploadAndVerdict time: {totalTime:F2}s");

            // 4. Parse results
            string verdictJson = verdict?.Value?.ToString() ?? "{}";
            string analysisJson = analysis ?? "{}";

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
            return StatusCode(500, $"Error: {ex.Message}");
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
                    var deleteProcessed = this.DeletePath(path);
                }
            }
            return NoContent();
        }
        catch (Exception e){
            return StatusCode(500, e.Message);
        }
    }
}