namespace AI_spotter.Models;

public class Session
{
    public int Id { get; set; }
    public string ExerciseType { get; set; } = "";
    public string CameraAngle { get; set; } = "";
    public int NReps { get; set; }
    public string CreatedAt { get; set; } = "";

    // Navigation properties
    public LandmarkData? Landmark { get; set; }
    public Analysis? Analysis { get; set; }
}
