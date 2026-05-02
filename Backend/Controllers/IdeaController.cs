namespace AI_spotter.Controllers;

using System.Text.Json;
using Microsoft.AspNetCore.Mvc;
using AI_spotter.PublicClasses;

[ApiController]
[Route("[controller]/[action]")]
public class IdeaController : ControllerBase
{
    private static readonly object _fileLock = new();
    private static readonly JsonSerializerOptions _jsonOpts = new()
    {
        WriteIndented = true,
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase
    };

    private readonly IWebHostEnvironment _env;

    public IdeaController(IWebHostEnvironment env) => _env = env;

    private string IdeasPath => Path.Combine(_env.ContentRootPath, "Ideas", "ideas.json");

    [HttpPost]
    public IActionResult Submit([FromBody] IdeaSubmission? submission)
    {
        if (submission is null
            || string.IsNullOrWhiteSpace(submission.Title)
            || string.IsNullOrWhiteSpace(submission.Description))
        {
            return BadRequest(new { error = "Title and description are required." });
        }

        // Length caps. ASP.NET model validation also enforces these via the
        // [StringLength] attributes on IdeaSubmission, but we re-check here
        // so the error message is consistent and we never write an oversized
        // record to ideas.json on disk.
        if (submission.Title!.Length > IdeaLimits.TitleMax
            || (submission.Category?.Length ?? 0) > IdeaLimits.CategoryMax
            || (submission.AffectedArea?.Length ?? 0) > IdeaLimits.AffectedAreaMax
            || submission.Description!.Length > IdeaLimits.DescriptionMax
            || (submission.Problem?.Length ?? 0) > IdeaLimits.ProblemMax
            || (submission.Acceptance?.Length ?? 0) > IdeaLimits.AcceptanceMax)
        {
            return BadRequest(new { error = "One or more fields exceed the allowed length." });
        }

        var idea = new Idea
        {
            Id = $"idea-{DateTime.UtcNow:yyyyMMdd-HHmmss}-{Guid.NewGuid().ToString("N")[..6]}",
            SubmittedAt = DateTime.UtcNow,
            Status = "new",
            Title = submission.Title.Trim(),
            Category = (submission.Category ?? "other").Trim(),
            AffectedArea = (submission.AffectedArea ?? "unknown").Trim(),
            Description = submission.Description.Trim(),
            Problem = (submission.Problem ?? string.Empty).Trim(),
            Acceptance = (submission.Acceptance ?? string.Empty).Trim(),
        };

        lock (_fileLock)
        {
            Directory.CreateDirectory(Path.GetDirectoryName(IdeasPath)!);

            List<Idea> ideas;
            if (System.IO.File.Exists(IdeasPath))
            {
                var existing = System.IO.File.ReadAllText(IdeasPath);
                ideas = string.IsNullOrWhiteSpace(existing)
                    ? new List<Idea>()
                    : JsonSerializer.Deserialize<List<Idea>>(existing, _jsonOpts) ?? new List<Idea>();
            }
            else
            {
                ideas = new List<Idea>();
            }

            ideas.Add(idea);
            System.IO.File.WriteAllText(IdeasPath, JsonSerializer.Serialize(ideas, _jsonOpts));
        }

        return Ok(new { id = idea.Id });
    }
}
