import json
from pathlib import Path


def get_mock_news(ticker):
    ticker = ticker.upper()

    file_path = Path("data/mock_news.json")

    with open(file_path, "r", encoding="utf-8") as file:
        news_data = json.load(file)

    return news_data.get(ticker, [])
