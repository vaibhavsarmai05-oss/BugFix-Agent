const analyzeBtn = document.getElementById("analyzeBtn");
const codeInput = document.getElementById("codeInput");
const result = document.getElementById("result");

function escapeHtml(text) {
    if (text === null || text === undefined) return "";

    return String(text)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function formatAnalysis(message) {
    if (typeof message === "object" && message !== null) {
        let output = "";

        if (message.explanation) {
            output += `<p><strong>Explanation:</strong> ${escapeHtml(message.explanation)}</p>`;
        }

        if (message.suggestion) {
            output += `<p><strong>Suggestion:</strong> ${escapeHtml(message.suggestion)}</p>`;
        }

        if (!output) {
            output = escapeHtml(JSON.stringify(message));
        }

        return output;
    }

    return escapeHtml(message);
}

function getFixedCode(fixedCode) {
    if (typeof fixedCode === "object" && fixedCode !== null) {
        return fixedCode.fixed_code || "";
    }

    return fixedCode || "";
}

function getRegressionTest(test) {
    if (typeof test === "object" && test !== null) {
        return test.test_code || "";
    }

    return test || "";
}

analyzeBtn.addEventListener("click", async () => {
    const code = codeInput.value.trim();

    if (!code) {
        alert("Please enter some Python code.");
        return;
    }

    result.innerHTML = "<p>Analyzing code...</p>";

    try {
        const response = await fetch("/analyze", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                code: code
            })
        });

        const data = await response.json();

        if (data.success) {
            result.innerHTML = `
                <h2>Analysis</h2>
                <p><strong>Status:</strong> Code executed successfully.</p>
                <pre>${escapeHtml(data.stdout || "")}</pre>
            `;

            return;
        }

        const fixedCode = getFixedCode(data.fixed_code);
        const regressionTest = getRegressionTest(data.regression_test);

        let html = `
            <h2>Analysis</h2>

            <p><strong>Issue:</strong> ${escapeHtml(data.error || data.message)}</p>

            <div>
                ${formatAnalysis(data.message)}
            </div>
        `;

        if (fixedCode) {
            html += `
                <h3>Proposed Fix:</h3>

                <pre id="fixedCode">${escapeHtml(fixedCode)}</pre>

                <button id="copyFixBtn">Copy Fixed Code</button>
                <button id="verifyBtn">Verify Fix</button>
            `;
        } else {
            html += `
                <h3>Proposed Fix:</h3>
                <p>${escapeHtml(
                    data.fixed_code?.message ||
                    "No automatic fix is available."
                )}</p>
            `;
        }

        if (regressionTest) {
            html += `
                <h3>Regression Test:</h3>

                <pre id="regressionTest">${escapeHtml(regressionTest)}</pre>

                <button id="copyTestBtn">Copy Regression Test</button>
            `;
        }

        result.innerHTML = html;

        const copyFixBtn = document.getElementById("copyFixBtn");

        if (copyFixBtn) {
            copyFixBtn.addEventListener("click", async () => {
                await navigator.clipboard.writeText(fixedCode);
                copyFixBtn.textContent = "Copied!";
            });
        }

        const verifyBtn = document.getElementById("verifyBtn");

        if (verifyBtn) {
            verifyBtn.addEventListener("click", async () => {
                verifyBtn.textContent = "Verifying...";

                try {
                    const verifyResponse = await fetch("/verify", {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json"
                        },
                        body: JSON.stringify({
                            original_code: code,
                            fixed_code: fixedCode
                        })
                    });

                    const verifyData = await verifyResponse.json();

                    if (verifyData.success) {
                        verifyBtn.textContent = "✓ Fix Verified";

                        const verification = document.createElement("p");
                        verification.innerHTML =
                            "<strong>Verification:</strong> Fix executed successfully.";

                        result.appendChild(verification);

                        if (verifyData.stdout) {
                            const output = document.createElement("pre");
                            output.textContent = verifyData.stdout;
                            result.appendChild(output);
                        }
                    } else {
                        verifyBtn.textContent = "Verify Fix";

                        const error = document.createElement("p");
                        error.innerHTML =
                            `<strong>Verification failed:</strong> ${escapeHtml(verifyData.error)}`;

                        result.appendChild(error);
                    }
                } catch (error) {
                    console.error(error);
                    verifyBtn.textContent = "Verify Fix";
                    alert("Could not verify the fix.");
                }
            });
        }

        const copyTestBtn = document.getElementById("copyTestBtn");

        if (copyTestBtn) {
            copyTestBtn.addEventListener("click", async () => {
                await navigator.clipboard.writeText(regressionTest);
                copyTestBtn.textContent = "Copied!";
            });
        }

    } catch (error) {
        console.error(error);

        result.innerHTML = `
            <h2>Error</h2>
            <p>Could not connect to BugFix Agent.</p>
            <p>${escapeHtml(error.message)}</p>
        `;
    }
});