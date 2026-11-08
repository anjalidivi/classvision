
document.addEventListener("DOMContentLoaded", () => {
    const video = document.getElementById("webcamVideo");

    if (!video) return;

    const startButton = document.getElementById("startCamera");
    const stopButton = document.getElementById("stopCamera");
    const status = document.getElementById("cameraStatus");
    const message = document.getElementById("cameraMessage");
    const placeholder = document.getElementById("cameraPlaceholder");

    const faceCount = document.getElementById("liveFaceCount");
    const trackingCount = document.getElementById("liveTrackingCount");
    const cameraStatusValue = document.getElementById("liveCameraStatus");

    let cameraStream = null;
    let detectionTimer = null;
    let processing = false;
    let active = false;

    // Canvas used to capture webcam frames.
    const captureCanvas = document.createElement("canvas");
    const captureContext = captureCanvas.getContext("2d");

    // Canvas overlay used to draw face boxes.
    const overlay = document.createElement("canvas");
    overlay.style.position = "absolute";
    overlay.style.pointerEvents = "none";

    const videoContainer = video.parentElement;
    videoContainer.style.position = "relative";
    videoContainer.appendChild(overlay);

    function resizeOverlay() {
        if (!video.videoWidth || !video.clientWidth) return;

        overlay.width = video.clientWidth;
        overlay.height = video.clientHeight;

        overlay.style.left = `${video.offsetLeft}px`;
        overlay.style.top = `${video.offsetTop}px`;
        overlay.style.width = `${video.clientWidth}px`;
        overlay.style.height = `${video.clientHeight}px`;
    }

    function drawFaces(faces, frameWidth, frameHeight) {
        resizeOverlay();

        const context = overlay.getContext("2d");
        context.clearRect(0, 0, overlay.width, overlay.height);

        const scaleX = overlay.width / frameWidth;
        const scaleY = overlay.height / frameHeight;

        faces.forEach(face => {
            const [x, y, width, height] = face.box;

            const left = x * scaleX;
            const top = y * scaleY;
            const boxWidth = width * scaleX;
            const boxHeight = height * scaleY;

            context.strokeStyle = "#42c98b";
            context.lineWidth = 2;
            context.strokeRect(left, top, boxWidth, boxHeight);

            context.fillStyle = "#42c98b";
            context.font = "bold 13px Arial";

            context.fillText(
                face.student_id,
                left,
                Math.max(top - 7, 14)
            );
        });
    }


async function detectFrame() {
    if (!active || processing || video.readyState < 2) return;

    processing = true;

    try {
        const originalWidth = video.videoWidth;
        const originalHeight = video.videoHeight;

        const frameWidth = Math.min(originalWidth, 640);
        const frameHeight = Math.round(
            originalHeight * frameWidth / originalWidth
        );

        captureCanvas.width = frameWidth;
        captureCanvas.height = frameHeight;

        captureContext.drawImage(
            video,
            0,
            0,
            frameWidth,
            frameHeight
        );

        const image = captureCanvas.toDataURL("image/jpeg", 0.65);

        const response = await fetch("/api/webcam/detect", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ image })
        });

        const result = await response.json();

        if (!response.ok || !result.success) {
            throw new Error(result.message || "Detection failed.");
        }

        faceCount.textContent = result.face_count;
        trackingCount.textContent = result.faces.length;

        drawFaces(result.faces, frameWidth, frameHeight);

        message.textContent = "Live face detection is running.";

    } catch (error) {
        console.error("Detection error:", error);
        message.textContent = `AI processing error: ${error.message}`;
    } finally {
        processing = false;
    }
}
   
async function startCamera() {
    console.log("START CAMERA BUTTON CLICKED");

    try {
        if (active) return;

        message.textContent = "Requesting webcam permission...";

        cameraStream = await navigator.mediaDevices.getUserMedia({
            video: {
                width: { ideal: 1280 },
                height: { ideal: 720 }
            },
            audio: false
        });

        video.srcObject = cameraStream;
        await video.play();

        active = true;

        placeholder.style.display = "none";
        video.style.display = "block";

        status.textContent = "CAMERA LIVE";
        cameraStatusValue.textContent = "ON";

        startButton.disabled = true;
        stopButton.disabled = false;

        message.textContent = "Connecting to Flask face detection...";

        detectFrame();

        detectionTimer = setInterval(detectFrame, 500);

    } catch (error) {
        console.error("Camera error:", error);

        message.textContent =
            error.message || "Unable to start webcam.";

        status.textContent = "CAMERA ERROR";
        cameraStatusValue.textContent = "ERROR";

        if (cameraStream) {
            cameraStream.getTracks().forEach(track => track.stop());
            cameraStream = null;
        }
    }
}


    async function stopCamera() {
        active = false;

        if (detectionTimer) {
            clearInterval(detectionTimer);
            detectionTimer = null;
        }

        if (cameraStream) {
            cameraStream.getTracks().forEach(track => track.stop());
            cameraStream = null;
        }

        video.srcObject = null;
        video.style.display = "none";
        placeholder.style.display = "block";

        overlay.getContext("2d").clearRect(
            0, 0, overlay.width, overlay.height
        );

        faceCount.textContent = "0";
        trackingCount.textContent = "0";

        status.textContent = "CAMERA OFF";
        cameraStatusValue.textContent = "OFF";

        startButton.disabled = false;
        stopButton.disabled = true;

        message.textContent = "Webcam stopped.";

        try {
            await fetch("/api/webcam/stop", {
                method: "POST"
            });
        } catch (error) {
            console.error("Unable to stop backend session:", error);
        }
    }

    startButton.addEventListener("click", startCamera);
    stopButton.addEventListener("click", stopCamera);

    stopButton.disabled = true;

    window.addEventListener("beforeunload", () => {
        if (cameraStream) {
            cameraStream.getTracks().forEach(track => track.stop());
        }
    });
});
