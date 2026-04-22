namespace AI_spotter.Models;

public class LandmarkData
{
    public int Id { get; set; }
    public int SessionId { get; set; }
    public byte[] Data { get; set; } = [];    // Raw .npy bytes
    public string Shape { get; set; } = "";   // e.g. "450,33,4"

    // Navigation property
    public Session? Session { get; set; }
}
