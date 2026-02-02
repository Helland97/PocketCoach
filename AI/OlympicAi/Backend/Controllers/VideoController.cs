namespace AI_spotter.Controllers;

using AI_spotter.Models;
using AI_spotter.Services;
using Microsoft.AspNetCore.Mvc;
using AI_spotter.PublicClasses;
using System.Net.Http;
using System.Text.Json;

public interface IAiClientConnect{
    HttpClient AiClient {get;}
    Task<string?> Connect(string path);
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
}

[ApiController]
[Route("[controller]")]
public class VideoController : ControllerBase{
    private readonly IAiClientConnect AiClient;
    UploadHandler handleHerVideo = new UploadHandler();

    public VideoController(IAiClientConnect aiClient){
        AiClient = aiClient;
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
    public async Task<IActionResult> UploadAndVerdict(IFormFile video){
        var startTime = DateTime.Now;
        try {
            Console.WriteLine($"[.NET] Starting UploadAndVerdict");

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

            // 2. Retrieve verdict
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

            var totalTime = (DateTime.Now - startTime).TotalSeconds;
            Console.WriteLine($"[.NET] Total UploadAndVerdict time: {totalTime:F2}s");
            Console.WriteLine($"[.NET] Verdict: {verdict.Value}");

            // 3. Return verdict (deletion will be handled by frontend when needed)
            return verdict?.Value != null ? Ok(verdict.Value) : StatusCode(500, "Verdict is null");
        } catch (Exception ex) {
            var totalTime = (DateTime.Now - startTime).TotalSeconds;
            Console.WriteLine($"[.NET] Error in UploadAndVerdict after {totalTime:F2}s: {ex.Message}");
            Console.WriteLine($"[.NET] Stack trace: {ex.StackTrace}");
            return StatusCode(500, $"Error: {ex.Message}");
        }
    }

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