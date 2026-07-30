"""Run a small OpenAI-powered FinQA direct-answer evaluation.

This is intentionally a minimum viable evaluation:

1. Load a few local FinQA examples.
2. Send each example's oracle context, table, and question to OpenAI.
3. Compare the returned answer with FinQA's gold execution answer.
4. Print a small accuracy summary.

It is not the official FinQA benchmark because it does not evaluate document
retrieval or generation of FinQA reasoning programs.
"""

import argparse
import json
import math
from pathlib import Path

from services.model_service import answer_finqa_example


# Resolve the default file relative to this script, not the terminal's current
# directory. This lets the command work when launched from another directory.
PROJECT_DIRECTORY = Path(__file__).resolve().parent
DEFAULT_DATA_FILE = PROJECT_DIRECTORY / "data" / "finqa_sample.json"


def normalize_answer(value):
    """Convert common financial answer formats into comparable values.

    Examples:
    - "$1,234.50" becomes 1234.5
    - "93.5%" becomes 0.935
    - "($25)" becomes -25.0
    - "YES" becomes "yes"

    None is returned when the value cannot be interpreted safely.
    """

    if value is None:
        return None

    text = str(value).strip().lower()

    # Financial documents sometimes use the Unicode minus sign.
    text = text.replace("\u2212", "-")

    # FinQA contains a small number of yes/no comparisons.
    if text in ("yes", "yes."):
        return "yes"
    if text in ("no", "no."):
        return "no"

    # Parentheses are common accounting notation for negative values.
    is_negative = text.startswith("(") and text.endswith(")")
    if is_negative:
        text = text[1:-1].strip()

    # FinQA gold percentage answers are commonly stored as decimal ratios.
    # For example, the displayed answer "93.5%" is compared with 0.935.
    is_percent = text.endswith("%")
    if is_percent:
        text = text[:-1].strip()

    # Remove display characters that do not change the numerical value.
    text = text.replace(",", "")
    for currency_symbol in ("$", "\u20ac", "\u00a3"):
        text = text.replace(currency_symbol, "")

    try:
        number = float(text.strip())
    except (TypeError, ValueError):
        return None

    # NaN and infinity should never count as valid financial answers.
    if not math.isfinite(number):
        return None

    if is_negative:
        number = -abs(number)

    if is_percent:
        number = number / 100.0

    return number


def answers_match(predicted, expected):
    """Return True when two normalized direct answers are equivalent."""

    normalized_prediction = normalize_answer(predicted)
    normalized_expected = normalize_answer(expected)

    if normalized_prediction is None or normalized_expected is None:
        return False

    # Numerical answers may differ slightly because of rounding.
    if isinstance(normalized_prediction, float) and isinstance(
        normalized_expected,
        float,
    ):
        return math.isclose(
            normalized_prediction,
            normalized_expected,
            rel_tol=1e-4,
            abs_tol=1e-4,
        )

    return normalized_prediction == normalized_expected


def load_examples(data_file):
    """Load the adapted FinQA examples from a local JSON file."""

    with open(data_file, "r", encoding="utf-8") as file:
        payload = json.load(file)

    # The included sample uses a metadata object with an "examples" list.
    # A plain list is accepted too, which makes future expansion easy.
    if isinstance(payload, dict):
        examples = payload.get("examples")
    else:
        examples = payload

    if not isinstance(examples, list) or len(examples) == 0:
        raise ValueError("FinQA data file must contain a non-empty example list.")

    return examples


def run_evaluation(examples, limit, answer_function=answer_finqa_example):
    """Evaluate up to `limit` examples and print a readable report.

    `answer_function` is an argument so unit tests can provide a fake function
    and avoid spending API tokens.
    """

    selected_examples = examples[:limit]
    correct_count = 0
    error_count = 0

    print("FinQA oracle-context direct-answer MVP")
    print("=" * 40)

    for position, example in enumerate(selected_examples, start=1):
        example_id = example.get("id", "unknown")
        qa = example.get("qa")

        # Check that scoring data exists before making a paid API request.
        if not isinstance(qa, dict) or "exe_ans" not in qa:
            error_count += 1
            print(f"\n[{position}] ERROR - {example_id}")
            print("Missing qa.exe_ans; API call skipped.")
            continue

        question = qa.get("question", "Question unavailable")
        expected_answer = qa["exe_ans"]

        print(f"\n[{position}] {example_id}")
        print(f"Question: {question}")

        try:
            result = answer_function(example)
            predicted_answer = result.get("answer")
            calculation = result.get("calculation", "")
            is_correct = answers_match(predicted_answer, expected_answer)

            if is_correct:
                correct_count += 1
                status = "PASS"
            else:
                status = "FAIL"

            print(f"Status: {status}")
            print(f"Predicted: {predicted_answer}")
            print(f"Expected: {expected_answer}")
            print(f"Calculation: {calculation}")
        except Exception as error:
            # One API or parsing error should not stop the remaining examples.
            error_count += 1
            print("Status: ERROR")
            print(f"Reason: {type(error).__name__}: {error}")

    attempted_count = len(selected_examples)
    incorrect_count = attempted_count - correct_count - error_count
    accuracy = (
        correct_count / attempted_count * 100
        if attempted_count > 0
        else 0.0
    )

    summary = {
        "attempted": attempted_count,
        "correct": correct_count,
        "incorrect": incorrect_count,
        "errors": error_count,
        "accuracy": accuracy,
    }

    print("\nSummary")
    print("-" * 40)
    print(f"Attempted: {attempted_count}")
    print(f"Correct: {correct_count}")
    print(f"Incorrect: {incorrect_count}")
    print(f"Errors: {error_count}")
    print(f"Direct-answer accuracy: {accuracy:.1f}%")

    return summary


def main():
    """Read command-line options and run the small evaluation."""

    parser = argparse.ArgumentParser(
        description=(
            "Evaluate OpenAI on a small FinQA oracle-context sample. "
            "This command makes one API request per example."
        )
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=DEFAULT_DATA_FILE,
        help="Path to an adapted FinQA JSON file.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=1,
        help="Maximum number of examples to evaluate (default: 1).",
    )
    arguments = parser.parse_args()

    if arguments.limit < 1:
        parser.error("--limit must be at least 1.")

    examples = load_examples(arguments.data)
    run_evaluation(examples, arguments.limit)


if __name__ == "__main__":
    main()
