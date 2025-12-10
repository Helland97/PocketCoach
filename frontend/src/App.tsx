import { useState } from "react";
import styles from "./App.module.css"

type Video = {
    id: number;
    path?: string | null;
    name?: string | null;           // stored GUID name
    originalName?: string | null;   // pretty name
};

export default function App() {
    const [video, setVideo] = useState<Video | null>(null);
    const [videoUrl, setVideoUrl] = useState<string>();
    const [verdict, setVerdict] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [busy, setBusy] = useState(false);



    async function handleUploadEl(input: HTMLInputElement) {
        const file = input.files?.[0];
        if (!file) return;
        const fileUrl = URL.createObjectURL(file);
        setVideoUrl(fileUrl);

        const fd = new FormData();
        fd.append("video", file);

        try {
            setBusy(true);
            setError(null);
            setVerdict(null);

            const res = await fetch("/Video", { method: "POST", body: fd });
            if (!res.ok) throw new Error(await res.text());
            const data: Video = await res.json();
            setVideo(data);
        } catch (err: any) {
            setError(err.message ?? String(err));
        } finally {
            input.value = "";
            setBusy(false);
        }
    }

    async function handleAnalysis() {
        try {
            setBusy(true);
            setError(null);

            if (videoUrl){
                const vidRes = await fetch(videoUrl);
                if (!vidRes.ok){
                    throw new Error("Video could not be fetched");
                }
                const vidBlob = await vidRes.blob();

                const formData = new FormData();
                formData.append('video', vidBlob, 'video.mp4');

                const res = await fetch(`/Video/upload`, { method: "POST", body: formData });
                if (!res.ok) throw new Error(await res.text());
                const text = await res.text();
                setVerdict(text);
            }
            else{
                throw new Error("No video is selected");
            }

        } catch (err: any) {
            setError(err.message ?? String(err));
        } finally {
            setBusy(false);
        }
    }

    return (
        <div className={styles.container}>
            <h1 className={styles.title}>Welcome to AI Spotter</h1>
            <h2 className={styles.info} >AI Spotter helps you review and correct lifting technique by uploading a video of
                yourself performing one of the following lifts .... </h2>


            <div className={styles.upload}>
                <input
                    type="file"
                    accept="video/mp4,video/gif"
                    onChange={(e) => handleUploadEl(e.currentTarget)}
                />
            </div>

            {busy && <p>Working…</p>}
            {error && <p style={{ color: "crimson" }}>{error}</p>}

            {video && (
                <div className={verdict ? styles.split : styles.card}>
                    <div className={styles.videoSection}>
                        <div className={styles.card}>
                            <p className={styles.uploadInfo}>
                                <strong>Uploaded:</strong> {video.name}
                            </p>

                            {video?.name && (
                                <div style={{ marginTop: 12 }}>
                                    <video
                                        controls
                                        src={videoUrl}
                                        className={styles.video}
                                    />
                                </div>
                            )}
                            <button
                                onClick={handleAnalysis}
                                disabled={busy}
                                className={styles.button}
                            >
                                Do Analysis
                            </button>
                        </div>
                    </div>

                    {verdict && (
                        <div className={styles.verdictSection}>
                            <div className={styles.verdictBox}>
                                <h2>AI Verdict</h2>
                                <pre className={styles.verdictPre}>
                                    {typeof verdict === "string"
                                        ? JSON.stringify(JSON.parse(verdict), null, 2)
                                        : JSON.stringify(verdict, null, 2)}
                                </pre>

                            </div>
                        </div>
                    )}
                </div>
            )}

        </div>
    )}