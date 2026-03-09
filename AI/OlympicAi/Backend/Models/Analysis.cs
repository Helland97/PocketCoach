namespace AI_spotter.Models;

public class Analysis
{
    public int Id { get; set; }
    public int SessionId { get; set; }
    public byte[] BiomechanicalData { get; set; } = [];   // Embedding .npy bytes (angles, velocity, symmetry, depth)
    public string BiomechanicalShape { get; set; } = "";   // e.g. "449,29"
    public string FeatureNames { get; set; } = "";         // JSON array of feature name strings
    public string ComparisonResult { get; set; } = "";     // Full DTW verdict as JSON

    // Navigation property
    public Session? Session { get; set; }
}
