namespace AI_spotter.PublicClasses;

using System.ComponentModel.DataAnnotations;

// Field length caps — also enforced by IdeaController for clean 400 responses.
// Keep these in sync with the frontend `maxLength` attributes in App.tsx.
public static class IdeaLimits
{
    public const int TitleMax = 200;
    public const int CategoryMax = 64;
    public const int AffectedAreaMax = 64;
    public const int DescriptionMax = 2000;
    public const int ProblemMax = 2000;
    public const int AcceptanceMax = 2000;
}

public class Idea
{
    public string Id { get; set; } = string.Empty;
    public DateTime SubmittedAt { get; set; }
    public string Status { get; set; } = "new";

    [StringLength(IdeaLimits.TitleMax)]
    public string Title { get; set; } = string.Empty;

    [StringLength(IdeaLimits.CategoryMax)]
    public string Category { get; set; } = string.Empty;

    [StringLength(IdeaLimits.AffectedAreaMax)]
    public string AffectedArea { get; set; } = string.Empty;

    [StringLength(IdeaLimits.DescriptionMax)]
    public string Description { get; set; } = string.Empty;

    [StringLength(IdeaLimits.ProblemMax)]
    public string Problem { get; set; } = string.Empty;

    [StringLength(IdeaLimits.AcceptanceMax)]
    public string Acceptance { get; set; } = string.Empty;
}

public class IdeaSubmission
{
    [StringLength(IdeaLimits.TitleMax)]
    public string? Title { get; set; }

    [StringLength(IdeaLimits.CategoryMax)]
    public string? Category { get; set; }

    [StringLength(IdeaLimits.AffectedAreaMax)]
    public string? AffectedArea { get; set; }

    [StringLength(IdeaLimits.DescriptionMax)]
    public string? Description { get; set; }

    [StringLength(IdeaLimits.ProblemMax)]
    public string? Problem { get; set; }

    [StringLength(IdeaLimits.AcceptanceMax)]
    public string? Acceptance { get; set; }
}
