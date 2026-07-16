import json
from pathlib import Path
from typing import Any, Dict, List


def get_mock_news(ticker: str) -> List[Dict[str, Any]]:
    """
    Get mock news for a given stock ticker from local JSON file.
    This data is then analyzed by OpenAI for classification and insights.
    """
    ticker = ticker.upper()
    file_path = Path("data/mock_news.json")

    try:
        with open(file_path, "r", encoding="utf-8") as file:
            news_data = json.load(file)
        return news_data.get(ticker, [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []
