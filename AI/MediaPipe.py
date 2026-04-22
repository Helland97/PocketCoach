import os
import time
import cv2
import json
import time
import numpy as np
import mediapipe as mp
import subprocess
from Utils.utils.utils import *
from Utils.counters.exercise_counter import ExerciseCounter
from Utils.counters.squat_counter import SquatCounter

# Module-level progress state, read by the /progress endpoint in main.py
processing_progress = {"active": False, "frame": 0, "total_frames": 0, "percent": 0}


class MediaPipeVideoProcessor:
    def __init__(self):
        self.pose = mp.solutions.pose.Pose()
        self.drawer = mp.solutions.drawing_utils

    def draw_pose(self, frame, results, all_landmarks=True, calculate_angle=False):
        """Draws pose skeleton on the frame based on the all_landmarks flag."""
        mp_pose = mp.solutions.pose
        mp_drawing = mp.solutions.drawing_utils

        if not results.pose_landmarks:
            return frame

        if all_landmarks:
            mp_drawing.draw_landmarks(
                frame,
                results.pose_landmarks,
                mp_pose.POSE_CONNECTIONS,
                landmark_drawing_spec=mp_drawing.DrawingSpec(color=(0, 255, 0), thickness=2, circle_radius=2),
                connection_drawing_spec=mp_drawing.DrawingSpec(color=(0, 0, 255), thickness=2, circle_radius=2)
            )
        else:
            exclude_ids = {
                PoseLandmark.NOSE.value,
                PoseLandmark.LEFT_EYE_INNER.value,
                PoseLandmark.LEFT_EYE_OUTER.value,
                PoseLandmark.RIGHT_EYE_INNER.value,
                PoseLandmark.RIGHT_EYE_OUTER.value,
                PoseLandmark.LEFT_EAR.value,
                PoseLandmark.RIGHT_EAR.value,
                PoseLandmark.MOUTH_LEFT.value,
                PoseLandmark.MOUTH_RIGHT.value,
            }
            filtered_connections = [
                (start, end) for (start, end) in mp_pose.POSE_CONNECTIONS
                if start not in exclude_ids and end not in exclude_ids
            ]
            landmark_specs = {}
            for idx in range(len(results.pose_landmarks.landmark)):
                if idx in exclude_ids:
                    landmark_specs[idx] = mp_drawing.DrawingSpec(thickness=0, circle_radius=0)
                else:
                    landmark_specs[idx] = mp_drawing.DrawingSpec(color=(0, 255, 0), thickness=2, circle_radius=2)
            mp_drawing.draw_landmarks(
                frame,
                results.pose_landmarks,
                filtered_connections,
                landmark_drawing_spec=landmark_specs,
                connection_drawing_spec=mp_drawing.DrawingSpec(color=(0, 0, 255), thickness=2, circle_radius=2)
            )
        
        # Draws degrees at specified joints if calculate_angle is True    
        if calculate_angle:
            frame = self.draw_angle(frame, results)
        
        return frame


    def draw_angle(self, frame, results, joint_names=None):
        """
        Draws the angle at specified joints on the frame.
        Args:
            frame: The image frame.
            results: The MediaPipe pose results.
            joint_names: List of joint names to draw angles for (e.g., ["right_knee", "left_knee"]).
        """
        if joint_names is None:
            joint_names = ["right_knee", "left_knee"]  # Default to knees

        if not results.pose_landmarks:
            return frame

        landmarks = results.pose_landmarks.landmark
        h, w = frame.shape[:2]
        colors = {
            "right_knee": (255, 0, 0),
            "left_knee": (0, 0, 255),
            # Add more colors for other joints if needed
        }

        for joint in joint_names:
            try:
                hip, knee, ankle = get_joint_coords(landmarks, joint)
                angle = calculate_angle(hip, knee, ankle)
                anatomical_angle = 180 - angle
                knee_px = (
                    int(landmarks[JOINTS[joint]["knee"]].x * w),
                    int(landmarks[JOINTS[joint]["knee"]].y * h)
                )
                cv2.putText(
                    frame,
                    f"{int(anatomical_angle)}",
                    knee_px,
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    colors.get(joint, (0, 255, 0)),
                    2,
                    cv2.LINE_AA
                )
            except Exception:
                pass  # Optionally log or print(e)
        return frame




    def process_video(self, input_path: str, output_path: str,
                    all_landmarks: bool = True,
                    draw_skeleton: bool = True,
                    calculate_angle=False,
                    exercise: str = "squat"):
        """
        Loads a video, optionally adds MediaPipe pose skeleton to each frame, and saves the processed video.
        Args:
            input_path (str): Path to the input video file.
            output_path (str): Path to save the output video file.
            all_landmarks (bool): Whether to draw all landmarks or exclude some.
            draw_skeleton (bool): Whether to draw the skeleton at all.
        """
        start_time = time.time()
        print(f"[MediaPipe] Starting video processing: {input_path}")

        # Ensure ProcessedVideos folder exists
        os.makedirs("ProcessedVideos", exist_ok=True)

        # Force output into ProcessedVideos folder
        output_path = os.path.join("ProcessedVideos", os.path.basename(output_path))
        print(f"[MediaPipe] Output path: {output_path}")

        print(f"[MediaPipe] [{time.time()-start_time:.2f}s] Opening video capture...")
        cap = cv2.VideoCapture(input_path)
        if not cap.isOpened():
            raise IOError(f"Cannot open video file: {input_path}")

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        print(f"[MediaPipe] Video info: {width}x{height}, {fps} fps, {total_frames} frames")

        processing_progress.update(active=True, frame=0, total_frames=total_frames, percent=0)

        # Try H.264 codec first, fall back to mp4v if not available
        print(f"[MediaPipe] [{time.time()-start_time:.2f}s] Setting up video writer...")
        fourcc_codes = ['avc1', 'H264', 'X264', 'mp4v']
        out = None
        for codec in fourcc_codes:
            fourcc = cv2.VideoWriter_fourcc(*codec)
            out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
            if out.isOpened():
                print(f"[MediaPipe] Using codec: {codec}")
                break
            out.release()

        if not out or not out.isOpened():
            cap.release()
            raise IOError(f"Cannot open video writer with any codec for: {output_path}")

        # ✅ choose exercise counter
        if exercise == "squat":
            counter = SquatCounter()
        else:
            raise NotImplementedError(f"Exercise '{exercise}' not implemented.")

        mp_pose = mp.solutions.pose
        landmarks_data = []  # ✅ Collect landmarks per frame
        print(f"[MediaPipe] [{time.time()-start_time:.2f}s] Starting frame processing...")
        frame_count = 0
        with mp_pose.Pose(
            static_image_mode=False,         # Use tracking across frames
            model_complexity=2,              # Use the most accurate model
            enable_segmentation=False,       # Skip segmentation unless needed
            min_detection_confidence=0.85,    # Only accept decent detections
            min_tracking_confidence=0.85      # Only track when confident
        ) as pose:

            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                frame_count += 1
                pct = int(frame_count * 100 // total_frames) if total_frames > 0 else 0
                processing_progress.update(frame=frame_count, percent=pct)
                if frame_count % 30 == 0:  # Log every 30 frames
                    print(f"[MediaPipe] [{time.time()-start_time:.2f}s] Processed {frame_count}/{total_frames} frames")

                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = pose.process(rgb_frame)
                
                if results.pose_landmarks:
                    frame_landmarks = []
                    for lm in results.pose_landmarks.landmark:
                        frame_landmarks.append([lm.x, lm.y, lm.z, lm.visibility])

                    # Convert to NumPy array
                    frame_landmarks = np.array(frame_landmarks)  # shape: (joints, 4) - x, y, z, visibility
                    landmarks_data.append(frame_landmarks)



                
                # ✅ add counter update here
                if results.pose_landmarks:
                    counter.update(results.pose_landmarks.landmark)

                if draw_skeleton:
                    frame = self.draw_pose(frame, results, all_landmarks, calculate_angle)

                out.write(frame)
                
            # Convert all frames to a single array: (frames, joints, dimensions)
            if len(landmarks_data) == 0:
                processing_progress.update(active=False, frame=total_frames, percent=100)
                cap.release()
                out.release()
                raise ValueError(
                    f"MediaPipe could not detect a pose in any of the {frame_count} frames. "
                    f"This can happen if the person is too far away, the lighting is poor, "
                    f"or the video quality is too low. Try a different video."
                )

            detected_ratio = len(landmarks_data) / frame_count if frame_count > 0 else 0
            print(f"[MediaPipe] Pose detected in {len(landmarks_data)}/{frame_count} frames ({detected_ratio:.0%})")
            landmarks_data = np.stack(landmarks_data)  # shape: (frames, joints, 3)

        processing_progress.update(active=False, frame=total_frames, percent=100)

        print(f"[MediaPipe] [{time.time()-start_time:.2f}s] Releasing video resources...")
        cap.release()
        out.release()

        # Re-encode with H.264 using ffmpeg command line for browser compatibility
        print(f"[MediaPipe] [{time.time()-start_time:.2f}s] Re-encoding video with H.264...")
        temp_output = output_path + ".temp.mp4"
        try:
            # Move original to temp file
            os.rename(output_path, temp_output)

            # Re-encode with H.264
            ffmpeg_cmd = [
                'ffmpeg', '-y',  # Overwrite output
                '-i', temp_output,  # Input file
                '-c:v', 'libx264',  # Video codec: H.264
                '-preset', 'medium',  # Encoding speed/quality balance
                '-crf', '23',  # Quality (lower = better, 23 is default)
                '-c:a', 'copy',  # Copy audio if present
                output_path  # Output file
            ]

            result = subprocess.run(
                ffmpeg_cmd,
                capture_output=True,
                text=True,
                check=True
            )

            # Remove temp file after successful re-encoding
            os.remove(temp_output)
            print(f"[MediaPipe] [{time.time()-start_time:.2f}s] Video successfully re-encoded with H.264")

        except subprocess.CalledProcessError as e:
            print(f"[MediaPipe] WARNING: FFmpeg re-encoding failed: {e.stderr}")
            # If re-encoding fails, restore the original file
            if os.path.exists(temp_output):
                os.rename(temp_output, output_path)
            print(f"[MediaPipe] Continuing with original codec")
        except Exception as e:
            print(f"[MediaPipe] WARNING: Error during re-encoding: {str(e)}")
            # Restore original file if something went wrong
            if os.path.exists(temp_output):
                os.rename(temp_output, output_path)

        # ✅ Make sure the folder exists
        print(f"[MediaPipe] [{time.time()-start_time:.2f}s] Saving landmarks...")
        os.makedirs("MediaPipe_landmarks", exist_ok=True)

        # ✅ Create path using the same base filename as the video
        base_name = os.path.splitext(os.path.basename(output_path))[0]
        npy_output_path = os.path.join("MediaPipe_landmarks", base_name + "_landmarks.npy")

        # ✅ Save NumPy array
        np.save(npy_output_path, landmarks_data)

        print(f"[MediaPipe] [{time.time()-start_time:.2f}s] Landmarks saved to {npy_output_path}")
        print(f"[MediaPipe] [{time.time()-start_time:.2f}s] Video processing complete! Total time: {time.time()-start_time:.2f}s")
        print(f"[MediaPipe] Video saved to: {output_path}")

        # ✅ return verdict with counter results
        return self.verdict(output_path, counter)


    def verdict(self, out_path:str, counter):
        """
        Processes a video file and returns a verdict based on the pose analysis.
        Args:
            input_path (str): Path to the input video file.
        Returns:
            str: Verdict based on the analysis.
        """
        #output_path = input_path.replace(".mp4", "_processed.mp4")
        #self.process_video(input_path, output_path, all_landmarks=True, draw_skeleton=True, calculate_angle=True)

        result = counter.get_results()
        result["video"] = "id"
        result["path"] = out_path
        print("Verdict:", counter.get_results())
        return result
