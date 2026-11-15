export async function createHandLandmarker() {
  const { FilesetResolver, HandLandmarker } = await import('@mediapipe/tasks-vision')
  const assets = `${import.meta.env.BASE_URL}mediapipe`
  const files = await FilesetResolver.forVisionTasks(`${assets}/wasm`)
  return HandLandmarker.createFromOptions(files, {
    baseOptions: { modelAssetPath: `${assets}/hand_landmarker.task` },
    runningMode: 'VIDEO', numHands: 1,
  })
}
