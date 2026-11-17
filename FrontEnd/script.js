
const AUTH_API_BASE = "/api";

console.log("SignConnect script.js loaded!");

const authButton = document.getElementById("authButton");
const menuButton = document.getElementById("menuButton");
const navLinks = document.getElementById("navLinks");

// ----------------------------------
// AUTHENTICATION BUTTON
// ----------------------------------

function updateAuthButton() {
    if (!authButton) return;

    const token = localStorage.getItem("access_token");

    authButton.textContent = token ? "Sign Out" : "Sign In";
}

if (authButton) {

    console.log("Auth button found!");

    updateAuthButton();

    authButton.addEventListener("click", async (event) => {

        event.preventDefault();

        console.log("Auth button clicked!");

        const token = localStorage.getItem("access_token");

        // User is not logged in
        if (!token) {
            window.location.assign("signin.html");
            return;
        }

        // User is logged in: logout
        authButton.disabled = true;
        authButton.textContent = "Signing out...";

        try {
            const response = await fetch(
                `${AUTH_API_BASE}/auth/logout`,
                {
                    method: "POST",
                    headers: {
                        "Authorization": `Bearer ${token}`
                    }
                }
            );

            if (!response.ok) {
                console.error("Backend logout failed:", response.status);
            }

        } catch (error) {
            console.error("Logout request failed:", error);

        } finally {

            localStorage.removeItem("access_token");
            localStorage.removeItem("user");

            window.location.reload();
        }
    });

} else {
    console.error("Auth button not found!");
}


// ----------------------------------
// MOBILE NAVIGATION
// ----------------------------------

if (menuButton && navLinks) {

    menuButton.addEventListener("click", () => {
        navLinks.classList.toggle("show");
    });

    document.querySelectorAll(".nav-links a").forEach(link => {
        link.addEventListener("click", () => {
            navLinks.classList.remove("show");
        });
    });
}


// ----------------------------------
// INITIALIZE
// ----------------------------------

updateAuthButton();
