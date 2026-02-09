import { useState, useEffect, useRef } from "react";
import styles from "./App.module.css";

type Video = {
    id: number;
    path?: string | null;
    name?: string | null;           // stored GUID name
    originalName?: string | null;   // pretty name
};

type Exercise = "back_squat" | "front_squat" | "deadlift" | "benchpress" | "military_press";
type CameraAngle = "front" | "back" | "left_side" | "right_side" | "45_front_left" | "45_front_right";

const EXERCISES: { value: Exercise; label: string }[] = [
    { value: "back_squat", label: "Back Squat" },
    { value: "front_squat", label: "Front Squat" },
    { value: "deadlift", label: "Deadlift" },
    { value: "benchpress", label: "Bench Press" },
    { value: "military_press", label: "Military Press" },
];

const CAMERA_ANGLES: { value: CameraAngle; label: string; description: string }[] = [
    { value: "front", label: "Front", description: "Camera facing the athlete" },
    { value: "back", label: "Back", description: "Camera behind the athlete" },
    { value: "left_side", label: "Left Side", description: "Camera on the athlete's left" },
    { value: "right_side", label: "Right Side", description: "Camera on the athlete's right" },
    { value: "45_front_left", label: "45° Front Left", description: "Diagonal from front-left" },
    { value: "45_front_right", label: "45° Front Right", description: "Diagonal from front-right" },
];

export default function App() {
    const [exercise, setExercise] = useState<Exercise | null>(null);
    const [cameraAngle, setCameraAngle] = useState<CameraAngle | null>(null);
    const [video, setVideo] = useState<Video | null>(null);
    const [videoUrl, setVideoUrl] = useState<string>();
    const [processedVideoPath, setProcessedVideoPath] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [busy, setBusy] = useState(false);
    const [analyzing, setAnalyzing] = useState(false);
    const [progress, setProgress] = useState(0);
    const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

    // Poll /progress every 500ms while analyzing
    useEffect(() => {
        if (analyzing) {
            pollRef.current = setInterval(async () => {
                try {
                    const res = await fetch("/progress");
                    if (res.ok) {
                        const data = await res.json();
                        setProgress(data.percent ?? 0);
                    }
                } catch {
                    // backend not reachable yet, ignore
                }
            }, 500);
        } else {
            if (pollRef.current) {
                clearInterval(pollRef.current);
                pollRef.current = null;
            }
            setProgress(0);
        }
        return () => {
            if (pollRef.current) {
                clearInterval(pollRef.current);
                pollRef.current = null;
            }
        };
    }, [analyzing]);

    const currentStep = !exercise ? "exercise" : !cameraAngle ? "angle" : "upload";

    function handleBack() {
        if (currentStep === "angle") {
            setCameraAngle(null);
            setExercise(null);
        } else if (currentStep === "upload") {
            if (video) {
                cleanupVideos(video.id, processedVideoPath || undefined);
            }
            setCameraAngle(null);
            setVideo(null);
            setVideoUrl(undefined);
            setProcessedVideoPath(null);
            setError(null);
        }
    }

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
                formData.append('exercise', exercise!);
                formData.append('camera_angle', cameraAngle!);

                setAnalyzing(true);
                const res = await fetch(`/Video/upload`, { method: "POST", body: formData });
                setAnalyzing(false);
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
            setAnalyzing(false);
            setError(err.message ?? String(err));
        } finally {
            setBusy(false);
        }
    }

    const selectedExerciseLabel = EXERCISES.find(e => e.value === exercise)?.label;
    const selectedAngleLabel = CAMERA_ANGLES.find(a => a.value === cameraAngle)?.label;

    return (
        <div className={styles.container}>
            <h1 className={styles.title}>Welcome to AI Spotter</h1>
            <h2 className={styles.info}>AI Spotter helps you review and correct lifting technique by uploading a video of
                yourself performing one of the following lifts.</h2>

            {/* Step indicator */}
            <div className={styles.steps}>
                <div className={`${styles.step} ${currentStep === "exercise" ? styles.stepActive : styles.stepDone}`}>
                    <span className={styles.stepNumber}>1</span>
                    <span className={styles.stepLabel}>Exercise</span>
                </div>
                <div className={styles.stepDivider} />
                <div className={`${styles.step} ${currentStep === "angle" ? styles.stepActive : currentStep === "upload" ? styles.stepDone : styles.stepPending}`}>
                    <span className={styles.stepNumber}>2</span>
                    <span className={styles.stepLabel}>Camera Angle</span>
                </div>
                <div className={styles.stepDivider} />
                <div className={`${styles.step} ${currentStep === "upload" ? styles.stepActive : styles.stepPending}`}>
                    <span className={styles.stepNumber}>3</span>
                    <span className={styles.stepLabel}>Upload & Analyze</span>
                </div>
            </div>

            {/* Back button */}
            {currentStep !== "exercise" && !busy && (
                <button className={styles.backButton} onClick={handleBack}>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M19 12H5M5 12L12 19M5 12L12 5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                    Back
                </button>
            )}

            {/* Step 1: Exercise Selection */}
            {currentStep === "exercise" && (
                <div className={styles.selectionContainer}>
                    <h3 className={styles.selectionTitle}>Select your exercise</h3>
                    <div className={styles.optionGrid}>
                        {EXERCISES.map((ex) => (
                            <button
                                key={ex.value}
                                className={styles.optionCard}
                                onClick={() => setExercise(ex.value)}
                            >
                                <span className={styles.optionLabel}>{ex.label}</span>
                            </button>
                        ))}
                    </div>
                </div>
            )}

            {/* Step 2: Camera Angle Selection */}
            {currentStep === "angle" && (
                <div className={styles.selectionContainer}>
                    <h3 className={styles.selectionTitle}>
                        Camera angle for <span className={styles.highlight}>{selectedExerciseLabel}</span>
                    </h3>
                    <p className={styles.selectionSubtext}>Where was the camera positioned relative to the athlete?</p>
                    <div className={styles.optionGrid}>
                        {CAMERA_ANGLES.map((angle) => (
                            <button
                                key={angle.value}
                                className={styles.optionCard}
                                onClick={() => setCameraAngle(angle.value)}
                            >
                                <span className={styles.optionLabel}>{angle.label}</span>
                                <span className={styles.optionDesc}>{angle.description}</span>
                            </button>
                        ))}
                    </div>
                </div>
            )}

            {/* Step 3: Upload & Analysis */}
            {currentStep === "upload" && (
                <>
                    {/* Selected config summary */}
                    <div className={styles.configSummary}>
                        <span className={styles.configTag}>{selectedExerciseLabel}</span>
                        <span className={styles.configTag}>{selectedAngleLabel}</span>
                    </div>

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
                                            <p className={styles.buttonLoadingText}>
                                                {analyzing ? `Analyzing video... ${progress}%` : "Uploading video..."}
                                            </p>
                                            <div className={styles.progressTrack}>
                                                <div
                                                    className={styles.progressFill}
                                                    style={{ width: analyzing ? `${progress}%` : undefined }}
                                                />
                                            </div>
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
                </>
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
