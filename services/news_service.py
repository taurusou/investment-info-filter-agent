import json
import os
from pathlib import Path
from typing import Any, Dict, List

import requests
from dotenv import load_dotenv

load_dotenv()


def _get_mock_news(ticker: str) -> List[Dict[str, Any]]:
    """
    Fallback: read mock news from local JSON file.
    """
    ticker = ticker.upper()
    file_path = Path("data/mock_news.json")

    try:
        with open(file_path, "r", encoding="utf-8") as file:
            news_data = json.load(file)
        return news_data.get(ticker, [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _get_real_news(ticker: str) -> List[Dict[str, Any]]:
    """
    Fetch real news from NewsAPI based on ticker symbol.
    """
    api_key = os.getenv("NEWSAPI_KEY", "").strip()
    if not api_key:
        return []

    ticker = ticker.upper()
    
    ticker_map = {
        "AAPL": "Apple",
        "TSLA": "Tesla",
        "NVDA": "Nvidia",
        "GOOGL": "Google",
        "MSFT": "Microsoft",
        "AMZN": "Amazon",
        "META": "Meta",
        "NFLX": "Netflix",
    }
    
    company_name = ticker_map.get(ticker, ticker)
    
    try:
        params = {
            "q": company_name,
            "sortBy": "publishedAt",
            "language": "en",
            "pageSize": 10,
            "apiKey": api_key,
        }
        
        response = requests.get(
            "https://newsapi.org/v2/everything",
            params=params,
            timeout=10,
        )
        response.raise_for_status()
        
        data = response.json()
        if data.get("status") != "ok":
            return []
        
        articles = data.get("articles", [])
        news_items = []
        
        for article in articles:
            news_items.append({
                "title": article.get("title", ""),
                "source": article.get("source", {}).get("name", "News"),
                "date": article.get("publishedAt", "")[:10],
                "url": article.get("url", ""),
                "content": article.get("description", ""),
            })
        
        return news_items
    except (requests.RequestException, KeyError, ValueError):
        return []


def get_mock_news(ticker: str) -> List[Dict[str, Any]]:
    """
    Get news for a given stock ticker.
    First tries to fetch from real NewsAPI, falls back to mock data.
    """
    ticker = ticker.upper()
    
    real_news = _get_real_news(ticker)
    if real_news:
        return real_news
    
    return _get_mock_news(ticker)
