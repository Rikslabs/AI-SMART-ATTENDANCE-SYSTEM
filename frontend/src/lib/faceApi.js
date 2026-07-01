import * as faceapi from "face-api.js";

const MODEL_URL = "https://justadudewhohacks.github.io/face-api.js/models";
let loadedPromise = null;

export function loadFaceModels() {
  if (!loadedPromise) {
    loadedPromise = Promise.all([
      faceapi.nets.tinyFaceDetector.loadFromUri(MODEL_URL),
      faceapi.nets.faceLandmark68Net.loadFromUri(MODEL_URL),
      faceapi.nets.faceRecognitionNet.loadFromUri(MODEL_URL),
    ]).then(() => true);
  }
  return loadedPromise;
}

const detectorOpts = new faceapi.TinyFaceDetectorOptions({ inputSize: 320, scoreThreshold: 0.5 });

export async function detectFaceDescriptor(video) {
  const result = await faceapi
    .detectSingleFace(video, detectorOpts)
    .withFaceLandmarks()
    .withFaceDescriptor();
  if (!result) return null;
  return {
    descriptor: Array.from(result.descriptor),
    box: result.detection.box,
    score: result.detection.score,
  };
}

export function drawBox(canvas, video, box, color = "#0033CC") {
  const ctx = canvas.getContext("2d");
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  if (!box) return;
  ctx.strokeStyle = color;
  ctx.lineWidth = 3;
  ctx.strokeRect(box.x, box.y, box.width, box.height);
}

export function captureFrameAsDataUrl(video) {
  const c = document.createElement("canvas");
  c.width = video.videoWidth;
  c.height = video.videoHeight;
  c.getContext("2d").drawImage(video, 0, 0);
  return c.toDataURL("image/jpeg", 0.85);
}
