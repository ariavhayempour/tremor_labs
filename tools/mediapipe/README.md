# MediaPipe hand tracking

Copied from the local `mediapipe-0.10.26/mediapipe-0.10.26/webcam_demo`:
`hands.py`, its requirements, and `models/hand_landmarker.task`. The upstream
Apache 2.0 license is included. The model came from Google's official model
storage (see the original demo). The full upstream build tree and Python virtual
environment are not needed by the application and are not vendored.

The integration frontend uses the existing `@mediapipe/tasks-vision` dependency.
`npm run setup:mediapipe` in `frontend/` copies its matching WASM files and this
model into `frontend/public/mediapipe/`. `npm run dev` and `npm run build` run
that setup automatically. No CDN or model download is needed at runtime.

The Python demo remains optional. From this directory create a virtual environment,
install `webcam_demo/requirements.txt`, and run `webcam_demo/hands.py --help`.
It is independent of the app's browser camera. Do not run both simultaneously.

Web API reference: https://developers.google.com/edge/mediapipe/solutions/vision/hand_landmarker/web_js
