"""
    Analyze stock-related news items.

    In the future, this function will call a real foundation model
    such as OpenAI or Gemini.

    For the first MVP version, this function uses simple keyword rules
    to simulate AI classification.

    It returns:
    - title
    - source
    - date
    - summary
    - possible impact label
    - reason
    - confidence
"""
def analyze_news(ticker, news_items):

    # Empty list to store analyzed news results
    results = []

    for item in news_items:
        # Convert content to lowercase, easier for keyword checking
        content = item["content"].lower()

        # Simple mock logic for testing
        # If the news contains positive-sounding keywords
        # label it as Positive.
        if "strong demand" in content or "new ai features" in content:
            label = "Positive"
            reason = "This event may improve investor sentiment or support future business growth."
            
        # If the news contains negative-sounding keywords,
        # label it as Negative.
        elif "regulatory pressure" in content or "lower-than-expected" in content:
            label = "Negative"
            reason = "This event may create uncertainty or suggest possible pressure on future performance."

        # Otherwise, label it as Neutral.
        else:
            label = "Neutral"
            reason = "The possible stock impact is unclear based on the available information."
            
        # Add the analyzed result to the results list
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
        
    # Return the full analysis result
    return {
        "ticker": ticker.upper(),
        "items": results,
        "disclaimer": "This tool is for educational and informational purposes only. It does not provide financial advice."
    }

"""
    Answer a user's follow-up question.

    In the future, this function will send the previous analysis
    and the user's question to a real foundation model.

    For now, it returns a simple mock answer.
"""
def answer_follow_up(question, previous_analysis):
    return {
        "answer": "Based on the previous analysis, the label is only a possible interpretation of the news impact. It should not be treated as direct buy or sell advice."
    }
