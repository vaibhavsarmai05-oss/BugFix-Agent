const analyzeBtn = document.getElementById("analyzeBtn");
const codeInput = document.getElementById("codeInput");
const message = document.getElementById("message");

// Keep a reference to the last submitted code and proposed fix so the
// Verify Fix button can access them without re-reading the DOM.
let _lastSubmittedCode = "";
let _lastFixedCode = "";

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
    _lastSubmittedCode = code;
    _lastFixedCode = "";

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

        // ── Proposed fix + Copy + Verify buttons ─────────────────────
        if (data.fixed_code) {
            _lastFixedCode = data.fixed_code;
            html += `
                <div class="result-fixed">
                    <div class="code-card-header">
                        <strong>Proposed Fix:</strong>
                        <span class="card-actions">
                            <button class="copy-btn" id="copyFixedBtn">Copy Fixed Code</button>
                            <button class="verify-btn" id="verifyBtn">Verify Fix</button>
                        </span>
                    </div>
                    <pre id="fixedCodePre">${escapeHtml(data.fixed_code)}</pre>
                </div>
                <div id="verifyResult"></div>
            `;
        }

        // ── Regression test + Copy button ────────────────────────────
        if (data.regression_test) {
            html += `
                <div class="result-regression">
                    <div class="code-card-header">
                        <strong>Regression Test:</strong>
                        <button class="copy-btn" id="copyTestBtn">Copy Regression Test</button>
                    </div>
                    <pre id="regressionTestPre">${escapeHtml(data.regression_test)}</pre>
                </div>
            `;
        }

        message.innerHTML = html;

        // Attach handlers after the HTML is in the DOM ────────────────
        if (data.fixed_code) {
            attachCopyHandler("copyFixedBtn", data.fixed_code);
            attachVerifyHandler(code, data.fixed_code);
        }
        if (data.regression_test) {
            attachCopyHandler("copyTestBtn", data.regression_test);
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
 * Wire up a Copy button (by element id) to write `textToCopy` to the clipboard.
 * Falls back gracefully when the Clipboard API is unavailable.
 */
function attachCopyHandler(btnId, textToCopy) {
    const btn = document.getElementById(btnId);
    if (!btn) return;

    btn.addEventListener("click", function () {
        if (!navigator.clipboard) {
            btn.textContent = "Copy unavailable";
            return;
        }

        navigator.clipboard.writeText(textToCopy).then(function () {
            btn.textContent = "Copied!";
            btn.disabled = true;
            setTimeout(function () {
                btn.textContent = btn.id === "copyFixedBtn"
                    ? "Copy Fixed Code"
                    : "Copy Regression Test";
                btn.disabled = false;
            }, 2000);
        }).catch(function () {
            btn.textContent = "Copy failed";
            setTimeout(function () {
                btn.textContent = btn.id === "copyFixedBtn"
                    ? "Copy Fixed Code"
                    : "Copy Regression Test";
            }, 2000);
        });
    });
}

/**
 * Wire up the Verify Fix button.
 * POSTs { original_code, fixed_code } to /verify and renders the result
 * in the #verifyResult placeholder that was injected alongside the fix card.
 */
function attachVerifyHandler(originalCode, fixedCode) {
    const btn = document.getElementById("verifyBtn");
    const resultDiv = document.getElementById("verifyResult");
    if (!btn || !resultDiv) return;

    btn.addEventListener("click", async function () {
        btn.disabled = true;
        btn.textContent = "Verifying...";
        resultDiv.innerHTML = "";

        try {
            const resp = await fetch("http://127.0.0.1:8000/verify", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    original_code: originalCode,
                    fixed_code: fixedCode
                })
            });

            const data = await resp.json();

            if (data.success) {
                let inner = `<strong>&#10003; Verification passed</strong> — the fixed code runs without errors.`;
                if (data.stdout) {
                    inner += `<pre>${escapeHtml(data.stdout)}</pre>`;
                }
                resultDiv.innerHTML = `<div class="result-verify result-verify-pass">${inner}</div>`;
            } else {
                let inner = `<strong>&#10007; Verification failed</strong> — the fixed code still produces an error.`;
                if (data.error) {
                    inner += `<pre>${escapeHtml(data.error)}</pre>`;
                }
                resultDiv.innerHTML = `<div class="result-verify result-verify-fail">${inner}</div>`;
            }
        } catch (_) {
            resultDiv.innerHTML = `
                <div class="result-verify result-verify-fail">
                    <strong>Could not connect to the backend for verification.</strong>
                </div>
            `;
        } finally {
            btn.disabled = false;
            btn.textContent = "Verify Fix";
        }
    });
}
