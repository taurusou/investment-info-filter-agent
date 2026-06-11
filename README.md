# investment-info-filter-agent

Project Overview

The Investment Information Filter Agent is an AI-powered tool designed to help novice investors quickly understand recent stock-related news and events.

When a user enters a stock name or ticker symbol, the agent retrieves recent important information, summarizes the news, and classifies the possible market impact as:

Positive / long-oriented
Neutral
Negative / short-oriented

The agent also explains the reasoning behind each label and supports basic follow-up questions.

Motivation

Beginner investors often face information overload when reading market news, company updates, analyst reports, and financial headlines. This project aims to help users filter important information, understand possible stock impact, and make more informed decisions without directly providing financial advice.

MVP Scope

The first version of this project will focus on:

Accepting a stock ticker or company name as input
Retrieving recent stock-related news or events
Summarizing each news item in beginner-friendly language
Classifying each event as positive, neutral, or negative
Explaining the reason behind the classification
Answering simple follow-up questions based on the retrieved information
Out of Scope

The MVP will not include:

Direct buy/sell recommendations
Automatic trading
Full portfolio management
Stock screening
Real-time trading signals
Personalized financial advice
Proposed Tech Stack
Frontend: HTML, CSS, JavaScript
Backend: Python Flask
AI Model: OpenAI API or Google Gemini API
Data Source: Mock news data first, then financial/news APIs
Deployment: GitHub Pages for documentation, possible backend deployment later
Basic System Architecture
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
Development Plan
Create the GitHub repository
Build a basic frontend layout
Create the Flask backend
Add mock stock news data
Build the /analyze API route
Connect a foundation model for summarization and classification
Add follow-up question support
Connect a real financial/news API
Improve UI and documentation
Deploy the project demo
Evaluation Criteria

The project will be evaluated based on:

Whether the agent can accept a stock ticker input
Whether the retrieved news is relevant
Whether the summaries are clear and beginner-friendly
Whether the impact labels are reasonable
Whether the reasoning is understandable
Whether follow-up questions work properly
Whether the tool avoids direct financial advice
Disclaimer

This project is for educational and informational purposes only. It does not provide financial advice, investment recommendations, or trading instructions.

Project Status

Current stage: initial MVP planning and repository setup.
