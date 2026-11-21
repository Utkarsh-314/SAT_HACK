console.log("ROOM PAGE DEBUG");

console.log("URL:", window.location.href);
console.log("ORIGIN:", window.location.origin);
console.log("HOSTNAME:", window.location.hostname);
console.log("TOKEN EXISTS:", !!localStorage.getItem("access_token"));
console.log(
    "TOKEN LENGTH:",
    localStorage.getItem("access_token")?.length
);
const API_BASE = "/api";

let pendingIceCandidates = [];
const token = localStorage.getItem("access_token");

const params = new URLSearchParams(window.location.search);
const meetingCode = (params.get("code") || "").trim().toUpperCase();

const localVideo = document.getElementById("localVideo");
const remoteVideo = document.getElementById("remoteVideo");

const remotePlaceholder = document.getElementById("remotePlaceholder");

const connectionStatus = document.getElementById("connectionStatus");
const statusMessage = document.getElementById("statusMessage");

const micButton = document.getElementById("micButton");
const cameraButton = document.getElementById("cameraButton");
const leaveButton = document.getElementById("leaveButton");

let localStream = null;
let remoteStream = null;

let peerConnection = null;
let signalingSocket = null;

let isMicOn = true;
let isCameraOn = true;

let isLeaving = false;

const ICE_SERVERS = {
    iceServers: [
        {
            urls: "stun:stun.l.google.com:19302"
        },
        {
            urls: "stun:stun1.l.google.com:19302"
        }
    ]
};


// ------------------------------------
// STATUS
// ------------------------------------

function setStatus(message) {
    statusMessage.textContent = message;
}

function setConnectionStatus(message) {
    connectionStatus.textContent = message;
}


// ------------------------------------
// AUTHENTICATION
// ------------------------------------


async function verifyAuthentication() {
    console.log("VERIFY AUTH STARTED");
    console.log("API URL:", `${API_BASE}/auth/me`);
    console.log("TOKEN EXISTS:", !!token);

    if (!token) {
        console.error("No access token found.");
        window.location.href = "signin.html";
        return false;
    }

    const controller = new AbortController();

    const timeout = setTimeout(() => {
        controller.abort();
    }, 10000);

    try {
        console.log("Sending authentication request...");

        const response = await fetch(`${API_BASE}/auth/me`, {
            method: "GET",
            headers: {
                Authorization: `Bearer ${token}`
            },
            signal: controller.signal
        });

        console.log("AUTH RESPONSE STATUS:", response.status);

        if (response.status === 401 || response.status === 403) {
            console.error("Token is invalid or expired.");

            localStorage.removeItem("access_token");
            localStorage.removeItem("user");

            window.location.href = "signin.html";
            return false;
        }

        if (!response.ok) {
            throw new Error(`Authentication API returned ${response.status}`);
        }

        console.log("AUTHENTICATION SUCCESSFUL");
        return true;

    } catch (error) {
        console.error("AUTHENTICATION ERROR:", error);

        if (error.name === "AbortError") {
            setStatus("Authentication timed out. Backend is not responding.");
        } else {
            setStatus("Cannot connect to authentication server: " + error.message);
        }

        return false;

    } finally {
        clearTimeout(timeout);
    }
}



// ------------------------------------
// VALIDATE MEETING
// ------------------------------------

async function validateMeeting() {

    const response = await fetch(`${API_BASE}/meetings/join`, {

        method: "POST",

        headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`
        },

        body: JSON.stringify({
            meeting_code: meetingCode
        })
    });

    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.detail || "Unable to join meeting");
    }

    document.getElementById("meetingName").textContent =
        data.meeting_name;

    document.getElementById("meetingCode").textContent =
        `Code: ${meetingCode}`;

}


// ------------------------------------
// CAMERA AND MICROPHONE
// ------------------------------------

async function initializeMedia() {

    if (!navigator.mediaDevices ||
        !navigator.mediaDevices.getUserMedia) {

        throw new Error(
            "Camera access requires HTTPS or localhost."
        );
    }

    localStream = await navigator.mediaDevices.getUserMedia({

        video: {
            width: { ideal: 1280 },
            height: { ideal: 720 }
        },

        audio: true

    });

    localVideo.srcObject = localStream;

}


async function extractFrame() {

    // Use local camera for single-participant testing
    const video = localVideo;

    if (
        !video ||
        !video.srcObject ||
        video.readyState < 2 ||
        video.videoWidth === 0 ||
        video.videoHeight === 0
    ) {
        return null;
    }

    const canvas = document.createElement("canvas");

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    const ctx = canvas.getContext("2d");

    ctx.drawImage(
        video,
        0,
        0,
        canvas.width,
        canvas.height
    );

    return new Promise(resolve => {
        canvas.toBlob(
            blob => resolve(blob),
            "image/jpeg",
            0.85
        );
    });
}

let isSendingFrame = false;

setInterval(async () => {

    if (isSendingFrame) return;

    const frame = await extractFrame();

    if (!frame) return;

    isSendingFrame = true;

    try {
        const formData = new FormData();
        formData.append("file", frame, "latest_frame.jpg");

        const response = await fetch(`${API_BASE}/frames/latest`, {
            method: "POST",
            headers: token ? {
                Authorization: `Bearer ${token}`
            } : {},
            body: formData
        });

        if (!response.ok) {
            throw new Error("Failed to send frame");
        }

        console.log("Frame saved in backend");

    } catch (error) {
        console.error("Frame upload error:", error);

    } finally {
        isSendingFrame = false;
    }

}, 1000);
// ------------------------------------
// CREATE PEER CONNECTION
// ------------------------------------

function createPeerConnection() {

    if (peerConnection) {
        return peerConnection;
    }

    peerConnection = new RTCPeerConnection(ICE_SERVERS);

    remoteStream = new MediaStream();

    remoteVideo.srcObject = remoteStream;

    // Add local camera and microphone tracks
    localStream.getTracks().forEach(track => {

        peerConnection.addTrack(
            track,
            localStream
        );

    });


    // Receive remote media
    peerConnection.ontrack = event => {

        event.streams[0].getTracks().forEach(track => {

            const alreadyAdded = remoteStream
                .getTracks()
                .some(existing => existing.id === track.id);

            if (!alreadyAdded) {
                remoteStream.addTrack(track);
            }

        });

        remotePlaceholder.style.display = "none";

        remoteVideo.play().catch(error => {
            console.warn("Remote playback needs user interaction:", error);
        });

    };


    // Send ICE candidates to the other participant
    peerConnection.onicecandidate = event => {

        if (event.candidate && signalingSocket?.readyState === WebSocket.OPEN) {

            sendSignal(
                "ice_candidate",
                event.candidate.toJSON()
            );

        }

    };


    // Connection state
    peerConnection.onconnectionstatechange = () => {

        const state = peerConnection.connectionState;

        setConnectionStatus(state);

        if (state === "connected") {
            setStatus("You are connected to the meeting.");
        }

        if (state === "failed") {
            setStatus("Connection failed. Check your network or TURN configuration.");
        }

        if (state === "disconnected") {
            setStatus("Participant connection interrupted.");
        }

    };

    return peerConnection;
}


// ------------------------------------
// SEND SIGNALING MESSAGE
// ------------------------------------

function sendSignal(type, payload) {

    if (!signalingSocket ||
        signalingSocket.readyState !== WebSocket.OPEN) {

        return;
    }

    signalingSocket.send(JSON.stringify({
        type,
        payload
    }));

}


// ------------------------------------
// CREATE AND SEND OFFER
// ------------------------------------

async function createOffer() {

    const pc = createPeerConnection();

    const offer = await pc.createOffer();

    await pc.setLocalDescription(offer);

    sendSignal(
        "offer",
        pc.localDescription.toJSON()
    );

}


// ------------------------------------
// HANDLE RECEIVED OFFER
// ------------------------------------

async function handleOffer(payload) {

    const pc = createPeerConnection();

    await pc.setRemoteDescription(
        new RTCSessionDescription(payload)
    );

    await flushPendingIceCandidates();

    const answer = await pc.createAnswer();

    await pc.setLocalDescription(answer);

    sendSignal(
        "answer",
        pc.localDescription.toJSON()
    );
}



// ------------------------------------
// HANDLE RECEIVED ANSWER
// ------------------------------------

async function handleAnswer(payload) {

    if (!peerConnection) {
        return;
    }

    await peerConnection.setRemoteDescription(
        new RTCSessionDescription(payload)
    );

    await flushPendingIceCandidates();
}

// ------------------------------------
// HANDLE ICE CANDIDATE
// ------------------------------------

async function handleICECandidate(payload) {

    const candidate = new RTCIceCandidate(payload);

    if (!peerConnection || !peerConnection.remoteDescription) {
        pendingIceCandidates.push(candidate);
        return;
    }

    try {
        await peerConnection.addIceCandidate(candidate);
    } catch (error) {
        console.error("ICE candidate error:", error);
    }
}

async function flushPendingIceCandidates() {

    if (!peerConnection || !peerConnection.remoteDescription) {
        return;
    }

    while (pendingIceCandidates.length > 0) {

        const candidate = pendingIceCandidates.shift();

        try {
            await peerConnection.addIceCandidate(candidate);
        } catch (error) {
            console.error("Queued ICE candidate error:", error);
        }
    }
}

// ------------------------------------
// WEBSOCKET CONNECTION
// ------------------------------------

function connectSignaling() {

    return new Promise((resolve, reject) => {

        const wsProtocol =
            window.location.protocol === "https:" ? "wss:" : "ws:";

        const wsUrl =
            `${wsProtocol}//${window.location.host}/ws/signaling/${encodeURIComponent(meetingCode)}` +
            `?token=${encodeURIComponent(token)}`;

        signalingSocket = new WebSocket(wsUrl);

        let settled = false;

        const connectionTimeout = setTimeout(() => {

            if (!settled) {
                settled = true;
                reject(new Error("WebSocket connection timed out."));
                signalingSocket.close();
            }

        }, 10000);


        signalingSocket.onopen = () => {

            setConnectionStatus("Waiting for participant");

            setStatus("Connected to meeting server. Waiting for another user.");

        };


        signalingSocket.onmessage = async event => {

            try {

                const message = JSON.parse(event.data);

                switch (message.type) {

                    case "joined":

                        if (!settled) {

                            settled = true;
                            clearTimeout(connectionTimeout);
                            resolve(true);

                        }

                        break;


                    case "peer_joined":

                        setStatus("Another participant joined. Connecting video...");

                        await createOffer();

                        break;


                    case "peer_present":

                        setStatus("Another participant is already in the meeting.");

                        break;


                    case "offer":

                        await handleOffer(message.payload);

                        break;


                    case "answer":

                        await handleAnswer(message.payload);

                        break;


                    case "ice_candidate":

                        await handleICECandidate(message.payload);

                        break;


                    case "peer_left":

                        if (peerConnection) {
                            peerConnection.close();
                            peerConnection = null;
                        }

                        remoteStream = new MediaStream();
                        remoteVideo.srcObject = remoteStream;

                        remotePlaceholder.style.display = "flex";

                        setConnectionStatus("Participant left");

                        setStatus("The other participant left the meeting.");

                        break;


                    case "error":

                        setStatus(message.message || "Signaling error.");

                        break;

                }

            } catch (error) {

                console.error("Signaling message error:", error);

                setStatus("An error occurred while handling the connection.");

            }

        };


        signalingSocket.onerror = () => {

            if (!settled) {

                settled = true;
                clearTimeout(connectionTimeout);

                reject(new Error("Unable to connect to the meeting server."));

            }

        };


        signalingSocket.onclose = () => {

            if (!settled) {

                settled = true;
                clearTimeout(connectionTimeout);

                reject(new Error("Meeting server connection closed."));

            }

            if (!isLeaving) {
                setConnectionStatus("Server disconnected");
            }

        };

    });

}


// ------------------------------------
// MICROPHONE CONTROL
// ------------------------------------

micButton.addEventListener("click", () => {

    if (!localStream) return;

    isMicOn = !isMicOn;

    localStream.getAudioTracks().forEach(track => {
        track.enabled = isMicOn;
    });

    micButton.classList.toggle("active", !isMicOn);

    micButton.querySelector("small").textContent =
        isMicOn ? "Mute" : "Unmute";

});


// ------------------------------------
// CAMERA CONTROL
// ------------------------------------

cameraButton.addEventListener("click", () => {

    if (!localStream) return;

    isCameraOn = !isCameraOn;

    localStream.getVideoTracks().forEach(track => {
        track.enabled = isCameraOn;
    });

    cameraButton.classList.toggle("active", !isCameraOn);

    cameraButton.querySelector("small").textContent =
        isCameraOn ? "Camera Off" : "Camera On";

});


// ------------------------------------
// LEAVE MEETING
// ------------------------------------

async function leaveMeeting() {

    if (isLeaving) return;

    isLeaving = true;

    if (signalingSocket &&
        signalingSocket.readyState === WebSocket.OPEN) {

        signalingSocket.close();
    }

    if (peerConnection) {

        peerConnection.close();
        peerConnection = null;

    }

    if (localStream) {

        localStream.getTracks().forEach(track => {
            track.stop();
        });

    }

    window.location.href = "meeting.html";

}

leaveButton.addEventListener("click", leaveMeeting);


// ------------------------------------
// START MEETING
// ------------------------------------

async function startMeeting() {

    try {

        setStatus("Checking authentication...");

        const authenticated = await verifyAuthentication();

        if (!authenticated) return;

        if (!meetingCode) {
            throw new Error("Meeting code is missing.");
        }

        await validateMeeting();

        setStatus("Requesting camera and microphone permission...");

        await initializeMedia();

        setStatus("Connecting to meeting server...");

        await connectSignaling();

    } catch (error) {

        console.error("Meeting initialization error:", error);

        setStatus(error.message);

        setConnectionStatus("Connection error");

    }

}


// ------------------------------------
// PAGE EXIT CLEANUP
// ------------------------------------

window.addEventListener("pagehide", () => {

    if (localStream) {

        localStream.getTracks().forEach(track => {
            track.stop();
        });

    }

    if (peerConnection) {
        peerConnection.close();
    }

    if (signalingSocket) {
        signalingSocket.close();
    }

});


// START
startMeeting();
