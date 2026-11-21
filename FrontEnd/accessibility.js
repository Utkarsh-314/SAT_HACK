
const API_BASE = "http://127.0.0.1:8000/api";

const form = document.getElementById("accessibilityForm");
const continueButton = document.getElementById("continueButton");
const skipButton = document.getElementById("skipButton");
const message = document.getElementById("accessibilityMessage");

let isSubmitting = false;


// ========================================
// CHECK PENDING SIGNUP DETAILS
// ========================================

function getPendingSignup() {
    try {
        const pending = sessionStorage.getItem("pending_signup");

        return pending ? JSON.parse(pending) : null;

    } catch (error) {
        return null;
    }
}

const pendingSignup = getPendingSignup();

if (
    !pendingSignup ||
    !pendingSignup.name ||
    !pendingSignup.user_id ||
    !pendingSignup.password
) {
    alert("Please complete the signup form first.");
    window.location.replace("signup.html");
}


// ========================================
// ACCESSIBILITY CARD SELECTION
// ========================================

const cards = document.querySelectorAll(".option-card");

cards.forEach(card => {

    const checkbox = card.querySelector("input");

    checkbox.addEventListener("change", () => {

        // None / prefer not to say is exclusive.
        if (checkbox.value === "None or prefer not to say"
            && checkbox.checked) {

            cards.forEach(otherCard => {
                const otherCheckbox =
                    otherCard.querySelector("input");

                if (otherCheckbox !== checkbox) {
                    otherCheckbox.checked = false;
                    otherCard.classList.remove("selected");
                }
            });

        } else if (checkbox.checked) {

            const noneCheckbox = document.querySelector(
                'input[value="None or prefer not to say"]'
            );

            if (noneCheckbox) {
                noneCheckbox.checked = false;
                noneCheckbox.closest(".option-card")
                    .classList.remove("selected");
            }
        }

        card.classList.toggle("selected", checkbox.checked);
    });

});


// ========================================
// CREATE ACCOUNT
// ========================================

async function createAccount() {

    if (isSubmitting) return;

    if (!pendingSignup) {
        window.location.replace("signup.html");
        return;
    }

    isSubmitting = true;

    continueButton.disabled = true;
    skipButton.disabled = true;

    continueButton.textContent = "Creating account...";

    message.textContent = "";

    try {

        // Existing signup API.
        // No disability column or new database field.
        // Get selected accessibility preferences
        const disabilities = Array.from(
            document.querySelectorAll(
                'input[name="disability"]:checked'
            )
        ).map(input => input.value);

        const response = await fetch(
            `${API_BASE}/auth/signup`,
            {
                method: "POST",

                headers: {
                    "Content-Type": "application/json"
                },

                body: JSON.stringify({
                    name: pendingSignup.name,
                    user_id: pendingSignup.user_id,
                    password: pendingSignup.password,
                    disabilities: disabilities
                })
            }
        );

        const rawText = await response.text();

        let data;

        try {
            data = rawText ? JSON.parse(rawText) : {};
        } catch {
            throw new Error(
                `Invalid server response (HTTP ${response.status}).`
            );
        }

        if (!response.ok) {
            throw new Error(
                data.detail ||
                data.message ||
                "Account creation failed."
            );
        }

        if (!data.access_token) {
            throw new Error(
                "Account created, but no access token was returned."
            );
        }


        // Save authentication.

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


        // Remove temporary signup details.

        sessionStorage.removeItem("pending_signup");


        message.style.color = "#16a34a";
        message.textContent = "Account created successfully!";

        window.location.replace("index.html");


    } catch (error) {

        console.error("Account creation error:", error);

        message.style.color = "#dc2626";

        message.textContent =
            error.message.includes("Failed to fetch")
                ? "Cannot connect to the server. Please check your backend."
                : error.message;

        isSubmitting = false;

        continueButton.disabled = false;
        skipButton.disabled = false;

        continueButton.innerHTML = 'Continue <span>→</span>';
    }
}


// ========================================
// CONTINUE
// ========================================

form.addEventListener("submit", event => {

    event.preventDefault();

    // Preferences are currently frontend-only.
    createAccount();

});


// ========================================
// SKIP FOR NOW
// ========================================

skipButton.addEventListener("click", () => {

    createAccount();

});
