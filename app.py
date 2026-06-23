# Import Flask tools:
from flask import Flask, render_template, request, jsonify
from services.news_service import get_mock_news
from services.model_service import analyze_news, answer_follow_up

app = Flask(__name__)

# Home route
@app.route("/")
def home():
    return render_template("index.html")

# Analyze route
# This route receives a stock ticker from the frontend,
# gets related mock news, analyzes the news, and sends the result back as JSON.
@app.route("/analyze", methods=["POST"])
def analyze():
    # Get JSON data sent from frontend JavaScript
    data = request.get_json()
    # Read the ticker value from the JSON data
    # strip() removes extra spaces before or after the input
    ticker = data.get("ticker", "").strip()

    # If the user did not enter anything, return an error
    if ticker == "":
        return jsonify({"error": "Ticker is required."}), 400

    # Get mock news for this ticker from mock_news.json
    news_items = get_mock_news(ticker)

    # If there is no news for this ticker, return an error
    if len(news_items) == 0:
        return jsonify({"error": "No news found for this ticker."}), 404

    # Analyze the news items
    # at this stage, this uses simple mock logic(not real AI model)
    analysis = analyze_news(ticker, news_items)
    return jsonify(analysis)


# Follow-up route
# This route receives a follow-up question from the user
# and answers based on the previous analysis.
@app.route("/follow-up", methods=["POST"])
def follow_up():
    # Get JSON data from frontend
    data = request.get_json()

    # Read the user's follow-up question
    question = data.get("question", "").strip()

    # Read the previous analysis result
    # The frontend sends this back so the backend knows the context
    previous_analysis = data.get("previous_analysis")

    # If the question is empty, return an error
    if question == "":
        return jsonify({"error": "Question is required."}), 400

    # If there is no previous analysis, return an error
    if previous_analysis is None:
        return jsonify({"error": "Previous analysis is required."}), 400

    # Generate a follow-up answer
    # For now, this is a mock answer
    answer = answer_follow_up(question, previous_analysis)
    return jsonify(answer)


if __name__ == "__main__":
    # Reload the app when code changes and show error messages.
    app.run(debug=True)
