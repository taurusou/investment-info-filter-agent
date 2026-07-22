(function () {
  "use strict";

  let latestAnalysis = null;
  let analysisRequestId = 0;
  let followUpRequestId = 0;

  const DEFAULT_DISCLAIMER =
    "This tool is for educational and informational purposes only. It does not provide financial advice.";

  function byId(id) {
    return document.getElementById(id);
  }

  function createElement(tagName, className, text) {
    const element = document.createElement(tagName);

    if (className) {
      element.className = className;
    }

    if (text !== undefined) {
      element.textContent = text;
    }

    return element;
  }

  function textValue(value, fallback) {
    if (typeof value === "string") {
      const trimmed = value.trim();
      return trimmed || fallback;
    }

    if (typeof value === "number" && Number.isFinite(value)) {
      return String(value);
    }

    return fallback;
  }

  function pluralize(count, singular, plural) {
    return count === 1 ? singular : plural;
  }

  function getButtonLabel(button) {
    if (!button) {
      return null;
    }

    return button.querySelector("[data-button-label], .button-label") || button;
  }

  function setButtonLoading(button, isLoading, loadingLabel) {
    if (!button) {
      return;
    }

    const label = getButtonLabel(button);

    if (!button.dataset.defaultLabel) {
      button.dataset.defaultLabel = textValue(label.textContent, "Submit");
    }

    button.disabled = isLoading;
    button.classList.toggle("is-loading", isLoading);
    button.setAttribute("aria-busy", String(isLoading));
    label.textContent = isLoading ? loadingLabel : button.dataset.defaultLabel;
  }

  function configureLiveRegion(element, role) {
    if (!element) {
      return;
    }

    element.setAttribute("aria-live", role === "alert" ? "assertive" : "polite");
    element.setAttribute("aria-atomic", "true");
    element.setAttribute("role", role || "status");
  }

  function setSearchFeedback(message, isError) {
    const feedback = byId("searchFeedback");

    if (!feedback) {
      return;
    }

    configureLiveRegion(feedback, isError ? "alert" : "status");
    feedback.textContent = message || "";
    feedback.classList.toggle("error", Boolean(isError));
  }

  function setFieldValidity(input, isValid) {
    if (!input) {
      return;
    }

    input.setAttribute("aria-invalid", String(!isValid));
  }

  function setRegionBusy(element, isBusy) {
    if (!element) {
      return;
    }

    element.setAttribute("aria-busy", String(isBusy));
  }

  function renderLoading(container, title) {
    if (!container) {
      return;
    }

    container.replaceChildren();
    configureLiveRegion(container, "status");
    setRegionBusy(container, true);

    const loadingState = createElement("div", "loading-state");
    const loadingHeader = createElement("div", "loading-header");
    const indicator = createElement("span", "skeleton");
    const heading = createElement("p", "", title);

    indicator.setAttribute("aria-hidden", "true");
    loadingHeader.append(indicator, heading);
    loadingState.append(loadingHeader);

    for (let index = 0; index < 3; index += 1) {
      const card = createElement("div", "skeleton skeleton-card");
      card.setAttribute("aria-hidden", "true");

      for (let lineIndex = 0; lineIndex < 3; lineIndex += 1) {
        const line = createElement("span", "skeleton skeleton-line");
        card.append(line);
      }

      loadingState.append(card);
    }

    container.append(loadingState);
  }

  function renderStatePanel(container, message, isError) {
    if (!container) {
      return;
    }

    container.replaceChildren();
    setRegionBusy(container, false);

    const className = isError
      ? "state-panel state-panel--error"
      : "state-panel";
    const panel = createElement("div", className);
    const icon = createElement("span", "state-icon", isError ? "!" : "i");
    const copy = createElement("p", isError ? "error" : "", message);

    icon.setAttribute("aria-hidden", "true");
    panel.setAttribute("role", isError ? "alert" : "status");
    panel.append(icon, copy);
    container.append(panel);
  }

  function resetFollowUp() {
    followUpRequestId += 1;

    const section = byId("followUpSection");
    const answer = byId("followUpAnswer");
    const input = byId("questionInput");
    const button = byId("followUpButton");

    if (section) {
      section.classList.add("hidden");
      section.setAttribute("aria-hidden", "true");
    }

    if (answer) {
      answer.replaceChildren();
      setRegionBusy(answer, false);
    }

    if (input) {
      input.value = "";
      setFieldValidity(input, true);
    }

    setButtonLoading(button, false, "Thinking...");
  }

  function revealFollowUp() {
    const section = byId("followUpSection");

    if (!section) {
      return;
    }

    section.classList.remove("hidden");
    section.setAttribute("aria-hidden", "false");
  }

  function normalizeImpact(value) {
    const normalized = textValue(value, "Neutral").toLowerCase();

    if (normalized === "positive") {
      return { label: "Positive", slug: "positive" };
    }

    if (normalized === "negative") {
      return { label: "Negative", slug: "negative" };
    }

    return { label: "Neutral", slug: "neutral" };
  }

  function normalizeConfidence(value) {
    const normalized = textValue(value, "").toLowerCase();

    if (normalized === "high") {
      return { label: "High confidence", slug: "high" };
    }

    if (normalized === "medium") {
      return { label: "Medium confidence", slug: "medium" };
    }

    if (normalized === "low") {
      return { label: "Low confidence", slug: "low" };
    }

    return { label: "Confidence unavailable", slug: "unknown" };
  }

  function formatDate(value) {
    const raw = textValue(value, "");

    if (!raw) {
      return { label: "Date unavailable", dateTime: "" };
    }

    const dateOnly = /^\d{4}-\d{2}-\d{2}$/.test(raw);
    const parsed = new Date(dateOnly ? `${raw}T00:00:00Z` : raw);

    if (Number.isNaN(parsed.getTime())) {
      return { label: raw, dateTime: "" };
    }

    const options = {
      month: "short",
      day: "numeric",
      year: "numeric"
    };

    if (dateOnly) {
      options.timeZone = "UTC";
    }

    return {
      label: new Intl.DateTimeFormat("en-US", options).format(parsed),
      dateTime: raw
    };
  }

  function validatedArticleUrl(value) {
    const raw = textValue(value, "");

    if (!raw) {
      return null;
    }

    try {
      const url = new URL(raw);
      return url.protocol === "http:" || url.protocol === "https:" ? url.href : null;
    } catch (error) {
      return null;
    }
  }

  function buildSignalStat(label, count, slug) {
    const stat = createElement("div", `signal-stat impact-${slug}`);
    const number = createElement("strong", "", String(count));
    const copy = createElement("span", "", label);

    stat.append(number, copy);
    return stat;
  }

  function buildNewsCard(item) {
    const impact = normalizeImpact(item.label);
    const confidence = normalizeConfidence(item.confidence);
    const date = formatDate(item.date);
    const source = textValue(item.source, "Source unavailable");
    const articleUrl = validatedArticleUrl(item.url);

    const card = createElement("article", `news-card impact-${impact.slug}`);
    const cardTop = createElement("div", "card-top");
    const meta = createElement("div", "article-meta");
    const sourceName = createElement("span", "", source);
    const divider = createElement("span", "meta-divider", "\u2022");
    const time = createElement("time", "", date.label);
    const badge = createElement(
      "span",
      `impact-badge impact-${impact.slug}`,
      impact.label
    );

    divider.setAttribute("aria-hidden", "true");

    if (date.dateTime) {
      time.setAttribute("datetime", date.dateTime);
    }

    meta.append(sourceName, divider, time);
    cardTop.append(meta, badge);

    const title = createElement(
      "h3",
      "article-title",
      textValue(item.title, "Untitled news item")
    );

    const summary = createElement("div", "article-summary");
    const summaryLabel = createElement("span", "summary-label", "Summary");
    const summaryCopy = createElement(
      "p",
      "",
      textValue(item.summary, "No summary was provided for this article.")
    );
    summary.append(summaryLabel, summaryCopy);

    const insight = createElement("div", "insight-box");
    const insightLabel = createElement("span", "summary-label", "Why it matters");
    const insightCopy = createElement(
      "p",
      "",
      textValue(item.reason, "The possible market impact is not yet clear.")
    );
    insight.append(insightLabel, insightCopy);

    const footer = createElement("footer", "card-footer");
    const confidenceView = createElement(
      "div",
      `confidence confidence--${confidence.slug}`
    );
    const confidenceDot = createElement("span", "confidence-dot");
    const confidenceLabel = createElement("span", "", confidence.label);

    confidenceDot.setAttribute("aria-hidden", "true");
    confidenceView.append(confidenceDot, confidenceLabel);
    footer.append(confidenceView);

    if (articleUrl) {
      const sourceLink = createElement("a", "source-link", "Read original article");
      sourceLink.href = articleUrl;
      sourceLink.target = "_blank";
      sourceLink.rel = "noopener noreferrer";
      footer.append(sourceLink);
    } else {
      const unavailable = createElement(
        "span",
        "source-link source-link--unavailable",
        "Source link unavailable"
      );
      footer.append(unavailable);
    }

    card.append(cardTop, title, summary, insight, footer);
    return card;
  }

  function displayResults(data) {
    const results = byId("results");

    if (!results) {
      return;
    }

    const payload = data && typeof data === "object" ? data : {};
    const items = Array.isArray(payload.items)
      ? payload.items.filter((item) => item && typeof item === "object")
      : [];
    const inputTicker = byId("tickerInput");
    const ticker = textValue(
      payload.ticker,
      inputTicker ? textValue(inputTicker.value, "Selected company") : "Selected company"
    ).toUpperCase();

    const counts = { positive: 0, neutral: 0, negative: 0 };
    items.forEach((item) => {
      counts[normalizeImpact(item.label).slug] += 1;
    });

    results.replaceChildren();
    configureLiveRegion(results, "status");
    setRegionBusy(results, false);

    const summary = createElement("section", "results-summary");
    const summaryHeading = createElement("div", "summary-heading");
    const headingCopy = createElement("div");
    const heading = createElement("h2", "results-title", `Analysis for ${ticker}`);
    const meta = createElement(
      "p",
      "summary-meta",
      `${items.length} ${pluralize(items.length, "article", "articles")} reviewed`
    );
    const sourceBadge = createElement("span", "source-badge");

    if (payload.news_source_used_openai === true) {
      sourceBadge.classList.add("source-badge--live");
      sourceBadge.textContent = "AI news retrieval";
    } else if (payload.news_source_used_openai === false) {
      sourceBadge.classList.add("source-badge--fallback");
      sourceBadge.textContent = "Sample dataset";
    } else {
      sourceBadge.textContent = "Analysis complete";
    }

    headingCopy.append(heading, meta);
    summaryHeading.append(headingCopy, sourceBadge);

    const signalGrid = createElement("div", "signal-grid");
    signalGrid.append(
      buildSignalStat("Positive", counts.positive, "positive"),
      buildSignalStat("Neutral", counts.neutral, "neutral"),
      buildSignalStat("Negative", counts.negative, "negative")
    );

    summary.append(summaryHeading, signalGrid);
    results.append(summary);

    if (items.length > 0) {
      const newsList = createElement("div", "news-list");
      items.forEach((item) => newsList.append(buildNewsCard(item)));
      results.append(newsList);
    } else {
      const emptyState = createElement("div", "state-panel");
      const emptyIcon = createElement("span", "state-icon", "i");
      const emptyCopy = createElement(
        "p",
        "",
        "The analysis completed, but no news items were available to display."
      );
      emptyIcon.setAttribute("aria-hidden", "true");
      emptyState.setAttribute("role", "status");
      emptyState.append(emptyIcon, emptyCopy);
      results.append(emptyState);
    }

    const disclaimer = createElement(
      "p",
      "disclaimer",
      textValue(payload.disclaimer, DEFAULT_DISCLAIMER)
    );
    results.append(disclaimer);
  }

  async function requestJson(url, options) {
    let response;

    try {
      response = await fetch(url, options);
    } catch (error) {
      throw new Error("We couldn't reach the server. Check your connection and try again.");
    }

    let data;

    try {
      data = await response.json();
    } catch (error) {
      if (!response.ok) {
        throw new Error(`The server couldn't complete this request (${response.status}). Please try again.`);
      }

      throw new Error("The server returned an unexpected response. Please try again.");
    }

    if (!response.ok) {
      throw new Error(
        textValue(data && data.error, `The request failed (${response.status}). Please try again.`)
      );
    }

    if (!data || typeof data !== "object" || Array.isArray(data)) {
      throw new Error("The server returned incomplete data. Please try again.");
    }

    return data;
  }

  async function analyzeTicker(event) {
    if (event && typeof event.preventDefault === "function") {
      event.preventDefault();
    }

    const input = byId("tickerInput");
    const results = byId("results");
    const button = byId("analyzeButton");
    const ticker = input ? input.value.trim().toUpperCase() : "";
    const requestId = ++analysisRequestId;

    latestAnalysis = null;
    resetFollowUp();

    if (input) {
      input.value = ticker;
    }

    if (!ticker) {
      setFieldValidity(input, false);
      setButtonLoading(button, false, "Analyzing...");
      setSearchFeedback("Enter a ticker symbol to continue.", true);
      renderStatePanel(results, "Enter a ticker symbol to start an analysis.", true);

      if (input) {
        input.focus();
      }

      return;
    }

    setFieldValidity(input, true);
    setSearchFeedback(`Analyzing ${ticker}\u2026`, false);
    setButtonLoading(button, true, "Analyzing...");
    renderLoading(results, `Reviewing recent news for ${ticker}\u2026`);

    try {
      const data = await requestJson("/analyze", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ ticker: ticker })
      });

      if (requestId !== analysisRequestId) {
        return;
      }

      latestAnalysis = data;
      displayResults(data);

      const itemCount = Array.isArray(data.items) ? data.items.length : 0;
      if (itemCount > 0) {
        revealFollowUp();
      }
      setSearchFeedback(
        `${ticker} analysis ready: ${itemCount} ${pluralize(itemCount, "article", "articles")} reviewed.`,
        false
      );
    } catch (error) {
      if (requestId !== analysisRequestId) {
        return;
      }

      latestAnalysis = null;
      resetFollowUp();
      const message = textValue(error && error.message, "Something went wrong. Please try again.");
      renderStatePanel(results, message, true);
      setSearchFeedback(message, true);
    } finally {
      if (requestId === analysisRequestId) {
        setRegionBusy(results, false);
        setButtonLoading(button, false, "Analyzing...");
      }
    }
  }

  function renderFollowUpLoading(container) {
    if (!container) {
      return;
    }

    container.replaceChildren();
    setRegionBusy(container, true);

    const panel = createElement("div", "state-panel");
    const icon = createElement("span", "state-icon", "\u2026");
    const copy = createElement("p", "", "Reviewing the analysis\u2026");
    icon.setAttribute("aria-hidden", "true");
    panel.setAttribute("role", "status");
    panel.append(icon, copy);
    container.append(panel);
  }

  function renderFollowUpAnswer(container, answer) {
    if (!container) {
      return;
    }

    container.replaceChildren();
    setRegionBusy(container, false);

    const card = createElement("div", "answer-card");
    const label = createElement("p", "answer-label", "AI response");
    const copy = createElement(
      "p",
      "",
      textValue(answer, "No answer was returned. Please try asking in a different way.")
    );
    card.append(label, copy);
    container.append(card);
  }

  async function askFollowUp(event) {
    if (event && typeof event.preventDefault === "function") {
      event.preventDefault();
    }

    const input = byId("questionInput");
    const answerContainer = byId("followUpAnswer");
    const button = byId("followUpButton");
    const question = input ? input.value.trim() : "";
    const requestId = ++followUpRequestId;

    if (!question) {
      setFieldValidity(input, false);
      setButtonLoading(button, false, "Thinking...");
      setRegionBusy(answerContainer, false);
      renderStatePanel(answerContainer, "Enter a follow-up question to continue.", true);

      if (input) {
        input.focus();
      }

      return;
    }

    if (!latestAnalysis) {
      setButtonLoading(button, false, "Thinking...");
      setRegionBusy(answerContainer, false);
      renderStatePanel(
        answerContainer,
        "Run a news analysis before asking a follow-up question.",
        true
      );
      return;
    }

    setFieldValidity(input, true);
    setButtonLoading(button, true, "Thinking...");
    renderFollowUpLoading(answerContainer);

    try {
      const data = await requestJson("/follow-up", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          question: question,
          previous_analysis: latestAnalysis
        })
      });

      if (requestId !== followUpRequestId) {
        return;
      }

      renderFollowUpAnswer(answerContainer, data.answer);
    } catch (error) {
      if (requestId !== followUpRequestId) {
        return;
      }

      const message = textValue(error && error.message, "Something went wrong. Please try again.");
      renderStatePanel(answerContainer, message, true);
    } finally {
      if (requestId === followUpRequestId) {
        setRegionBusy(answerContainer, false);
        setButtonLoading(button, false, "Thinking...");
      }
    }
  }

  function initializeInterface() {
    const analyzeForm = byId("analyzeForm");
    const followUpForm = byId("followUpForm");
    const results = byId("results");
    const feedback = byId("searchFeedback");
    const answer = byId("followUpAnswer");

    if (analyzeForm) {
      analyzeForm.addEventListener("submit", analyzeTicker);
    }

    if (followUpForm) {
      followUpForm.addEventListener("submit", askFollowUp);
    }

    document.querySelectorAll("[data-ticker]").forEach((trigger) => {
      trigger.addEventListener("click", (event) => {
        event.preventDefault();
        const input = byId("tickerInput");
        const ticker = textValue(trigger.dataset.ticker, "").toUpperCase();

        if (!input || !ticker) {
          return;
        }

        input.value = ticker;
        analyzeTicker();
      });
    });

    document.querySelectorAll("[data-question]").forEach((trigger) => {
      trigger.addEventListener("click", (event) => {
        event.preventDefault();
        const input = byId("questionInput");
        const question = textValue(trigger.dataset.question, "");

        if (!input || !question) {
          return;
        }

        input.value = question;
        askFollowUp();
      });
    });

    configureLiveRegion(results, "status");
    configureLiveRegion(feedback, "status");
    configureLiveRegion(answer, "status");
    resetFollowUp();
  }

  window.analyzeTicker = analyzeTicker;
  window.displayResults = displayResults;
  window.askFollowUp = askFollowUp;

  document.addEventListener("DOMContentLoaded", initializeInterface, { once: true });
})();
