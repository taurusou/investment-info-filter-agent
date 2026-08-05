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

This phase is deliberately small and follows four steps:

1. Give the model the report context, table, and question.
2. Request a final answer, a short calculation, and the source values used.
3. Save the response locally so later scoring runs do not need another API call.
4. Assign a quality category and print a summary.

This MVP evaluates numerical answers only. FinQA yes/no answers and official
reasoning-program execution are outside this phase's scoring scope.

The FinQA gold answer is used only after the model responds. FinQA reasoning
programs are neither sent to the model nor evaluated by this MVP.

### Run the evaluator

The default command evaluates one example. On the first run, an uncached
example makes one API request:

```powershell
python -B finqa_mvp.py --limit 1
```

Evaluate all three included examples:

```powershell
python -B finqa_mvp.py --limit 3
```

Run again without making any API requests:

```powershell
python -B finqa_mvp.py --limit 3 --offline
```

Force fresh responses even when the current cache still matches:

```powershell
python -B finqa_mvp.py --limit 3 --refresh
```

The default cache is `data/finqa_responses.json`. The file stores the example
ID, question, input signature, model name, prompt version, answer, calculation,
and evidence. It does **not** store `OPENAI_API_KEY` or any other value from
`.env`. The cache is listed in `.gitignore`, so it stays local unless it is
deliberately renamed or copied as an evaluation artifact.

Cache behavior:

- Cache hit: reuse the saved response and score it again.
- Cache miss: make one OpenAI request and save the successful response.
- Changed report context, question, model, or prompt: treat the old response as
  stale and make a new request. Scoring-only changes still reuse the response.
- `--offline`: never call OpenAI; a missing cache entry becomes an error.
- `--refresh`: ignore old entries and request new responses.

### Scoring categories

| Category | Meaning |
| --- | --- |
| `correct` | The answer passes the numerical-evidence and arithmetic checks, then matches within strict floating-point tolerance. |
| `numerically_close` | The answer passes those checks and is outside strict tolerance, but within the 0.5% rounding tolerance. |
| `unsupported` | The final answer is correct or close, but its evidence is missing/invented/unused, an operand is uncited, or its basic arithmetic does not produce the displayed answer. |
| `incorrect` | The final answer is unparseable or outside the wider rounding tolerance. |

API failures, invalid per-example inputs, malformed model responses, and
offline cache misses are reported separately as `error`; they do not silently
become financial-answer failures. A cache-write failure is printed as a warning
while preserving the received answer's quality result. An invalid cache file is
a command-line error and can be deliberately replaced with `--refresh`.
Because a wrong answer can also use invented evidence, the summary separately
counts every output that fails the automated support check, including outputs
whose primary category is `incorrect`.

The strict comparison uses relative and absolute tolerances of `0.000001`.
The close comparison uses a `0.5%` relative tolerance and `0.0001` absolute
tolerance. The scorer also handles commas, currency symbols, accounting
parentheses, and both percentage formats found in FinQA. Each
adapted example contains `exe_ans_scale` metadata so `93.5%` can be compared
with ratio gold `0.935`, while `24.69%` can be compared with percentage-point
gold `24.69136`, without accepting an explicit percent-unit mistake.
Missing or invalid scale metadata is rejected before an API call is made.

### Example failures and lessons learned

1. **Observed rounding difference from the August 4, 2026 API run.** For the
   Canada MMBOE example, the model returned `24.69%`; the gold answer is
   `24.69136`. Its calculation `(60 / 243) * 100` and evidence values `60` and
   `243` passed the automated checks, so the evaluator labeled it
   `numerically_close` instead of treating a two-decimal answer as fully
   incorrect. The lesson is that exact string matching is too brittle for
   financial calculations.

2. **Constructed unsupported-output unit test.** A response can display the
   correct `25%` answer while claiming it used `999 / 3996`, even though those
   values are absent from the supplied report. The evaluator labels this
   `unsupported`. The lesson is that matching the gold answer alone does not
   prove that the financial claim is supported. This second example is a test
   fixture, not an observed OpenAI benchmark result.

The verified `gpt-4o-mini` / `finqa-evidence-v2` three-example run produced two
`correct` answers, one `numerically_close` answer, and no unsupported,
incorrect, or operational-error results. That is `66.7%` strict accuracy and a
`100.0%` correct-or-close rate. This tiny result is exploratory and should not
be generalized.

### Run the tests

The unit tests use fake model functions, so they do not spend API credits:

```powershell
python -B -m unittest discover -s tests -v
```

This is an **oracle-context direct-answer sanity check**, not an official FinQA
benchmark score. It does not evaluate retrieval or FinQA program generation,
and results from three selected examples are only exploratory. The automated
support check verifies numerical source values and safely recomputes basic
`+`, `-`, `*`, and `/` expressions. It does not yet prove that the model chose
the correct financial metric or respected every unit. See
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
