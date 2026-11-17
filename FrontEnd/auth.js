
const API_BASE = "/api";

// Display messages
function showMessage(element, message, type = "error") {
    element.textContent = message;
    element.className = `form-message ${type}`;
}

// Password visibility
document.querySelectorAll(".toggle-password").forEach(button => {
    button.addEventListener("click", () => {
        const input = document.getElementById(button.dataset.target);

        if (!input) return;

        const isPassword = input.type === "password";
        input.type = isPassword ? "text" : "password";
        button.textContent = isPassword ? "Hide" : "Show";
    });
});

// Handle signup
const signupForm = document.getElementById("signupForm");

if (signupForm) {
    signupForm.addEventListener("submit", async event => {
        event.preventDefault();

        const name = document.getElementById("name").value.trim();
        const user_id = document.getElementById("user_id").value.trim();
        const password = document.getElementById("password").value;
        const confirmPassword =
            document.getElementById("confirm_password").value;

        const message = document.getElementById("signupMessage");
        const button = document.getElementById("signupButton");

        if (password !== confirmPassword) {
            showMessage(message, "Passwords do not match.");
            return;
        }

        if (password.length < 8) {
            showMessage(message, "Password must contain at least 8 characters.");
            return;
        }

        button.disabled = true;
        button.textContent = "Creating account...";

        try {
            const response = await fetch(`${API_BASE}/auth/signup`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    name,
                    user_id,
                    password
                })
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(
                    data.detail || "Unable to create your account."
                );
            }

            if (!data.access_token) {
                throw new Error("Account created, but no access token was returned.");
            }

            localStorage.setItem("access_token", data.access_token);

            if (data.user) {
                localStorage.setItem("user", JSON.stringify(data.user));
            }

            showMessage(message, "Account created successfully!", "success");

            setTimeout(() => {
                window.location.href = "index.html";
            }, 700);

        } catch (error) {
            showMessage(
                message,
                error.message.includes("Failed to fetch")
                    ? "Cannot connect to the server. Please check that the backend is running."
                    : error.message
            );
        } finally {
            button.disabled = false;
            button.innerHTML = 'Create Account <span>→</span>';
        }
    });
}

// Handle signin
const signinForm = document.getElementById("signinForm");

if (signinForm) {
    signinForm.addEventListener("submit", async event => {
        event.preventDefault();

        const user_id = document.getElementById("user_id").value.trim();
        const password = document.getElementById("password").value;

        const message = document.getElementById("signinMessage");
        const button = document.getElementById("signinButton");

        button.disabled = true;
        button.textContent = "Signing in...";

        try {
            const response = await fetch(`${API_BASE}/auth/login`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    user_id,
                    password
                })
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || "Invalid User ID or password.");
            }

            if (!data.access_token) {
                throw new Error("Login response did not contain an access token.");
            }

            localStorage.setItem("access_token", data.access_token);

            if (data.user) {
                localStorage.setItem("user", JSON.stringify(data.user));
            }

            showMessage(message, "Login successful!", "success");

            setTimeout(() => {
                window.location.href = "index.html";
            }, 500);

        } catch (error) {
            showMessage(
                message,
                error.message.includes("Failed to fetch")
                    ? "Cannot connect to the server. Please check that the backend is running."
                    : error.message
            );
        } finally {
            button.disabled = false;
            button.innerHTML = 'Sign In <span>→</span>';
        }
    });
}
