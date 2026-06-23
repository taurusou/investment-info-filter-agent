# Import json to read JSON data from mock_news.json
import json
# Import Path 
from pathlib import Path

"""
    Get mock news for a given stock ticker.

    Example:
    If ticker is "AAPL", this function looks inside mock_news.json
    and returns the list of mock Apple news items.

    This is temporary before connecting a real financial news API.
"""
def get_mock_news(ticker):
    # Convert ticker to uppercase
    ticker = ticker.upper()

    # Path to the mock news data file
    file_path = Path("data/mock_news.json")

    # Open and read the JSON file
    with open(file_path, "r", encoding="utf-8") as file:
        news_data = json.load(file)

    # Return the news list for the ticker
    # If the ticker does not exist, return an empty list
    return news_data.get(ticker, [])
