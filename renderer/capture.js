// Iter Browser — device capture tab.
//
// Loaded as a plain file:// page inside a normal WebContentsView tab (no
// preload/contextBridge here — same as any other tab Iter can open). It is
// NOT self-driving: window.iterCapturePhoto()/iterCaptureAudio() are called
// from the main process via webContents.executeJavaScript(..., true) (the
// exact same mechanism tab_manager.js already uses for eval()), so the
// Python-side tool call controls exactly when the OS permission prompt and
// the actual capture happen. Opening this tab and doing nothing is always
// safe — nothing is captured until one of those two functions is invoked.

const params = new URLSearchParams(location.search);
const mode = params.get('mode') === 'audio' ? 'audio' : 'photo';
const video = document.getElementById('preview');
const statusEl = document.getElementById('status');

if (mode === 'audio') {
  video.style.display = 'none';
  statusEl.textContent = 'Ready — waiting for Iter to start recording audio.';
} else {
  statusEl.textContent = 'Ready — waiting for Iter to take a photo.';
}

let activeStream = null;

function setStatus(text, isErr) {
  statusEl.textContent = text;
  statusEl.style.color = isErr ? '#ff6b6b' : '#ccc';
}

function stopStream() {
  if (activeStream) {
    activeStream.getTracks().forEach((t) => t.stop());
    activeStream = null;
  }
}

window.iterCapturePhoto = async function iterCapturePhoto() {
  try {
    setStatus('Requesting camera access…');
    const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 1280, height: 720 } });
    activeStream = stream;
    video.srcObject = stream;
    await video.play();
    await new Promise((r) => setTimeout(r, 700)); // let auto-exposure/focus settle
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth || 1280;
    canvas.height = video.videoHeight || 720;
    canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);
    const dataUrl = canvas.toDataURL('image/png');
    setStatus('Photo captured at ' + new Date().toLocaleTimeString() + '.');
    stopStream();
    return dataUrl;
  } catch (err) {
    setStatus('Camera error: ' + (err && err.message ? err.message : err), true);
    stopStream();
    throw err;
  }
};

window.iterCaptureAudio = async function iterCaptureAudio(durationMs) {
  durationMs = Number(durationMs) || 5000;
  try {
    setStatus('Requesting microphone access…');
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    activeStream = stream;
    const chunks = [];
    const recorder = new MediaRecorder(stream);
    recorder.ondataavailable = (e) => { if (e.data && e.data.size) chunks.push(e.data); };
    const stopped = new Promise((resolve) => { recorder.onstop = resolve; });
    recorder.start();
    let remaining = Math.round(durationMs / 1000);
    setStatus('Recording… ' + remaining + 's left');
    const tick = setInterval(() => {
      remaining -= 1;
      if (remaining >= 0) setStatus('Recording… ' + remaining + 's left');
    }, 1000);
    await new Promise((r) => setTimeout(r, durationMs));
    clearInterval(tick);
    recorder.stop();
    await stopped;
    const blob = new Blob(chunks, { type: 'audio/webm' });
    const dataUrl = await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
    setStatus('Recording captured at ' + new Date().toLocaleTimeString() + '.');
    stopStream();
    return dataUrl;
  } catch (err) {
    setStatus('Microphone error: ' + (err && err.message ? err.message : err), true);
    stopStream();
    throw err;
  }
};
