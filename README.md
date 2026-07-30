# Investment Information Filter Agent

## Project Overview

The **Investment Information Filter Agent** is an AI-powered tool designed to help novice investors quickly understand recent stock-related news and events.

When a user enters a stock name or ticker symbol, the agent retrieves recent important information, summarizes the news, and classifies the possible market impact as:

- Positive / long-oriented
- Neutral
- Negative / short-oriented

The agent also explains the reasoning behind each label and supports basic follow-up questions.

## Motivation

Beginner investors often face information overload when reading market news, company updates, analyst reports, and financial headlines. This project aims to help users filter important information, understand possible stock impact, and make more informed decisions without directly providing financial advice.

## MVP Scope

The first version of this project will focus on:

- Accepting a stock ticker or company name as input
- Retrieving recent stock-related news or events
- Summarizing each news item in beginner-friendly language
- Classifying each event as positive, neutral, or negative
- Explaining the reason behind the classification
- Answering simple follow-up questions based on the retrieved information

## Out of Scope

The MVP will not include:

- Direct buy/sell recommendations
- Automatic trading
- Full portfolio management
- Stock screening
- Real-time trading signals
- Personalized financial advice

## Proposed Tech Stack

- **Frontend:** HTML, CSS, JavaScript
- **Backend:** Python Flask
- **AI Model:** OpenAI API or Google Gemini API
- **Data Source:** Mock news data first, then financial/news APIs
- **Deployment:** GitHub Pages for documentation, possible backend deployment later

## FinQA Direct-Answer MVP

The project includes a small OpenAI-powered numerical reasoning evaluation
using three adapted examples from the
[FinQA dataset](https://github.com/czyssrs/FinQA).

This phase is deliberately small:

- It gives the model FinQA's gold supporting evidence and financial table.
- It asks the model for a final answer and a short calculation.
- It compares the prediction with `qa.exe_ans`.
- It prints direct-answer accuracy in the terminal.
- It defaults to one example so the first run uses only one API request.

Run one example:

```powershell
python -B finqa_mvp.py --limit 1
```

Run all three included examples:

```powershell
python -B finqa_mvp.py --limit 3
```

The evaluator uses the existing `OPENAI_API_KEY` and `OPENAI_MODEL` values from
`.env`. Gold answers and FinQA reasoning programs are never included in the
OpenAI prompt.

This is an **oracle-context direct-answer sanity check**, not an official FinQA
benchmark score. It does not evaluate retrieval or FinQA program generation,
and results from three selected examples are only exploratory. See
[`data/FINQA_NOTICE.md`](data/FINQA_NOTICE.md) for attribution and license
information.

## Basic System Architecture

```text
User Input
   ↓
Frontend
   ↓
Flask Backend
   ↓
News Retrieval Service
   ↓
Foundation Model
   ↓
Summary + Impact Label + Reasoning
   ↓
Frontend Result Display
