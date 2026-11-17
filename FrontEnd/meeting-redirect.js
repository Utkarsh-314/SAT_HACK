
const API_BASE = "/api";

const startMeetingButton = document.getElementById(
    "startMeetingButton"
);

if (startMeetingButton) {
    startMeetingButton.addEventListener("click", async (event) => {
        event.preventDefault();

        const token = localStorage.getItem("access_token");

        // User is not logged in
        if (!token) {
            window.location.href = "signin.html";
            return;
        }

        startMeetingButton.textContent = "Checking...";
        startMeetingButton.style.pointerEvents = "none";

        try {
            const response = await fetch(`${API_BASE}/auth/me`, {
                method: "GET",
                headers: {
                    "Authorization": `Bearer ${token}`,
                    "Content-Type": "application/json"
                }
            });

            if (response.ok) {
                window.location.href = "meeting.html";
            } else {
                // Invalid or expired token
                localStorage.removeItem("access_token");
                localStorage.removeItem("user");

                window.location.href = "signin.html";
            }

        } catch (error) {
            console.error("Authentication error:", error);

            alert("Unable to connect to the server. Please try again.");

            startMeetingButton.textContent = "Start Meeting";
            startMeetingButton.style.pointerEvents = "auto";
        }
    });
}
