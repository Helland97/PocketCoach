namespace AI_spotter.PublicClasses;

public class Idea
{
    public string Id { get; set; } = string.Empty;
    public DateTime SubmittedAt { get; set; }
    public string Status { get; set; } = "new";
    public string Title { get; set; } = string.Empty;
    public string Category { get; set; } = string.Empty;
    public string AffectedArea { get; set; } = string.Empty;
    public string Description { get; set; } = string.Empty;
    public string Problem { get; set; } = string.Empty;
    public string Acceptance { get; set; } = string.Empty;
}

public class IdeaSubmission
{
    public string? Title { get; set; }
    public string? Category { get; set; }
    public string? AffectedArea { get; set; }
    public string? Description { get; set; }
    public string? Problem { get; set; }
    public string? Acceptance { get; set; }
}
