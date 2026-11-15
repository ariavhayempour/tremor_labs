import { cp, mkdir } from 'node:fs/promises'
const root = new URL('../', import.meta.url)
const output = new URL('public/mediapipe/', root)
await mkdir(output, { recursive: true })
await cp(new URL('node_modules/@mediapipe/tasks-vision/wasm/', root), new URL('wasm/', output), { recursive: true })
await cp(new URL('../tools/mediapipe/webcam_demo/models/hand_landmarker.task', root), new URL('hand_landmarker.task', output))
console.log('MediaPipe model and WASM copied to public/mediapipe (local runtime).')
