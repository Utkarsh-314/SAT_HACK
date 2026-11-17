
const API_BASE = "/api";

const token = localStorage.getItem("access_token");


// ========================================
// 1. AUTHENTICATION CHECK
// ========================================

async function verifyUser() {

    if (!token) {
        window.location.href = "signin.html";
        return false;
    }

    try {

        const response = await fetch(`${API_BASE}/auth/me`, {
            method: "GET",
            headers: {
                "Authorization": `Bearer ${token}`
            }
        });

        if (!response.ok) {
            throw new Error("Invalid session");
        }

        const data = await response.json();

        const user = data.user || data;

        const name = user.name || user.user_id || "User";

        document.getElementById("userName").textContent =
            `Signed in as ${name}`;

        document.getElementById("welcomeName").textContent =
            name;

        return true;

    } catch (error) {

        console.error("Authentication failed:", error);

        localStorage.removeItem("access_token");
        localStorage.removeItem("user");

        window.location.href = "signin.html";

        return false;
    }
}


// ========================================
// 2. STATUS MESSAGE
// ========================================

function showStatus(message, type = "info") {

    const status = document.getElementById("statusMessage");

    status.textContent = message;

    status.style.color =
        type === "error" ? "#f87171" :
            type === "success" ? "#4ade80" :
                "#fbbf24";

}


// ========================================
// 3. CREATE MEETING
// ========================================

const createMeetingForm =
    document.getElementById("createMeetingForm");

createMeetingForm.addEventListener("submit", async (event) => {

    event.preventDefault();

    const meetingName =
        document.getElementById("meetingName").value.trim();

    const description =
        document.getElementById("meetingDescription").value.trim();

    const button =
        document.getElementById("createMeetingButton");

    if (!meetingName) {
        showStatus("Please enter a meeting name.", "error");
        return;
    }

    button.disabled = true;
    button.textContent = "Creating Meeting...";

    try {

        const response = await fetch(`${API_BASE}/meetings/`, {

            method: "POST",

            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
            },

            body: JSON.stringify({
                meeting_name: meetingName,
                description: description
            })

        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Unable to create meeting.");
        }

        if (!data.meeting_code) {
            throw new Error("Server did not return a meeting code.");
        }

        // Display meeting information

        const meetingCode = data.meeting_code;

        const meetingLink = data.meeting_link ||
            `${window.location.origin}/room.html?code=${encodeURIComponent(meetingCode)}`;

        document.getElementById("generatedCode").textContent =
            meetingCode;

        document.getElementById("meetingLink").value =
            meetingLink;

        document.getElementById("createdMeeting")
            .classList.remove("hidden");

        // Save current meeting details

        localStorage.setItem("current_meeting", JSON.stringify({
            meeting_code: meetingCode,
            meeting_name: meetingName,
            meeting_link: meetingLink
        }));

        showStatus("Meeting created successfully!", "success");

    } catch (error) {

        console.error("Create meeting error:", error);

        showStatus(error.message, "error");

    } finally {

        button.disabled = false;
        button.innerHTML = "＋ Create Meeting";

    }

});


// ========================================
// 4. COPY MEETING CODE
// ========================================

document.getElementById("copyCodeButton")
    .addEventListener("click", async () => {

        const code =
            document.getElementById("generatedCode").textContent;

        try {
            await navigator.clipboard.writeText(code);
            showStatus("Meeting code copied!", "success");
        } catch {
            showStatus("Unable to copy meeting code.", "error");
        }

    });


// ========================================
// 5. COPY MEETING LINK
// ========================================

document.getElementById("copyLinkButton")
    .addEventListener("click", async () => {

        const link =
            document.getElementById("meetingLink").value;

        try {
            await navigator.clipboard.writeText(link);
            showStatus("Invitation link copied!", "success");
        } catch {
            showStatus("Unable to copy invitation link.", "error");
        }

    });


// ========================================
// 6. JOIN MEETING
// ========================================

const joinMeetingForm =
    document.getElementById("joinMeetingForm");

joinMeetingForm.addEventListener("submit", async (event) => {

    event.preventDefault();

    const meetingCode =
        document.getElementById("meetingCode").value.trim();

    const button =
        document.getElementById("joinMeetingButton");

    if (!meetingCode) {
        showStatus("Please enter a meeting code.", "error");
        return;
    }

    button.disabled = true;
    button.textContent = "Checking Meeting...";

    try {

        const response = await fetch(`${API_BASE}/meetings/join`, {

            method: "POST",

            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
            },

            body: JSON.stringify({
                meeting_code: meetingCode
            })

        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Meeting not found or unavailable.");
        }

        localStorage.setItem("current_meeting", JSON.stringify({
            meeting_code: meetingCode,
            meeting_name: data.meeting_name || "Meeting"
        }));

        showStatus("Meeting verified! Preparing meeting room...", "success");

        window.location.href =
            `room.html?code=${encodeURIComponent(meetingCode)}`;

    } catch (error) {

        console.error("Join meeting error:", error);

        showStatus(error.message, "error");

    } finally {

        button.disabled = false;
        button.textContent = "Join Meeting →";

    }

});


// ========================================
// 7. ENTER CREATED MEETING
// ========================================

document.getElementById("enterMeetingButton")
    .addEventListener("click", () => {

        const meeting = JSON.parse(
            localStorage.getItem("current_meeting") || "null"
        );

        if (!meeting || !meeting.meeting_code) {
            showStatus("No meeting available.", "error");
            return;
        }

        window.location.href =
            `room.html?code=${encodeURIComponent(meeting.meeting_code)}`;

    });


// ========================================
// 8. LOGOUT
// ========================================

document.getElementById("logoutButton")
    .addEventListener("click", async () => {

        try {

            await fetch(`${API_BASE}/auth/logout`, {

                method: "POST",

                headers: {
                    "Authorization": `Bearer ${token}`
                }

            });

        } catch (error) {

            console.error("Logout request failed:", error);

        } finally {

            localStorage.removeItem("access_token");
            localStorage.removeItem("user");
            localStorage.removeItem("current_meeting");

            window.location.href = "index.html";
        }

    });


// ========================================
// 9. INITIALIZE LOBBY
// ========================================

verifyUser();
