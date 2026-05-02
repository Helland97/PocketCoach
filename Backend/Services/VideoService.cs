namespace AI_spotter.Services;
using AI_spotter.Models;

public class VideoService(){
    static List<Video> Videos { get; }

    // Start IDs at 1; no seeded fake entries (the previous "temp/Vid_*"
    // placeholders pointed at nonexistent paths and caused GetAI / Analyze
    // to forward bogus paths to the Python backend).
    static int currId = 1;
    static VideoService(){
        Videos = new List<Video>();
    }

    public static List<Video> GetAll() => Videos;

    public static Video? Get(int id) => Videos.FirstOrDefault<Video>(v => v.Id == id);

    public static void Add(Video video){
        video.Id = currId++;
        Videos.Add(video);
    }

    public static void Update(Video video){
        var prevVid = Videos.Find(v => v.Id == video.Id);
        if (prevVid is null){
            return;
        }
        Videos[Videos.IndexOf(prevVid)] = video;
    }

    public static void Delete(int id){
        Video? video = Get(id);
        if (video is null){
            return;
        }
        Videos.Remove(video);
    }
}
