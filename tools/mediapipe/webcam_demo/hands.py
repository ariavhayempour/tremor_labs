"""Live hand landmarks from a Logitech webcam. No images are saved."""

import argparse
from pathlib import Path
import sys
import time

import cv2
import mediapipe as mp


MODEL = Path(__file__).resolve().parent / "models" / "hand_landmarker.task"
WINDOW = "MediaPipe Hands - Logitech Brio"
CONNECTIONS = (
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (0, 17), (17, 18), (18, 19), (19, 20),
)


def cameras():
    from AVFoundation import AVCaptureDevice, AVMediaTypeVideo
    return list(AVCaptureDevice.devicesWithMediaType_(AVMediaTypeVideo))


def select_camera(index):
    devices = cameras()
    for i, device in enumerate(devices):
        print(f"Camera {i}: {device.localizedName()}", flush=True)
    if index is not None:
        if not 0 <= index < len(devices):
            raise RuntimeError(f"Camera {index} is not available.")
        return index, str(devices[index].localizedName())
    for i, device in enumerate(devices):
        name = str(device.localizedName())
        if "brio" in name.lower() or "logitech" in name.lower():
            return i, name
    raise RuntimeError("Logitech camera not found. Connect the Brio, or use --camera INDEX.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--camera", type=int, help="Override automatic Logitech camera selection")
    parser.add_argument("--list-cameras", action="store_true")
    parser.add_argument("--check", action="store_true", help="Process 30 webcam frames without a window")
    parser.add_argument("--self-test", action="store_true", help="Test inference without using the camera")
    args = parser.parse_args()
    if args.list_cameras:
        for i, device in enumerate(cameras()):
            print(f"{i}: {device.localizedName()}")
        return
    if not MODEL.is_file():
        raise RuntimeError(f"Missing model: {MODEL}")
    options = mp.tasks.vision.HandLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(MODEL)),
        running_mode=mp.tasks.vision.RunningMode.VIDEO,
        num_hands=2,
    )
    with mp.tasks.vision.HandLandmarker.create_from_options(options) as detector:
        if args.self_test:
            import numpy as np
            image = mp.Image(image_format=mp.ImageFormat.SRGB,
                             data=np.zeros((480, 640, 3), dtype=np.uint8))
            result = detector.detect_for_video(image, 0)
            print(f"PASS: MediaPipe {mp.__version__}; model inference works; "
                  f"{len(result.hand_landmarks)} hands in blank test image.")
            return
        index, name = select_camera(args.camera)
        print(f"Opening {name} (camera {index}). Allow camera access if macOS asks.", flush=True)
        capture = cv2.VideoCapture(index, cv2.CAP_AVFOUNDATION)
        try:
            if not capture.isOpened():
                raise RuntimeError(
                    "Camera could not open. Close the Logi Tune preview and other camera apps. "
                    "In System Settings > Privacy & Security > Camera, allow the app "
                    "that launched this script (for example Terminal), then restart it.")
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, 1980)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
            capture.set(cv2.CAP_PROP_FPS, 60)
            if not args.check:
                cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
                cv2.resizeWindow(WINDOW, 1980, 1080)
            frame_count = 0
            max_hands = 0
            last_time = time.monotonic()
            last_timestamp = -1
            fps = 0.0
            failures = 0
            while True:
                ok, frame = capture.read()
                if not ok:
                    failures += 1
                    if failures >= 60:
                        raise RuntimeError("Camera stopped delivering frames. Close other camera previews and reconnect the Brio.")
                    time.sleep(0.05)
                    continue
                failures = 0
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                timestamp = max(last_timestamp + 1, time.monotonic_ns() // 1_000_000)
                last_timestamp = timestamp
                result = detector.detect_for_video(
                    mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), timestamp)
                frame_count += 1
                max_hands = max(max_hands, len(result.hand_landmarks))
                if frame_count == 1:
                    print(f"Receiving {frame.shape[1]}x{frame.shape[0]} video from {name}.", flush=True)
                if args.check:
                    if frame_count >= 30:
                        print(f"PASS: 30 camera frames processed; maximum hands detected: {max_hands}.")
                        break
                    continue
                # Mirror the preview after inference; labels use the original camera image.
                frame = cv2.flip(frame, 1)
                height, width = frame.shape[:2]
                for landmarks, handedness in zip(result.hand_landmarks, result.handedness):
                    points = [(int((1 - p.x) * (width - 1)), int(p.y * (height - 1))) for p in landmarks]
                    for start, end in CONNECTIONS:
                        cv2.line(frame, points[start], points[end], (60, 220, 100), 2, cv2.LINE_AA)
                    for i, point in enumerate(points):
                        color = (0, 210, 255) if i in (4, 8, 12, 16, 20) else (255, 255, 255)
                        cv2.circle(frame, point, 5, color, -1, cv2.LINE_AA)
                    x, y = points[0]
                    cv2.putText(frame, handedness[0].category_name,
                                (max(0, x), max(25, y - 15)), cv2.FONT_HERSHEY_SIMPLEX,
                                0.7, (60, 220, 100), 2, cv2.LINE_AA)
                now = time.monotonic()
                fps = 0.9 * fps + 0.1 / max(now - last_time, 0.0001)
                last_time = now
                cv2.rectangle(frame, (0, 0), (width, 75), (25, 25, 25), -1)
                cv2.putText(frame, f"{name} | Hands: {len(result.hand_landmarks)} | {fps:.0f} FPS",
                            (16, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                cv2.putText(frame, "Show your hands | Yellow dots: fingertips | Q / Esc: quit",
                            (16, 59), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (210, 210, 210), 1)
                cv2.imshow(WINDOW, frame)
                if cv2.waitKey(1) & 0xFF in (ord("q"), ord("Q"), 27):
                    break
                if cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
                    break
        finally:
            capture.release()
            cv2.destroyAllWindows()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except (RuntimeError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
