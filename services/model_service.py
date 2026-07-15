import json
import os
import re
from typing import Any, Dict, List

import requests
from dotenv import load_dotenv

load_dotenv()


def _extract_json_payload(raw_response: str) -> Dict[str, Any]:
    text = (raw_response or "").strip()

    if not text:
        raise ValueError("Empty response from model")

    fenced_match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.IGNORECASE | re.DOTALL)
    if fenced_match:
        text = fenced_match.group(1).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"(\{.*\})", text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        raise


def _call_openai(prompt: str, system_prompt: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    payload = {
        "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }

    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=60,
    )
    response.raise_for_status()

    data = response.json()
    return data["choices"][0]["message"]["content"]


def _heuristic_analysis(ticker: str, news_items: List[Dict[str, Any]]) -> Dict[str, Any]:
    results = []

    for item in news_items:
        content = item["content"].lower()

        if "strong demand" in content or "new ai features" in content:
            label = "Positive"
            reason = "This event may improve investor sentiment or support future business growth."
        elif "regulatory pressure" in content or "lower-than-expected" in content:
            label = "Negative"
            reason = "This event may create uncertainty or suggest possible pressure on future performance."
        else:
            label = "Neutral"
            reason = "The possible stock impact is unclear based on the available information."

        results.append(
            {
                "title": item["title"],
                "source": item["source"],
                "date": item["date"],
                "url": item["url"],
                "summary": item["content"],
                "label": label,
                "reason": reason,
                "confidence": "Medium",
            }
        )

    return {
        "ticker": ticker.upper(),
        "items": results,
        "disclaimer": "This tool is for educational and informational purposes only. It does not provide financial advice.",
    }


def analyze_news(ticker: str, news_items: List[Dict[str, Any]]) -> Dict[str, Any]:
    prompt = (
        f"Analyze the following stock news for ticker {ticker.upper()}. "
        "Return only valid JSON with this structure: "
        '{"ticker": "AAPL", "items": [{"title": "...", "source": "...", "date": "...", "url": "...", "summary": "...", "label": "Positive|Neutral|Negative", "reason": "...", "confidence": "High|Medium|Low"}], "disclaimer": "..."}.'
        "Keep summaries beginner-friendly and concise.\n"
        f"News items:\n{json.dumps(news_items, indent=2)}"
    )
    system_prompt = (
        "You are a concise investment news analysis assistant. "
        "Classify each item as Positive, Neutral, or Negative based on likely market impact. "
        "Do not provide financial advice. Return valid JSON only."
    )

    try:
        raw_response = _call_openai(prompt, system_prompt)
        payload = _extract_json_payload(raw_response)

        if not isinstance(payload, dict):
            raise ValueError("Model response was not a JSON object")

        payload.setdefault("ticker", ticker.upper())
        payload.setdefault("disclaimer", "This tool is for educational and informational purposes only. It does not provide financial advice.")
        payload.setdefault("items", [])
        return payload
    except (RuntimeError, requests.RequestException, ValueError, json.JSONDecodeError):
        return _heuristic_analysis(ticker, news_items)


def answer_follow_up(question: str, previous_analysis: Dict[str, Any]) -> Dict[str, Any]:
    prompt = (
        "Answer the user's follow-up question using the previous analysis. "
        "Keep the answer concise and educational. "
        "Return only valid JSON with this structure: {\"answer\": \"...\"}.\n"
        f"Question: {question}\n"
        f"Previous analysis: {json.dumps(previous_analysis, indent=2)}"
    )
    system_prompt = (
        "You are a helpful financial education assistant. "
        "Answer simple follow-up questions based on the provided analysis. "
        "Do not give direct buy/sell advice. Return valid JSON only."
    )

    try:
        raw_response = _call_openai(prompt, system_prompt)
        payload = _extract_json_payload(raw_response)
        if isinstance(payload, dict) and payload.get("answer"):
            return payload
    except (RuntimeError, requests.RequestException, ValueError, json.JSONDecodeError):
        pass

    return {
        "answer": "Based on the previous analysis, the label is only a possible interpretation of the news impact. It should not be treated as direct buy or sell advice."
    }
