const analyzeBtn = document.getElementById("analyzeBtn");
const codeInput = document.getElementById("codeInput");
const message = document.getElementById("message");

analyzeBtn.addEventListener("click", async function () {
    const code = codeInput.value.trim();

    if (code === "") {
        message.innerHTML = `
            <div class="result-error">
                <strong>Please paste some code first.</strong>
            </div>
        `;
        return;
    }

    // ── Loading state ────────────────────────────────────────────────
    setLoading(true);
    message.innerHTML = "";

    try {
        const response = await fetch("http://127.0.0.1:8000/analyze", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ code: code })
        });

        const data = await response.json();

        // ── Success ──────────────────────────────────────────────────
        if (data.status === "success") {
            let html = `
                <div class="result-fixed">
                    <strong>&#10003; ${escapeHtml(data.message)}</strong>
                </div>
            `;
            if (data.stdout) {
                html += `
                    <div class="result-suggestion">
                        <strong>Output:</strong>
                        <pre>${escapeHtml(data.stdout)}</pre>
                    </div>
                `;
            }
            message.innerHTML = html;
            return;
        }

        // ── Error header ─────────────────────────────────────────────
        let html = `
            <div class="result-error">
                <strong>Issue:</strong> ${escapeHtml(data.message)}
            </div>
        `;

        // ── Issues list (optional array field) ───────────────────────
        if (Array.isArray(data.issues) && data.issues.length > 0) {
            const items = data.issues
                .map(issue => `<li>${escapeHtml(String(issue))}</li>`)
                .join("");
            html += `
                <div class="result-issues">
                    <strong>Issues found:</strong>
                    <ul class="issues-list">${items}</ul>
                </div>
            `;
        }

        // ── Explanation ──────────────────────────────────────────────
        if (data.explanation) {
            html += `
                <div class="result-suggestion">
                    <strong>Explanation:</strong> ${escapeHtml(data.explanation)}
                </div>
            `;
        }

        // ── Suggestion ───────────────────────────────────────────────
        if (data.suggestion) {
            html += `
                <div class="result-suggestion">
                    <strong>Suggestion:</strong> ${escapeHtml(data.suggestion)}
                </div>
            `;
        }

        // ── Fixed code + Copy button ─────────────────────────────────
        if (data.fixed_code) {
            html += `
                <div class="result-fixed">
                    <div class="fixed-code-header">
                        <strong>Fixed Code:</strong>
                        <button class="copy-btn" id="copyBtn">Copy</button>
                    </div>
                    <pre id="fixedCodePre">${escapeHtml(data.fixed_code)}</pre>
                </div>
            `;
        }

        message.innerHTML = html;

        // Attach copy handler after the HTML is in the DOM
        if (data.fixed_code) {
            attachCopyHandler(data.fixed_code);
        }

    } catch (error) {
        message.innerHTML = `
            <div class="result-error">
                <strong>Could not connect to the backend.</strong>
            </div>
        `;
    } finally {
        // ── Always restore button ────────────────────────────────────
        setLoading(false);
    }
});


// ── Helpers ──────────────────────────────────────────────────────────

/**
 * Enable or disable the loading state on the Analyze button.
 */
function setLoading(isLoading) {
    analyzeBtn.disabled = isLoading;
    analyzeBtn.textContent = isLoading ? "Analyzing..." : "Analyze Code";
}

/**
 * Escape special HTML characters to prevent XSS from user-supplied code.
 */
function escapeHtml(text) {
    return String(text)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

/**
 * Wire up the Copy button to write fixedCode to the clipboard.
 * Falls back gracefully when the Clipboard API is unavailable.
 */
function attachCopyHandler(fixedCode) {
    const copyBtn = document.getElementById("copyBtn");
    if (!copyBtn) return;

    copyBtn.addEventListener("click", function () {
        if (!navigator.clipboard) {
            // Clipboard API not available (e.g. non-secure context)
            copyBtn.textContent = "Copy unavailable";
            return;
        }

        navigator.clipboard.writeText(fixedCode).then(function () {
            copyBtn.textContent = "Copied!";
            copyBtn.disabled = true;
            setTimeout(function () {
                copyBtn.textContent = "Copy";
                copyBtn.disabled = false;
            }, 2000);
        }).catch(function () {
            copyBtn.textContent = "Copy failed";
            setTimeout(function () {
                copyBtn.textContent = "Copy";
            }, 2000);
        });
    });
}
