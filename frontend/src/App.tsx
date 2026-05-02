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

type FeatureResult = {
    feature: string;
    correlation: number;
    mae_degrees: number;
    combined_score: number;
    is_core: boolean;
};

type RepResult = {
    rep_number: number;
    core_similarity: number;
    depth_score: number;
    user_flexion: number;
    template_flexion: number;
    hit_parallel: boolean;
    per_feature: FeatureResult[];
    feedback: string;
};

type AnalysisResult = {
    n_reps: number;
    average_core_similarity: number;
    average_depth_score: number;
    reps: RepResult[];
};

function gradeFor(score: number): { letter: string; className: string } {
    if (score > 0.80) return { letter: "A", className: "gradeA" };
    if (score > 0.60) return { letter: "B", className: "gradeB" };
    if (score > 0.40) return { letter: "C", className: "gradeC" };
    if (score > 0.20) return { letter: "D", className: "gradeD" };
    return { letter: "F", className: "gradeF" };
}

function formatFeatureName(name: string): string {
    return name
        .replace(/_/g, " ")
        .replace(/\b\w/g, c => c.toUpperCase());
}

function getImprovementTips(rep: RepResult): string[] {
    const tips: string[] = [];

    const problemFeatures = rep.per_feature
        .filter(f => f.is_core && f.combined_score < 0.80)
        .sort((a, b) => a.combined_score - b.combined_score);

    for (const f of problemFeatures) {
        const name = f.feature.toLowerCase();
        if (name.includes("knee")) {
            if (f.mae_degrees > 15) {
                tips.push(`Your knee angle differs significantly (${f.mae_degrees.toFixed(1)}° off). Focus on controlling squat depth and keeping a consistent knee bend throughout the movement.`);
            } else {
                tips.push(`Knee tracking is slightly off (${f.mae_degrees.toFixed(1)}° off). Focus on pushing your knees over your toes and maintaining alignment.`);
            }
        } else if (name.includes("hip")) {
            tips.push(`Hip hinge pattern differs from the template (${f.mae_degrees.toFixed(1)}° off). Practice hip mobility and focus on initiating the movement by pushing your hips back.`);
        } else if (name.includes("trunk")) {
            tips.push(`Trunk angle is off by ${f.mae_degrees.toFixed(1)}°. Focus on keeping your chest up and maintaining a neutral spine throughout the lift.`);
        } else {
            tips.push(`${formatFeatureName(f.feature)} movement pattern differs (${f.mae_degrees.toFixed(1)}° off). Try to match the pro's range of motion more closely.`);
        }
    }

    if (!rep.hit_parallel) {
        tips.push("You did not hit parallel on this rep. Try to squat deeper by working on hip and ankle mobility.");
    }

    if (rep.depth_score < 80) {
        tips.push(`Depth score is ${Math.round(rep.depth_score)}/100. The pro template goes deeper — focus on increasing your range of motion gradually.`);
    }

    if (tips.length === 0) {
        tips.push("Great form on this rep! Keep up the consistent technique.");
    }

    return tips;
}

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

// --- Data consent helpers (persists across sessions) ---
const CONSENT_KEY = "ai_spotter_data_consent";

function getStoredConsent(): boolean | null {
    const val = localStorage.getItem(CONSENT_KEY);
    if (val === "true") return true;
    if (val === "false") return false;
    return null; // never asked
}

function setStoredConsent(value: boolean) {
    localStorage.setItem(CONSENT_KEY, String(value));
}

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
    const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
    const [expandedReps, setExpandedReps] = useState<Set<number>>(new Set());
    const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const [dataConsent, setDataConsent] = useState<boolean | null>(getStoredConsent);
    const showConsentModal = dataConsent === null;
    const [showSettings, setShowSettings] = useState(false);
    const [showBugReport, setShowBugReport] = useState(false);
    const [bugDescription, setBugDescription] = useState("");
    const [bugSubmitted, setBugSubmitted] = useState(false);
    const [showIdeaReport, setShowIdeaReport] = useState(false);
    const [ideaTitle, setIdeaTitle] = useState("");
    const [ideaCategory, setIdeaCategory] = useState("new feature");
    const [ideaAffectedArea, setIdeaAffectedArea] = useState("not sure");
    const [ideaDescription, setIdeaDescription] = useState("");
    const [ideaProblem, setIdeaProblem] = useState("");
    const [ideaAcceptance, setIdeaAcceptance] = useState("");
    const [ideaSubmitted, setIdeaSubmitted] = useState(false);
    const [ideaError, setIdeaError] = useState<string | null>(null);

    async function submitIdea() {
        try {
            setIdeaError(null);
            const res = await fetch("/Idea/submit", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    title: ideaTitle,
                    category: ideaCategory,
                    affectedArea: ideaAffectedArea,
                    description: ideaDescription,
                    problem: ideaProblem,
                    acceptance: ideaAcceptance,
                }),
            });
            if (!res.ok) {
                throw new Error((await res.text()) || "Submission failed");
            }
            setIdeaSubmitted(true);
            setIdeaTitle("");
            setIdeaCategory("new feature");
            setIdeaAffectedArea("not sure");
            setIdeaDescription("");
            setIdeaProblem("");
            setIdeaAcceptance("");
        } catch (err) {
            setIdeaError(err instanceof Error ? err.message : String(err));
        }
    }

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
            setAnalysis(null);
            setExpandedReps(new Set());
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
        setAnalysis(null);
        setExpandedReps(new Set());

        const fd = new FormData();
        fd.append("video", file);

        try {
            setBusy(true);
            setError(null);

            const res = await fetch("/Video", { method: "POST", body: fd });
            if (!res.ok) throw new Error(await res.text());
            const data: Video = await res.json();
            setVideo(data);
        } catch (err) {
            setError(err instanceof Error ? err.message : String(err));
        } finally {
            input.value = "";
            setBusy(false);
        }
    }

    async function handleAnalysis() {
        try {
            setBusy(true);
            setError(null);

            if (video?.id){
                // Reference the already-uploaded video by id — do not
                // re-transfer the blob. The backend looks up the stored
                // file under its Videos/ mount and forwards the server-side
                // path to the Python backend.
                const formData = new FormData();
                formData.append('videoId', String(video.id));
                formData.append('exercise', exercise!);
                formData.append('camera_angle', cameraAngle!);
                formData.append('consent', String(dataConsent === true));

                setAnalyzing(true);
                const res = await fetch(`/Video/upload`, { method: "POST", body: formData });
                setAnalyzing(false);
                if (!res.ok) throw new Error(await res.text());
                const text = await res.text();

                // Parse combined response: { mediapipe: {...}, analysis: {...} }
                const combined = JSON.parse(text);
                const mediapipe = combined.mediapipe;
                const analysisData = combined.analysis;

                if (mediapipe?.path) {
                    setProcessedVideoPath(mediapipe.path);
                    setVideoUrl(`/view_processed/${encodeURIComponent(mediapipe.path)}`);
                }

                if (analysisData?.n_reps != null) {
                    setAnalysis(analysisData);
                }
            }
            else{
                throw new Error("No video is selected");
            }

        } catch (err) {
            setAnalyzing(false);
            setError(err instanceof Error ? err.message : String(err));
        } finally {
            setBusy(false);
        }
    }

    const selectedExerciseLabel = EXERCISES.find(e => e.value === exercise)?.label;
    const selectedAngleLabel = CAMERA_ANGLES.find(a => a.value === cameraAngle)?.label;

    function handleConsent(accepted: boolean) {
        setStoredConsent(accepted);
        setDataConsent(accepted);
    }

    if (showConsentModal) {
        return (
            <div className={styles.container}>
                <div className={styles.consentModal}>
                    <h2 className={styles.consentTitle}>Help Us Improve</h2>
                    <p className={styles.consentText}>
                        AI Spotter can collect anonymized movement data to improve our exercise analysis models.
                        No videos are stored — only skeleton joint data and analysis results.
                    </p>
                    <p className={styles.consentText}>
                        You can change this at any time in the app settings.
                    </p>
                    <div className={styles.consentButtons}>
                        <button
                            className={styles.consentAccept}
                            onClick={() => handleConsent(true)}
                        >
                            Accept
                        </button>
                        <button
                            className={styles.consentDecline}
                            onClick={() => handleConsent(false)}
                        >
                            Decline
                        </button>
                    </div>
                </div>
            </div>
        );
    }

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

                            {/* Analysis Error */}
                            {!analysis && error && (
                                <div className={styles.analysisError}>
                                    <div className={styles.analysisErrorIcon}>
                                        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                                            <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="1.5"/>
                                            <path d="M12 8V13" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                                            <circle cx="12" cy="16.5" r="1" fill="currentColor"/>
                                        </svg>
                                    </div>
                                    <h3 className={styles.analysisErrorTitle}>Analysis Failed</h3>
                                    <p className={styles.analysisErrorMessage}>
                                        {error.toLowerCase().includes("pose") || error.toLowerCase().includes("landmark")
                                            ? "We couldn't detect a person in this video. The AI was unable to track body landmarks in any of the frames."
                                            : error.toLowerCase().includes("no reps") || error.toLowerCase().includes("n_reps")
                                            ? "No repetitions were detected in this video. Make sure the full exercise movement is visible."
                                            : "Something went wrong while analyzing your video."}
                                    </p>
                                    <div className={styles.analysisErrorTips}>
                                        <p className={styles.analysisErrorTipsLabel}>Tips for a better result:</p>
                                        <ul>
                                            <li>Make sure your full body is visible in the frame</li>
                                            <li>Use good lighting so the camera can see you clearly</li>
                                            <li>Avoid busy or cluttered backgrounds</li>
                                            <li>Keep the camera steady and at a reasonable distance</li>
                                        </ul>
                                    </div>
                                    <button
                                        className={styles.button}
                                        onClick={() => { setError(null); setProcessedVideoPath(null); }}
                                        style={{ marginTop: "0.5rem" }}
                                    >
                                        Try Another Video
                                    </button>
                                </div>
                            )}

                            {/* Verdict Display */}
                            {analysis && (
                                <div className={styles.verdictContainer}>
                                    <h3 className={styles.verdictTitle}>Analysis Results</h3>

                                    {/* Overall Summary */}
                                    <div className={styles.summaryRow}>
                                        <div className={styles.summaryCard}>
                                            <span className={styles.summaryValue}>
                                                {Math.round(analysis.average_core_similarity * 100)}%
                                            </span>
                                            <span className={styles.summaryLabel}>Core Similarity</span>
                                        </div>
                                        <div className={styles.summaryCard}>
                                            <span className={styles.summaryValue}>
                                                {Math.round(analysis.average_depth_score)}/100
                                            </span>
                                            <span className={styles.summaryLabel}>Depth Score</span>
                                        </div>
                                        <div className={styles.summaryCard}>
                                            <span className={styles.summaryValue}>{analysis.n_reps}</span>
                                            <span className={styles.summaryLabel}>Reps Detected</span>
                                        </div>
                                    </div>

                                    {/* Per-Rep Breakdown */}
                                    {analysis.reps.map((rep) => {
                                        const coreGrade = gradeFor(rep.core_similarity);
                                        const isExpanded = expandedReps.has(rep.rep_number);
                                        const tips = getImprovementTips(rep);
                                        return (
                                            <div key={rep.rep_number} className={styles.repCard}>
                                                <div className={styles.repHeader}>
                                                    <span className={styles.repTitle}>Rep {rep.rep_number}</span>
                                                    <span className={`${styles.repGrade} ${styles[coreGrade.className]}`}>
                                                        {coreGrade.letter}
                                                    </span>
                                                </div>

                                                <div className={styles.repStats}>
                                                    <span>Similarity: {Math.round(rep.core_similarity * 100)}%</span>
                                                    <span>Depth: {Math.round(rep.depth_score)}/100</span>
                                                    <span>Parallel: {rep.hit_parallel ? "Yes" : "No"}</span>
                                                </div>

                                                {/* Core features table */}
                                                <table className={styles.featureTable}>
                                                    <thead>
                                                        <tr>
                                                            <th>Joint</th>
                                                            <th>Score</th>
                                                            <th>Grade</th>
                                                        </tr>
                                                    </thead>
                                                    <tbody>
                                                        {rep.per_feature
                                                            .filter(f => f.is_core)
                                                            .map(f => {
                                                                const g = gradeFor(f.combined_score);
                                                                return (
                                                                    <tr key={f.feature}>
                                                                        <td>{formatFeatureName(f.feature)}</td>
                                                                        <td>{Math.round(f.combined_score * 100)}%</td>
                                                                        <td><span className={`${styles.badge} ${styles[g.className]}`}>{g.letter}</span></td>
                                                                    </tr>
                                                                );
                                                            })}
                                                    </tbody>
                                                </table>

                                                {/* Expand / Collapse button */}
                                                <button
                                                    className={styles.detailToggle}
                                                    onClick={() => setExpandedReps(prev => {
                                                        const next = new Set(prev);
                                                        if (next.has(rep.rep_number)) next.delete(rep.rep_number);
                                                        else next.add(rep.rep_number);
                                                        return next;
                                                    })}
                                                >
                                                    <svg
                                                        className={`${styles.detailToggleIcon} ${isExpanded ? styles.detailToggleIconOpen : ""}`}
                                                        width="18" height="18" viewBox="0 0 24 24" fill="none"
                                                        xmlns="http://www.w3.org/2000/svg"
                                                    >
                                                        <path d="M9 5l7 7-7 7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                                                    </svg>
                                                    {isExpanded ? "Hide Details" : "In-Depth Analysis"}
                                                </button>

                                                {/* Expanded detail section */}
                                                {isExpanded && (
                                                    <div className={styles.detailSection}>
                                                        {/* Improvement tips */}
                                                        <div className={styles.tipsContainer}>
                                                            <h4 className={styles.tipsTitle}>What to Improve</h4>
                                                            <ul className={styles.tipsList}>
                                                                {tips.map((tip, idx) => (
                                                                    <li key={idx} className={styles.tipItem}>{tip}</li>
                                                                ))}
                                                            </ul>
                                                        </div>

                                                        {/* Full feature breakdown */}
                                                        <h4 className={styles.detailSubtitle}>All Joint Metrics</h4>
                                                        <table className={styles.featureTable}>
                                                            <thead>
                                                                <tr>
                                                                    <th>Joint</th>
                                                                    <th>Score</th>
                                                                    <th>MAE</th>
                                                                    <th>Grade</th>
                                                                </tr>
                                                            </thead>
                                                            <tbody>
                                                                {rep.per_feature.map(f => {
                                                                    const g = gradeFor(f.combined_score);
                                                                    return (
                                                                        <tr key={f.feature} className={f.is_core ? styles.coreRow : ""}>
                                                                            <td>
                                                                                {formatFeatureName(f.feature)}
                                                                                {f.is_core && <span className={styles.coreTag}>core</span>}
                                                                            </td>
                                                                            <td>{Math.round(f.combined_score * 100)}%</td>
                                                                            <td>{f.mae_degrees.toFixed(1)}°</td>
                                                                            <td><span className={`${styles.badge} ${styles[g.className]}`}>{g.letter}</span></td>
                                                                        </tr>
                                                                    );
                                                                })}
                                                            </tbody>
                                                        </table>

                                                        {/* Depth comparison */}
                                                        <div className={styles.depthComparison}>
                                                            <span>Your max flexion: <strong>{rep.user_flexion.toFixed(1)}°</strong></span>
                                                            <span>Pro template: <strong>{rep.template_flexion.toFixed(1)}°</strong></span>
                                                        </div>
                                                    </div>
                                                )}
                                            </div>
                                        );
                                    })}
                                </div>
                            )}
                        </div>
                    )}
                </>
            )}

            {error && !video && (
                <div className={styles.errorContainer}>
                    <svg className={styles.errorIcon} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2"/>
                        <path d="M12 8V12M12 16H12.01" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                    </svg>
                    <p className={styles.errorText}>{error}</p>
                </div>
            )}

            {/* Settings gear button (top-right) */}
            <button
                className={styles.settingsButton}
                onClick={() => setShowSettings(!showSettings)}
                title="Settings"
            >
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M12 15a3 3 0 100-6 3 3 0 000 6z" stroke="currentColor" strokeWidth="1.5"/>
                    <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 01-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09a1.65 1.65 0 00-1.08-1.51 1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09a1.65 1.65 0 001.51-1.08 1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06a1.65 1.65 0 001.82.33H9a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1.08z" stroke="currentColor" strokeWidth="1.5"/>
                </svg>
            </button>

            {/* Settings panel */}
            {showSettings && (
                <div className={styles.settingsPanel}>
                    <div className={styles.settingsPanelHeader}>
                        <h3 className={styles.settingsPanelTitle}>Settings</h3>
                        <button className={styles.settingsClose} onClick={() => setShowSettings(false)}>
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none"><path d="M18 6L6 18M6 6l12 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/></svg>
                        </button>
                    </div>
                    <div className={styles.settingsRow}>
                        <div className={styles.settingsLabel}>
                            <span className={styles.settingsLabelText}>Share movement data</span>
                            <span className={styles.settingsLabelDesc}>Help improve our AI models with anonymized joint data</span>
                        </div>
                        <button
                            className={`${styles.toggle} ${dataConsent ? styles.toggleOn : ""}`}
                            onClick={() => handleConsent(!dataConsent)}
                            role="switch"
                            aria-checked={dataConsent === true}
                        >
                            <span className={styles.toggleKnob} />
                        </button>
                    </div>
                </div>
            )}

            {/* Idea report button (bottom-right, stacked above bug button) */}
            <button
                className={styles.ideaButton}
                onClick={() => {
                    setShowIdeaReport(true);
                    setIdeaSubmitted(false);
                    setIdeaError(null);
                }}
                title="Report an idea or improvement"
            >
                <svg className={styles.ideaIcon} width="22" height="22" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    {/* Lightbulb */}
                    <path d="M9 18h6M10 21h4M12 3a7 7 0 00-4 12.7c.6.4 1 1.1 1 1.8V18h6v-.5c0-.7.4-1.4 1-1.8A7 7 0 0012 3z" stroke="#f5c518" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
                    <path d="M12 7v4" stroke="#f5c518" strokeWidth="1.6" strokeLinecap="round"/>
                </svg>
                <span className={styles.ideaLabel}>Report an idea/improvement</span>
            </button>

            {/* Idea report modal */}
            {showIdeaReport && (
                <div className={styles.bugOverlay} onClick={() => setShowIdeaReport(false)}>
                    <div className={styles.ideaModal} onClick={e => e.stopPropagation()}>
                        <div className={styles.settingsPanelHeader}>
                            <h3 className={styles.settingsPanelTitle}>Report an Idea or Improvement</h3>
                            <button className={styles.settingsClose} onClick={() => setShowIdeaReport(false)}>
                                <svg width="18" height="18" viewBox="0 0 24 24" fill="none"><path d="M18 6L6 18M6 6l12 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/></svg>
                            </button>
                        </div>

                        {ideaSubmitted ? (
                            <div className={styles.bugSuccess}>
                                <svg width="48" height="48" viewBox="0 0 24 24" fill="none">
                                    <circle cx="12" cy="12" r="10" stroke="#27ae60" strokeWidth="1.5"/>
                                    <path d="M8 12l3 3 5-5" stroke="#27ae60" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                                </svg>
                                <p>Thanks! Your idea was saved for review.</p>
                            </div>
                        ) : (
                            <>
                                <p className={styles.bugFormDesc}>
                                    Have a new feature in mind, or know how an existing one could be better? Fill in as much as you can — more detail means faster action.
                                </p>

                                <div className={styles.ideaField}>
                                    <label className={styles.ideaFieldLabel}>Title</label>
                                    <input
                                        type="text"
                                        className={styles.ideaInput}
                                        placeholder="One-line summary (e.g. Add deadlift 45° back-right camera angle)"
                                        value={ideaTitle}
                                        onChange={e => setIdeaTitle(e.target.value)}
                                        maxLength={120}
                                    />
                                </div>

                                <div className={styles.ideaField}>
                                    <label className={styles.ideaFieldLabel}>Category</label>
                                    <select
                                        className={styles.ideaInput}
                                        value={ideaCategory}
                                        onChange={e => setIdeaCategory(e.target.value)}
                                    >
                                        <option value="new feature">New feature</option>
                                        <option value="UI/UX improvement">UI / UX improvement</option>
                                        <option value="analysis accuracy">Analysis accuracy</option>
                                        <option value="performance">Performance</option>
                                        <option value="exercise/camera support">Exercise or camera support</option>
                                        <option value="other">Other</option>
                                    </select>
                                </div>

                                <div className={styles.ideaField}>
                                    <label className={styles.ideaFieldLabel}>
                                        Affected area <span className={styles.ideaOptional}>(optional)</span>
                                    </label>
                                    <select
                                        className={styles.ideaInput}
                                        value={ideaAffectedArea}
                                        onChange={e => setIdeaAffectedArea(e.target.value)}
                                    >
                                        <option value="not sure">Not sure</option>
                                        <option value="frontend">Frontend (UI)</option>
                                        <option value="dotnet-backend">.NET backend</option>
                                        <option value="python-backend">Python backend / AI</option>
                                        <option value="cross-cutting">Cross-cutting</option>
                                        <option value="infrastructure/docker">Infrastructure / Docker</option>
                                    </select>
                                </div>

                                <div className={styles.ideaField}>
                                    <label className={styles.ideaFieldLabel}>Description</label>
                                    <textarea
                                        className={styles.bugTextarea}
                                        placeholder="Describe the idea in detail — what should it do?"
                                        value={ideaDescription}
                                        onChange={e => setIdeaDescription(e.target.value)}
                                        rows={4}
                                    />
                                </div>

                                <div className={styles.ideaField}>
                                    <label className={styles.ideaFieldLabel}>
                                        Problem / motivation <span className={styles.ideaOptional}>(optional)</span>
                                    </label>
                                    <textarea
                                        className={styles.bugTextarea}
                                        placeholder="What pain point does this solve? Why does it matter?"
                                        value={ideaProblem}
                                        onChange={e => setIdeaProblem(e.target.value)}
                                        rows={3}
                                    />
                                </div>

                                <div className={styles.ideaField}>
                                    <label className={styles.ideaFieldLabel}>
                                        Acceptance criteria <span className={styles.ideaOptional}>(optional)</span>
                                    </label>
                                    <textarea
                                        className={styles.bugTextarea}
                                        placeholder="How will we know this is done? (e.g. deadlift is selectable; analysis under 30s; rep card shows tempo)"
                                        value={ideaAcceptance}
                                        onChange={e => setIdeaAcceptance(e.target.value)}
                                        rows={3}
                                    />
                                </div>

                                {ideaError && (
                                    <p className={styles.ideaErrorText}>{ideaError}</p>
                                )}

                                <button
                                    className={styles.bugSubmit}
                                    disabled={ideaTitle.trim().length === 0 || ideaDescription.trim().length === 0}
                                    onClick={submitIdea}
                                >
                                    Submit Idea
                                </button>
                            </>
                        )}
                    </div>
                </div>
            )}

            {/* Bug report button (bottom-right) */}
            <button
                className={styles.bugButton}
                onClick={() => { setShowBugReport(true); setBugSubmitted(false); setBugDescription(""); }}
                title="Report a bug"
            >
                <svg className={styles.bugIcon} width="22" height="22" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    {/* Legs */}
                    <path d="M5.5 10.5L2.5 8.5M5.5 14L2.5 16M5.5 17.5L3.5 20.5M18.5 10.5L21.5 8.5M18.5 14L21.5 16M18.5 17.5L20.5 20.5" stroke="#888" strokeWidth="1.3" strokeLinecap="round"/>
                    {/* Body */}
                    <ellipse cx="12" cy="15" rx="5.5" ry="6" fill="#3d2b1a"/>
                    {/* Wing split */}
                    <line x1="12" y1="9.5" x2="12" y2="21" stroke="#2a1d10" strokeWidth="0.8"/>
                    {/* Wing shells (elytra) */}
                    <path d="M6.5 15c0-3 2.5-5.5 5.5-5.5v11c-3 0-5.5-2.5-5.5-5.5z" fill="#c0392b"/>
                    <path d="M17.5 15c0-3-2.5-5.5-5.5-5.5v11c3 0 5.5-2.5 5.5-5.5z" fill="#e74c3c"/>
                    {/* Spots */}
                    <circle cx="9.5" cy="13" r="0.9" fill="#2c1810"/>
                    <circle cx="10" cy="16.5" r="0.8" fill="#2c1810"/>
                    <circle cx="14.5" cy="13" r="0.9" fill="#2c1810"/>
                    <circle cx="14" cy="16.5" r="0.8" fill="#2c1810"/>
                    {/* Head */}
                    <ellipse cx="12" cy="8.5" rx="3" ry="2.2" fill="#1a1a1a"/>
                    {/* Antennae */}
                    <path d="M10 7L8 4.5M14 7L16 4.5" stroke="#1a1a1a" strokeWidth="1.2" strokeLinecap="round"/>
                    <circle cx="7.7" cy="4" r="0.7" fill="#1a1a1a"/>
                    <circle cx="16.3" cy="4" r="0.7" fill="#1a1a1a"/>
                    {/* Eyes */}
                    <circle cx="10.5" cy="8" r="0.7" fill="#fff"/>
                    <circle cx="13.5" cy="8" r="0.7" fill="#fff"/>
                </svg>
                <span className={styles.bugLabel}>Report a bug</span>
            </button>

            {/* Bug report modal */}
            {showBugReport && (
                <div className={styles.bugOverlay} onClick={() => setShowBugReport(false)}>
                    <div className={styles.bugModal} onClick={e => e.stopPropagation()}>
                        <div className={styles.settingsPanelHeader}>
                            <h3 className={styles.settingsPanelTitle}>Report a Bug</h3>
                            <button className={styles.settingsClose} onClick={() => setShowBugReport(false)}>
                                <svg width="18" height="18" viewBox="0 0 24 24" fill="none"><path d="M18 6L6 18M6 6l12 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/></svg>
                            </button>
                        </div>

                        {bugSubmitted ? (
                            <div className={styles.bugSuccess}>
                                <svg width="48" height="48" viewBox="0 0 24 24" fill="none">
                                    <circle cx="12" cy="12" r="10" stroke="#27ae60" strokeWidth="1.5"/>
                                    <path d="M8 12l3 3 5-5" stroke="#27ae60" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                                </svg>
                                <p>Thanks for your report! We'll look into it.</p>
                            </div>
                        ) : (
                            <>
                                <p className={styles.bugFormDesc}>
                                    Found something that doesn't work right? Describe the issue below and we'll investigate.
                                </p>
                                <textarea
                                    className={styles.bugTextarea}
                                    placeholder="Describe the bug: what happened, what you expected, and any steps to reproduce it..."
                                    value={bugDescription}
                                    onChange={e => setBugDescription(e.target.value)}
                                    rows={5}
                                />
                                <button
                                    className={styles.bugSubmit}
                                    disabled={bugDescription.trim().length === 0}
                                    onClick={() => {
                                        // ---------------------------------------------------------------
                                        // FUTURE: Send bug report to your backend / email service.
                                        // Example: await fetch("/api/bug-report", {
                                        //   method: "POST",
                                        //   headers: { "Content-Type": "application/json" },
                                        //   body: JSON.stringify({ description: bugDescription, timestamp: new Date().toISOString() })
                                        // });
                                        // ---------------------------------------------------------------
                                        console.log("[BugReport]", bugDescription);
                                        setBugSubmitted(true);
                                    }}
                                >
                                    Submit Report
                                </button>
                            </>
                        )}
                    </div>
                </div>
            )}

        </div>
    )}
