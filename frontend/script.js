const analyzeBtn = document.getElementById("analyzeBtn");
const codeInput = document.getElementById("codeInput");
const message = document.getElementById("message");

analyzeBtn.addEventListener("click", async function () {
    const code = codeInput.value.trim();

    if (code === "") {
        message.textContent = "Please paste some code first.";
        return;
    }

    message.textContent = "Analyzing code...";

    try {
        const response = await fetch("http://127.0.0.1:8000/analyze", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                code: code
            })
        });

        const data = await response.json();

        message.innerHTML = `
    <div class="result-error">
        <strong>Issue:</strong> ${data.message}
    </div>
`;

if (data.suggestion) {
    message.innerHTML += `
        <div class="result-suggestion">
            <strong>Suggestion:</strong> ${data.suggestion}
        </div>
    `;
}

if (data.fixed_code) {
    message.innerHTML += `
        <div class="result-fixed">
            <strong>Fixed Code:</strong>
            <pre>${data.fixed_code}</pre>
        </div>
    `;
}

    } catch (error) {
        message.textContent = "Could not connect to the backend.";
    }
});