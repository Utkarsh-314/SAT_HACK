console.log("SIGNUP FLOW VERSION 2 LOADED");
console.log("Current page:", window.location.pathname);
const API_BASE = "/api";


// ========================================
// READ API RESPONSE SAFELY
// ========================================

async function readApiResponse(response) {
    const rawText = await response.text();

    let data;

    try {
        data = rawText ? JSON.parse(rawText) : {};
    } catch (error) {
        console.error("Invalid API response:", rawText);
        throw new Error(
            `Server returned a non-JSON response (HTTP ${response.status}).`
        );
    }

    if (!response.ok) {
        throw new Error(
            data.detail ||
            data.message ||
            `Request failed with status ${response.status}`
        );
    }

    return data;
}


// ========================================
// DISPLAY MESSAGES
// ========================================

function showMessage(element, message, type = "error") {
    if (!element) return;

    element.textContent = message;
    element.className = `form-message ${type}`;
}


// ========================================
// PASSWORD VISIBILITY
// ========================================

document.querySelectorAll(".toggle-password").forEach(button => {
    button.addEventListener("click", () => {
        const input = document.getElementById(button.dataset.target);

        if (!input) return;

        const isPassword = input.type === "password";

        input.type = isPassword ? "text" : "password";
        button.textContent = isPassword ? "Hide" : "Show";
    });
});


// ========================================
// SIGNUP - FIRST STAGE
// DO NOT CALL BACKEND HERE
// ========================================

const signupForm = document.getElementById("signupForm");

if (signupForm) {
    signupForm.addEventListener("submit", event => {
        event.preventDefault();

        const name = document.getElementById("name").value.trim();
        const user_id = document.getElementById("user_id").value.trim();
        const password = document.getElementById("password").value;
        const confirmPassword =
            document.getElementById("confirm_password").value;

        const message = document.getElementById("signupMessage");
        const button = document.getElementById("signupButton");

        if (!name || !user_id || !password || !confirmPassword) {
            showMessage(message, "Please fill in all required fields.");
            return;
        }

        if (password !== confirmPassword) {
            showMessage(message, "Passwords do not match.");
            return;
        }

        if (password.length < 8) {
            showMessage(
                message,
                "Password must contain at least 8 characters."
            );
            return;
        }

        if (user_id.length < 3 || user_id.length > 50) {
            showMessage(
                message,
                "User ID must contain 3–50 characters."
            );
            return;
        }

        try {
            // Temporarily preserve signup information.
            sessionStorage.setItem(
                "pending_signup",
                JSON.stringify({
                    name,
                    user_id,
                    password
                })
            );

            button.disabled = true;
            button.textContent = "Continue...";

            // Navigate to accessibility preferences.
            window.location.assign("accessibility.html");

        } catch (error) {
            console.error(error);
            showMessage(
                message,
                "Unable to continue. Please try again."
            );

            button.disabled = false;
            button.innerHTML = 'Create Account <span>→</span>';
        }
    });
}


// ========================================
// SIGNIN
// ========================================

const signinForm = document.getElementById("signinForm");

if (signinForm) {
    signinForm.addEventListener("submit", async event => {
        event.preventDefault();

        const user_id =
            document.getElementById("user_id").value.trim();

        const password =
            document.getElementById("password").value;

        const message =
            document.getElementById("signinMessage");

        const button =
            document.getElementById("signinButton");

        button.disabled = true;
        button.textContent = "Signing in...";

        try {
            const response = await fetch(
                `${API_BASE}/auth/login`,
                {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify({
                        user_id,
                        password
                    })
                }
            );

            const data = await readApiResponse(response);

            if (!data.access_token) {
                throw new Error(
                    "Login response did not contain an access token."
                );
            }

            localStorage.setItem(
                "access_token",
                data.access_token
            );

            if (data.user) {
                localStorage.setItem(
                    "user",
                    JSON.stringify(data.user)
                );
            }

            showMessage(message, "Login successful!", "success");

            setTimeout(() => {
                window.location.href = "index.html";
            }, 500);

        } catch (error) {
            console.error("Signin error:", error);

            showMessage(
                message,
                error.message.includes("Failed to fetch")
                    ? "Cannot connect to the server. Please check your backend."
                    : error.message
            );

        } finally {
            button.disabled = false;
            button.innerHTML = 'Sign In <span>→</span>';
        }
    });
}
