let latestAnalysis = null;

async function analyzeTicker() {
  const ticker = document.getElementById("tickerInput").value;
  const resultsDiv = document.getElementById("results");

  resultsDiv.innerHTML = "Loading...";

  const response = await fetch("/analyze", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ ticker: ticker })
  });

  const data = await response.json();

  if (!response.ok) {
    resultsDiv.innerHTML = `<p class="error">${data.error}</p>`;
    return;
  }

  latestAnalysis = data;
  displayResults(data);

  document.getElementById("followUpSection").classList.remove("hidden");
}

function displayResults(data) {
  const resultsDiv = document.getElementById("results");

  let html = `<h2>Analysis for ${data.ticker}</h2>`;

  data.items.forEach(item => {
    html += `
      <div class="card">
        <h3>${item.title}</h3>
        <p><strong>Date:</strong> ${item.date}</p>
        <p><strong>Source:</strong> ${item.source}</p>
        <p><strong>Summary:</strong> ${item.summary}</p>
        <p><strong>Possible Impact:</strong> ${item.label}</p>
        <p><strong>Reason:</strong> ${item.reason}</p>
        <p><strong>Confidence:</strong> ${item.confidence}</p>
      </div>
    `;
  });

  html += `<p class="disclaimer">${data.disclaimer}</p>`;

  resultsDiv.innerHTML = html;
}

async function askFollowUp() {
  const question = document.getElementById("questionInput").value;
  const answerDiv = document.getElementById("followUpAnswer");

  answerDiv.innerHTML = "Thinking...";

  const response = await fetch("/follow-up", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      question: question,
      previous_analysis: latestAnalysis
    })
  });

  const data = await response.json();

  if (!response.ok) {
    answerDiv.innerHTML = `<p class="error">${data.error}</p>`;
    return;
  }

  answerDiv.innerHTML = `<p>${data.answer}</p>`;
}
