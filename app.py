from flask import Flask, render_template, request, jsonify
from services.news_service import get_mock_news
from services.model_service import analyze_news, answer_follow_up

app = Flask(__name__)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.get_json()
    ticker = data.get("ticker", "").strip()

    if ticker == "":
        return jsonify({"error": "Ticker is required."}), 400

    news_items = get_mock_news(ticker)

    if len(news_items) == 0:
        return jsonify({"error": "No mock news found for this ticker."}), 404

    analysis = analyze_news(ticker, news_items)
    return jsonify(analysis)


@app.route("/follow-up", methods=["POST"])
def follow_up():
    data = request.get_json()
    question = data.get("question", "").strip()
    previous_analysis = data.get("previous_analysis")

    if question == "":
        return jsonify({"error": "Question is required."}), 400

    if previous_analysis is None:
        return jsonify({"error": "Previous analysis is required."}), 400

    answer = answer_follow_up(question, previous_analysis)
    return jsonify(answer)


if __name__ == "__main__":
    app.run(debug=True)
