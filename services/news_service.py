import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List

import requests
from dotenv import load_dotenv

load_dotenv()


def _extract_json_list(raw_response: str) -> List[Dict[str, Any]]:
    """Parse JSON list output from the OpenAI response."""
    text = (raw_response or "").strip()
    if not text:
        return []

    fenced_match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.IGNORECASE | re.DOTALL)
    if fenced_match:
        text = fenced_match.group(1).strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict) and "items" in parsed:
            return parsed.get("items", [])
    except json.JSONDecodeError:
        match = re.search(r"(\[.*\])", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
    return []


def _get_mock_news(ticker: str) -> List[Dict[str, Any]]:
    """Load fallback mock news from the local data file."""
    ticker = ticker.upper()
    file_path = Path("data/mock_news.json")

    try:
        with open(file_path, "r", encoding="utf-8") as file:
            news_data = json.load(file)
        return news_data.get(ticker, [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _get_news_from_openai(ticker: str) -> List[Dict[str, Any]]:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        print("news_service: OPENAI_API_KEY is missing or empty, using mock fallback")
        return []

    model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    print(f"news_service: using OpenAI model {model_name} for ticker {ticker}")

    prompt = (
        f"Provide up to 5 recent stock news items for the company or ticker '{ticker}'. "
        "Return only valid JSON in the form of a list of objects. "
        "Each object should contain: title, source, date, url, content. "
        "Do not include any explanation outside the JSON. "
        "If you do not know the exact date or url, leave the field blank, but still provide the item."
    )

    payload = {
        "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        "messages": [
            {"role": "system", "content": "You are a news retrieval assistant. Provide stock news in strict JSON format."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }

    try:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=60,
        )
        if response.status_code != 200:
            print(f"news_service: OpenAI returned status {response.status_code}: {response.text}")
            return []

        data = response.json()
        raw = data["choices"][0]["message"]["content"]
        news_items = _extract_json_list(raw)

        valid_items = []
        for item in news_items:
            if not isinstance(item, dict):
                continue
            valid_items.append(
                {
                    "title": item.get("title", "").strip(),
                    "source": item.get("source", "").strip(),
                    "date": item.get("date", "").strip(),
                    "url": item.get("url", "").strip(),
                    "content": item.get("content", "").strip(),
                }
            )
        if not valid_items:
            print(f"news_service: OpenAI response parsed to zero valid items. raw=\n{raw}")
        return valid_items
    except requests.RequestException as exc:
        print(f"news_service: OpenAI request failed: {exc}")
        return []
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        print(f"news_service: OpenAI parsing failed: {exc}")
        return []


def get_news(ticker: str) -> (List[Dict[str, Any]], bool):
    """
    Fetch news for a given ticker, using OpenAI as the primary source.
    Falls back to local mock news if OpenAI fails.

    Returns a tuple: (news_items, used_openai)
    """
    ticker = ticker.upper()
    news_items = _get_news_from_openai(ticker)
    if news_items:
        print(f"news_service: fetched {len(news_items)} items from OpenAI for {ticker}")
        return news_items, True

    mock = _get_mock_news(ticker)
    print(f"news_service: falling back to mock data ({len(mock)} items) for {ticker}")
    return mock, False
