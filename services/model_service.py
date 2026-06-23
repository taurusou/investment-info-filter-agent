def analyze_news(ticker, news_items):
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

        results.append({
            "title": item["title"],
            "source": item["source"],
            "date": item["date"],
            "url": item["url"],
            "summary": item["content"],
            "label": label,
            "reason": reason,
            "confidence": "Medium"
        })

    return {
        "ticker": ticker.upper(),
        "items": results,
        "disclaimer": "This tool is for educational and informational purposes only. It does not provide financial advice."
    }


def answer_follow_up(question, previous_analysis):
    return {
        "answer": "Based on the previous analysis, the label is only a possible interpretation of the news impact. It should not be treated as direct buy or sell advice."
    }
