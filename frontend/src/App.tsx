import { useState } from "react";
import styles from "./App.module.css";

type Video = {
    id: number;
    path?: string | null;
    name?: string | null;           // stored GUID name
    originalName?: string | null;   // pretty name
};

export default function App() {
    const [video, setVideo] = useState<Video | null>(null);
    const [videoUrl, setVideoUrl] = useState<string>();
    const [processedVideoPath, setProcessedVideoPath] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [busy, setBusy] = useState(false);

    async function cleanupVideos(videoId?: number, processedPath?: string) {
        try {
            await fetch("/Video/cleanup", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    videoId: videoId,
                    processedPath: processedPath
                })
            });
        } catch (err) {
            console.error("Cleanup failed:", err);
        }
    }

    async function handleUploadEl(input: HTMLInputElement) {
        const file = input.files?.[0];
        if (!file) return;

        // Cleanup previous videos before uploading new one
        if (video?.id) {
            await cleanupVideos(video.id, processedVideoPath || undefined);
        }

        const fileUrl = URL.createObjectURL(file);
        setVideoUrl(fileUrl);
        setProcessedVideoPath(null);

        const fd = new FormData();
        fd.append("video", file);

        try {
            setBusy(true);
            setError(null);

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

                // Parse verdict to get processed video path
                const verdictData = JSON.parse(text);
                if (verdictData.path) {
                    setProcessedVideoPath(verdictData.path);
                    // Update video URL to point to processed video (relative URL works in both dev and production)
                    setVideoUrl(`/view_processed/${encodeURIComponent(verdictData.path)}`);
                }
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


            {!video ? (
                busy ? (
                    <div className={styles.uploadingContainer}>
                        <div className={styles.spinner}></div>
                        <p className={styles.loadingText}>Uploading video...</p>
                    </div>
                ) : (
                    <div className={styles.upload}>
                        <label htmlFor="file-upload" className={styles.uploadLabel}>
                            <svg className={styles.uploadIcon} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                                <path d="M7 18C4.23858 18 2 15.7614 2 13C2 10.2386 4.23858 8 7 8C7.33526 5.59791 9.45642 4 12 4C14.7614 4 17 6.23858 17 9C19.7614 9 22 11.2386 22 14C22 16.7614 19.7614 19 17 19H7Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                                <path d="M12 12V21M12 12L9 15M12 12L15 15" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                            </svg>
                            <span className={styles.uploadText}>Choose Video File</span>
                            <span className={styles.uploadSubtext}>MP4 or GIF format</span>
                        </label>
                        <input
                            id="file-upload"
                            type="file"
                            accept="video/mp4,video/gif"
                            onChange={(e) => handleUploadEl(e.currentTarget)}
                            className={styles.uploadInput}
                        />
                    </div>
                )
            ) : (
                <div className={styles.singleVideoContainer}>
                    <div className={styles.videoSection}>
                        <div className={styles.card}>
                            <div className={styles.cardHeader}>
                                <p className={styles.uploadInfo}>
                                    <strong>{processedVideoPath ? 'Processed:' : 'Uploaded:'}</strong>{' '}
                                    {processedVideoPath
                                        ? processedVideoPath.split('\\').pop()?.split('/').pop()
                                        : video.name}
                                </p>
                                <label htmlFor="file-upload-new" className={styles.uploadNewButton}>
                                    <svg className={styles.uploadNewIcon} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                                        <path d="M7 18C4.23858 18 2 15.7614 2 13C2 10.2386 4.23858 8 7 8C7.33526 5.59791 9.45642 4 12 4C14.7614 4 17 6.23858 17 9C19.7614 9 22 11.2386 22 14C22 16.7614 19.7614 19 17 19H7Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                                        <path d="M12 12V21M12 12L9 15M12 12L15 15" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                                    </svg>
                                    Upload New
                                </label>
                                <input
                                    id="file-upload-new"
                                    type="file"
                                    accept="video/mp4,video/gif"
                                    onChange={(e) => handleUploadEl(e.currentTarget)}
                                    className={styles.uploadInput}
                                />
                            </div>

                            {videoUrl && (
                                <div style={{ marginTop: 12 }}>
                                    <video
                                        key={videoUrl}
                                        controls
                                        src={videoUrl}
                                        className={styles.video}
                                    />
                                </div>
                            )}

                            {busy ? (
                                <div className={styles.buttonLoadingContainer}>
                                    <div className={styles.buttonSpinner}></div>
                                    <p className={styles.buttonLoadingText}>Analyzing video...</p>
                                </div>
                            ) : !processedVideoPath ? (
                                <button
                                    onClick={handleAnalysis}
                                    className={styles.button}
                                >
                                    Do Analysis
                                </button>
                            ) : null}
                        </div>
                    </div>
                </div>
            )}

            {error && (
                <div className={styles.errorContainer}>
                    <svg className={styles.errorIcon} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2"/>
                        <path d="M12 8V12M12 16H12.01" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                    </svg>
                    <p className={styles.errorText}>{error}</p>
                </div>
            )}

        </div>
    )}
