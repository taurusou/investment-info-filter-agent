"""Run a small OpenAI-powered FinQA direct-answer evaluation.

This beginner-friendly evaluator does four jobs:

1. Load a few local FinQA examples.
2. Reuse a saved model response, or call OpenAI when no response is saved.
3. Score the answer as correct, numerically close, unsupported, or incorrect.
4. Print a small report that explains every decision.

It is not the official FinQA benchmark because it does not evaluate document
retrieval or generation of FinQA reasoning programs.
"""

import argparse
import ast
import hashlib
import json
import math
import os
import re
from pathlib import Path

from services.model_service import (
    FINQA_PROMPT_VERSION,
    answer_finqa_example,
)


# Resolve default files relative to this script, not the terminal's current
# directory. This lets the command work when launched from another directory.
PROJECT_DIRECTORY = Path(__file__).resolve().parent
DEFAULT_DATA_FILE = PROJECT_DIRECTORY / "data" / "finqa_sample.json"
DEFAULT_CACHE_FILE = PROJECT_DIRECTORY / "data" / "finqa_responses.json"

# This version describes the JSON file structure used by the local cache.
CACHE_FORMAT_VERSION = 2

# "Correct" uses a very small tolerance for floating-point noise only.
CORRECT_RELATIVE_TOLERANCE = 1e-6
CORRECT_ABSOLUTE_TOLERANCE = 1e-6

# "Numerically close" allows about 0.5% relative rounding difference.
# The small absolute tolerance helps when the expected answer is near zero.
CLOSE_RELATIVE_TOLERANCE = 5e-3
CLOSE_ABSOLUTE_TOLERANCE = 1e-4

CATEGORY_NAMES = (
    "correct",
    "numerically_close",
    "unsupported",
    "incorrect",
)

VALID_ANSWER_SCALES = (
    "number",
    "ratio",
    "percentage_points",
)

# This pattern finds ordinary numbers, comma-separated numbers, decimals, and
# percentages inside a calculation or a financial-report passage.
NUMBER_PATTERN = re.compile(
    r"[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?%?"
)

def normalize_answer(value):
    """Convert a common financial answer format into one simple value.

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

    # A displayed percentage is normally converted to its decimal ratio.
    # A later helper also tries percentage points because FinQA gold answers
    # use both conventions in different examples.
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


def answer_candidates(value, expected_scale=None):
    """Return the reasonable numeric interpretations of one answer.

    FinQA gold percentage answers are not stored on one consistent scale.
    For example, one included gold answer is 0.935 for 93.5%, while another
    is 24.69136 for 24.69136%. A displayed percentage therefore has two
    possible interpretations. The included sample's scale metadata selects
    the correct one rather than accepting both blindly.

    This percentage flexibility is used only by the scorer. The correct answer
    is never sent to the model.
    """

    normalized_value = normalize_answer(value)
    if normalized_value is None:
        return []

    candidates = [normalized_value]
    text = str(value).strip()

    if text.endswith("%") and isinstance(normalized_value, float):
        percentage_points = normalized_value * 100.0

        # The adapted examples can state which FinQA convention applies.
        # This prevents a real unit error such as 0.935% from being accepted
        # as the decimal ratio 0.935.
        if expected_scale == "percentage_points":
            candidates = [percentage_points]
        elif expected_scale == "ratio":
            candidates = [normalized_value]
        elif expected_scale == "number":
            # A percent sign is a unit error for a non-percentage gold answer.
            candidates = []
        else:
            # Keeping both interpretations is a backward-compatible fallback
            # for custom data files that do not yet contain scale metadata.
            candidates.append(percentage_points)

    return candidates


def compare_answers(predicted, expected, expected_scale=None):
    """Return correct, numerically_close, or incorrect for two answers."""

    predicted_candidates = answer_candidates(predicted, expected_scale)
    expected_candidates = answer_candidates(expected)

    if not predicted_candidates or not expected_candidates:
        return "incorrect"

    # Yes/no answers must match exactly and never use numeric tolerances.
    if isinstance(predicted_candidates[0], str) or isinstance(
        expected_candidates[0], str
    ):
        if predicted_candidates[0] == expected_candidates[0]:
            return "correct"
        return "incorrect"

    # First try the strict tolerance. This catches only tiny representation
    # differences, such as 127.4 versus 127.40000001.
    for predicted_number in predicted_candidates:
        for expected_number in expected_candidates:
            if math.isclose(
                predicted_number,
                expected_number,
                rel_tol=CORRECT_RELATIVE_TOLERANCE,
                abs_tol=CORRECT_ABSOLUTE_TOLERANCE,
            ):
                return "correct"

    # Next try the wider tolerance for ordinary rounding differences.
    for predicted_number in predicted_candidates:
        for expected_number in expected_candidates:
            if math.isclose(
                predicted_number,
                expected_number,
                rel_tol=CLOSE_RELATIVE_TOLERANCE,
                abs_tol=CLOSE_ABSOLUTE_TOLERANCE,
            ):
                return "numerically_close"

    return "incorrect"


def answers_match(predicted, expected, expected_scale=None):
    """Return True when answers are correct or acceptably close.

    This small wrapper keeps compatibility with the first version of the MVP.
    New code should use compare_answers() when it needs the detailed category.
    """

    relationship = compare_answers(predicted, expected, expected_scale)
    return relationship in ("correct", "numerically_close")


def numeric_value_and_unit(value):
    """Return one displayed number plus whether it had a percent sign."""

    normalized_value = normalize_answer(value)
    if not isinstance(normalized_value, float):
        return None

    text = str(value).strip()
    if text.endswith("%"):
        # Store percentages as the number printed before the sign. Keeping the
        # unit beside it prevents report text "0.25%" from supporting invented
        # evidence "0.25", which is 100 times larger as a ratio.
        return normalized_value * 100.0, "percent"

    return normalized_value, "number"


def extract_numeric_values(value):
    """Find displayed numbers and their percent units inside text."""

    values = []
    text = str(value)

    for token in NUMBER_PATTERN.findall(text):
        parsed_value = numeric_value_and_unit(token)
        if parsed_value is not None:
            values.append(parsed_value)

    return values


def numbers_are_equal(first_number, second_number):
    """Compare two source values without allowing ordinary rounding."""

    return math.isclose(
        first_number,
        second_number,
        rel_tol=1e-9,
        abs_tol=1e-9,
    )


def collect_source_numbers(example):
    """Collect every numerical value in the supplied report context."""

    source_numbers = []

    for passage_name in ("pre_text", "post_text"):
        passages = example.get(passage_name, [])
        if isinstance(passages, list):
            for passage in passages:
                source_numbers.extend(extract_numeric_values(passage))

    table = example.get("table", [])
    if isinstance(table, list):
        for row in table:
            if isinstance(row, list):
                for cell in row:
                    # Parsing the whole cell preserves accounting negatives
                    # such as "($25)" when a cell contains only one value.
                    whole_cell_value = numeric_value_and_unit(cell)
                    if whole_cell_value is not None:
                        source_numbers.append(whole_cell_value)
                    else:
                        # Headers and cells containing several values cannot be
                        # normalized as one number, so scan those as text.
                        source_numbers.extend(extract_numeric_values(cell))

    return source_numbers


def number_appears_in_list(number, number_list):
    """Return True when one number has a strict match in a list."""

    for listed_number in number_list:
        if numbers_are_equal(number, listed_number):
            return True
    return False


def source_value_appears_in_list(value_and_unit, source_values):
    """Match both a number and its percent/non-percent unit."""

    evidence_number, evidence_unit = value_and_unit

    for source_number, source_unit in source_values:
        same_number = numbers_are_equal(evidence_number, source_number)
        if same_number and evidence_unit == source_unit:
            return True

    return False


def displayed_numeric_value(value):
    """Read the number exactly as displayed, without changing percent scale."""

    text = str(value).strip()

    if text.endswith("%"):
        candidates = answer_candidates(text, expected_scale="percentage_points")
    else:
        candidates = answer_candidates(text)

    for candidate in candidates:
        if isinstance(candidate, float):
            return candidate

    return None


def evaluate_arithmetic_node(node):
    """Safely evaluate one small arithmetic-syntax-tree node.

    The return value contains:

    - the calculated value;
    - every literal operand used by the expression;
    - the number of binary operations.

    Only basic arithmetic nodes are accepted. Names, function calls, powers,
    attributes, and every other Python feature are rejected.
    """

    if isinstance(node, ast.Constant):
        value = node.value
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("Calculation constants must be ordinary numbers.")

        number = float(value)
        if not math.isfinite(number):
            raise ValueError("Calculation contains a non-finite number.")

        return number, [number], 0

    if isinstance(node, ast.UnaryOp):
        value, operands, operation_count = evaluate_arithmetic_node(
            node.operand
        )

        if isinstance(node.op, ast.USub):
            result = -value
            # Preserve a directly written negative source operand such as -25.
            if isinstance(node.operand, ast.Constant):
                operands = [-operands[0]]
        elif isinstance(node.op, ast.UAdd):
            result = value
        else:
            raise ValueError("Calculation uses an unsupported unary operator.")

        return result, operands, operation_count

    if isinstance(node, ast.BinOp):
        left_value, left_operands, left_count = evaluate_arithmetic_node(
            node.left
        )
        right_value, right_operands, right_count = evaluate_arithmetic_node(
            node.right
        )

        if isinstance(node.op, ast.Add):
            result = left_value + right_value
        elif isinstance(node.op, ast.Sub):
            result = left_value - right_value
        elif isinstance(node.op, ast.Mult):
            result = left_value * right_value
        elif isinstance(node.op, ast.Div):
            if right_value == 0:
                raise ValueError("Calculation divides by zero.")
            result = left_value / right_value
        else:
            raise ValueError(
                "Calculation may use only +, -, *, and / operators."
            )

        if not math.isfinite(result):
            raise ValueError("Calculation produced a non-finite number.")

        operands = left_operands + right_operands
        operation_count = left_count + right_count + 1
        return result, operands, operation_count

    raise ValueError("Calculation contains unsupported text or syntax.")


def evaluate_calculation(calculation):
    """Safely calculate a model expression without using Python eval()."""

    # The v2 prompt requires only an expression. Rejecting '=' avoids ignoring
    # a contradictory right-hand result such as "125 - 100 = 999".
    if "=" in calculation:
        raise ValueError("Calculation must not contain an equals sign.")

    expression = calculation.strip()
    if expression == "":
        raise ValueError("Calculation expression is empty.")

    try:
        syntax_tree = ast.parse(expression, mode="eval")
    except SyntaxError as error:
        raise ValueError(
            "Calculation is not a valid basic arithmetic expression."
        ) from error

    result, operands, operation_count = evaluate_arithmetic_node(
        syntax_tree.body
    )

    if operation_count == 0:
        raise ValueError("Calculation must contain an arithmetic operation.")

    return result, operands


def check_response_support(example, response):
    """Check whether a response's numerical evidence comes from the report.

    This is intentionally a small grounding check, not a full proof checker.
    It verifies that:

    1. A calculation and at least one evidence value were supplied.
    2. Every evidence value appears in the provided report context or table.
    3. Calculation operands are cited as evidence, except simple conversion
       constants such as 100 for percentage calculations.
    4. Every cited evidence value is actually used by the calculation.
    5. A safe arithmetic parser confirms that the expression leads to the
       displayed answer within the documented rounding tolerance.

    The function returns both a Boolean result and a readable explanation.
    """

    if not isinstance(response, dict):
        return False, "The model response was not a JSON object."

    calculation = response.get("calculation", "")
    if not isinstance(calculation, str) or calculation.strip() == "":
        return False, "No calculation was provided."

    evidence = response.get("evidence", [])
    if not isinstance(evidence, list) or len(evidence) == 0:
        return False, "No evidence values were provided."

    try:
        calculated_value, calculation_numbers = evaluate_calculation(
            calculation
        )
    except ValueError as error:
        return False, str(error)

    source_numbers = collect_source_numbers(example)
    cited_numbers = []
    cited_evidence = []
    has_percent_evidence = False

    for evidence_item in evidence:
        # Each evidence entry should be one source number, not an explanation.
        if isinstance(evidence_item, bool) or not isinstance(
            evidence_item,
            (str, int, float),
        ):
            return False, "Evidence entries must be simple numbers."

        parsed_evidence = numeric_value_and_unit(evidence_item)

        if parsed_evidence is None:
            return False, f"Evidence value {evidence_item!r} is not numeric."

        if not source_value_appears_in_list(
            parsed_evidence,
            source_numbers,
        ):
            return (
                False,
                f"Evidence value {evidence_item!r} was not found in the report.",
            )

        cited_number, evidence_unit = parsed_evidence
        if evidence_unit == "percent":
            has_percent_evidence = True

        cited_numbers.append(cited_number)
        cited_evidence.append((evidence_item, cited_number))

    question = example.get("qa", {}).get("question", "")
    is_percentage_calculation = (
        "percent" in str(question).lower()
        or str(response.get("answer", "")).strip().endswith("%")
        or has_percent_evidence
    )

    allowed_constants = [1.0]
    if is_percentage_calculation:
        allowed_constants.append(100.0)

    for calculation_number in calculation_numbers:
        is_cited = number_appears_in_list(
            calculation_number,
            cited_numbers,
        )
        is_constant = number_appears_in_list(
            calculation_number,
            allowed_constants,
        )

        if not is_cited and not is_constant:
            return (
                False,
                "Calculation operand "
                f"{calculation_number:g} was not listed in evidence.",
            )

    # Listing irrelevant source numbers should not make a constant-only or
    # unrelated calculation look supported. Every cited item must actually be
    # used, and this also guarantees at least one report value was used.
    for evidence_item, cited_number in cited_evidence:
        if not number_appears_in_list(cited_number, calculation_numbers):
            return (
                False,
                f"Evidence value {evidence_item!r} was not used in the calculation.",
            )

    displayed_answer = displayed_numeric_value(response.get("answer"))
    if displayed_answer is None:
        return False, "The displayed answer is not numeric."

    calculation_matches_answer = math.isclose(
        calculated_value,
        displayed_answer,
        rel_tol=CLOSE_RELATIVE_TOLERANCE,
        abs_tol=CLOSE_ABSOLUTE_TOLERANCE,
    )
    if not calculation_matches_answer:
        return (
            False,
            "The written calculation does not produce the displayed answer.",
        )

    return (
        True,
        "The source-number occurrence and arithmetic checks passed.",
    )


def validate_scoring_metadata(example):
    """Validate gold-answer fields before an API request can be made."""

    qa = example.get("qa")
    if not isinstance(qa, dict) or "exe_ans" not in qa:
        raise ValueError("FinQA example must include qa.exe_ans.")

    normalized_expected = normalize_answer(qa.get("exe_ans"))
    if normalized_expected is None:
        raise ValueError("qa.exe_ans must contain a scorable answer.")

    if not isinstance(normalized_expected, float):
        raise ValueError("This FinQA MVP supports numerical gold answers only.")

    expected_scale = qa.get("exe_ans_scale")
    if expected_scale not in VALID_ANSWER_SCALES:
        allowed_scales = ", ".join(VALID_ANSWER_SCALES)
        raise ValueError(
            "Numeric FinQA examples require qa.exe_ans_scale set to one "
            f"of: {allowed_scales}."
        )

    return expected_scale


def score_model_response(example, response):
    """Assign one of the four instructor-requested quality categories."""

    expected_scale = validate_scoring_metadata(example)
    qa = example["qa"]
    expected_answer = qa.get("exe_ans")

    if isinstance(response, dict):
        predicted_answer = response.get("answer")
    else:
        predicted_answer = None

    answer_category = compare_answers(
        predicted_answer,
        expected_answer,
        expected_scale,
    )
    is_supported, support_reason = check_response_support(example, response)

    # An answer outside the broad tolerance is incorrect even when its source
    # values are also unsupported. The support result remains in diagnostics.
    if answer_category == "incorrect":
        category = "incorrect"
        reason = "The final answer is outside the allowed numerical tolerance."
    elif not is_supported:
        # A correct-looking number is not trusted when its calculation cannot
        # be connected to values in the supplied report.
        category = "unsupported"
        reason = support_reason
    elif answer_category == "correct":
        category = "correct"
        reason = (
            "The answer passed the automated support check and matches within "
            "the strict tolerance."
        )
    else:
        category = "numerically_close"
        reason = (
            "The answer passed the automated support check, is outside the "
            "strict tolerance, and is within the 0.5% rounding tolerance."
        )

    return {
        "category": category,
        "reason": reason,
        "supported": is_supported,
        "support_reason": support_reason,
    }


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


def make_input_signature(example):
    """Create a short fingerprint from only the data sent to the model.

    The gold answer is deliberately excluded. Correcting a gold label or
    changing scoring code should still reuse the already-paid model response.
    A report, table, or question change produces a different fingerprint.
    """

    qa = example.get("qa", {})
    question = qa.get("question") if isinstance(qa, dict) else None
    model_input = {
        "pre_text": example.get("pre_text"),
        "table": example.get("table"),
        "post_text": example.get("post_text"),
        "question": question,
    }

    serialized_input = json.dumps(
        model_input,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized_input.encode("utf-8")).hexdigest()


def make_empty_cache():
    """Return the starting structure for a new response cache."""

    return {
        "format_version": CACHE_FORMAT_VERSION,
        "responses": {},
    }


def load_response_cache(cache_file):
    """Load a response cache, or create an empty one for the first run."""

    cache_path = Path(cache_file)
    if not cache_path.exists():
        return make_empty_cache()

    try:
        with open(cache_path, "r", encoding="utf-8") as file:
            cache = json.load(file)
    except json.JSONDecodeError as error:
        raise ValueError(
            f"Response cache is not valid JSON: {cache_path}"
        ) from error

    if not isinstance(cache, dict):
        raise ValueError("Response cache must contain a JSON object.")

    if cache.get("format_version") != CACHE_FORMAT_VERSION:
        raise ValueError(
            "Response cache has an unsupported format_version."
        )

    if not isinstance(cache.get("responses"), dict):
        raise ValueError("Response cache must contain a 'responses' object.")

    return cache


def find_cached_response(cache, example, model_name=None):
    """Return a saved response only when its model inputs still match."""

    example_id = example.get("id")
    qa = example.get("qa", {})
    question = qa.get("question") if isinstance(qa, dict) else None

    record = cache.get("responses", {}).get(example_id)
    if not isinstance(record, dict):
        return None

    # If an example ID is accidentally reused for a different question, do
    # not silently score the old response against the new question.
    if record.get("question") != question:
        return None

    if record.get("input_signature") != make_input_signature(example):
        return None

    if record.get("prompt_version") != FINQA_PROMPT_VERSION:
        return None

    if model_name is not None and record.get("model") != model_name:
        return None

    response = record.get("response")
    if not isinstance(response, dict):
        return None

    answer = response.get("answer")
    if answer is None or str(answer).strip() == "":
        return None

    if not isinstance(response.get("calculation"), str):
        return None

    if not isinstance(response.get("evidence"), list):
        return None

    return response


def store_cached_response(cache, example, response, model_name):
    """Place one successful model response into the in-memory cache."""

    if not isinstance(response, dict):
        raise ValueError("Model response must be a dictionary before caching.")

    answer = response.get("answer")
    if answer is None or str(answer).strip() == "":
        raise ValueError("A response without an answer cannot be cached.")

    calculation = response.get("calculation", "")
    if not isinstance(calculation, str):
        calculation = ""

    evidence = response.get("evidence", [])
    if not isinstance(evidence, list):
        evidence = []

    example_id = example.get("id")
    if not isinstance(example_id, str) or example_id.strip() == "":
        raise ValueError("FinQA example must have a non-empty text ID.")

    qa = example.get("qa", {})
    question = qa.get("question") if isinstance(qa, dict) else None

    cache["responses"][example_id] = {
        "question": question,
        "input_signature": make_input_signature(example),
        "model": model_name,
        "prompt_version": FINQA_PROMPT_VERSION,
        "response": {
            "answer": str(answer).strip(),
            "calculation": calculation.strip(),
            "evidence": evidence,
        },
    }


def save_response_cache(cache_file, cache):
    """Save the cache through a temporary file to avoid partial JSON."""

    cache_path = Path(cache_file)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = cache_path.with_name(cache_path.name + ".tmp")

    # The temporary file is completely closed before it replaces the real
    # cache. This is safer if the program is interrupted during a write.
    with open(temporary_path, "w", encoding="utf-8") as file:
        json.dump(cache, file, indent=2, ensure_ascii=False)
        file.write("\n")

    temporary_path.replace(cache_path)


def current_model_name():
    """Return the configured model name without exposing the API key."""

    model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
    return model_name or "gpt-4o-mini"


def run_evaluation(
    examples,
    limit,
    answer_function=answer_finqa_example,
    cache_file=None,
    offline=False,
    refresh=False,
    model_name=None,
):
    """Evaluate examples and print a readable category report.

    `answer_function` is an argument so tests can provide a fake function and
    avoid spending API tokens. `cache_file` defaults to None for the same
    reason; the command-line program passes the real default path explicitly.
    """

    if offline and refresh:
        raise ValueError("offline and refresh modes cannot be used together.")

    selected_examples = examples[:limit]
    category_counts = {category: 0 for category in CATEGORY_NAMES}
    error_count = 0
    unsupported_claim_count = 0
    chosen_model = model_name or current_model_name()

    if cache_file is None:
        cache = make_empty_cache()
    else:
        try:
            cache = load_response_cache(cache_file)
        except ValueError:
            if not refresh:
                raise

            # --refresh is also the explicit recovery path for an obsolete or
            # malformed cache. A normal run never overwrites it silently.
            cache = make_empty_cache()

    print("FinQA oracle-context direct-answer evaluation")
    print("=" * 48)

    for position, example in enumerate(selected_examples, start=1):
        example_id = example.get("id", "unknown")
        qa = example.get("qa")

        # Check scoring data before making a paid API request.
        if not isinstance(example_id, str) or example_id.strip() == "":
            error_count += 1
            print(f"\n[{position}] ERROR - invalid example ID")
            print("Missing or invalid example ID; API call skipped.")
            continue

        if not isinstance(qa, dict) or "exe_ans" not in qa:
            error_count += 1
            print(f"\n[{position}] ERROR - {example_id}")
            print("Missing qa.exe_ans; API call skipped.")
            continue

        try:
            validate_scoring_metadata(example)
        except ValueError as error:
            error_count += 1
            print(f"\n[{position}] ERROR - {example_id}")
            print(f"{error} API call skipped.")
            continue

        question = qa.get("question", "Question unavailable")
        expected_answer = qa["exe_ans"]

        print(f"\n[{position}] {example_id}")
        print(f"Question: {question}")

        try:
            response = None
            response_source = "OpenAI API"
            cache_warning = None

            # Default behavior reuses saved responses. --refresh skips this
            # lookup, while --offline never proceeds to an API call.
            if not refresh:
                response = find_cached_response(
                    cache,
                    example,
                    model_name=chosen_model,
                )

            if response is not None:
                response_source = "local cache"
            elif offline:
                raise RuntimeError(
                    "No cached response is available in offline mode."
                )
            else:
                response = answer_function(example)

                if cache_file is not None:
                    try:
                        store_cached_response(
                            cache,
                            example,
                            response,
                            chosen_model,
                        )

                        # Save immediately so this paid response survives if a
                        # later example fails or the program is interrupted.
                        save_response_cache(cache_file, cache)
                    except (OSError, TypeError, ValueError) as cache_error:
                        # A disk problem should not erase the quality result of
                        # an API answer that was already received and paid for.
                        cache_warning = (
                            f"{type(cache_error).__name__}: {cache_error}"
                        )

            score = score_model_response(example, response)
            category = score["category"]
            category_counts[category] += 1
            if not score["supported"]:
                unsupported_claim_count += 1

            print(f"Category: {category.upper()}")
            print(f"Response source: {response_source}")
            print(f"Predicted: {response.get('answer')}")
            print(f"Expected: {expected_answer}")
            print(f"Calculation: {response.get('calculation', '')}")

            evidence = response.get("evidence", [])
            if isinstance(evidence, list) and evidence:
                print(f"Evidence: {', '.join(str(item) for item in evidence)}")
            else:
                print("Evidence: (none)")

            print(f"Reason: {score['reason']}")

            if cache_warning is not None:
                print(f"Cache warning: {cache_warning}")

            # An incorrect response can also have unsupported evidence. Show
            # that diagnostic without changing its primary category.
            if category == "incorrect" and not score["supported"]:
                print(f"Support note: {score['support_reason']}")
        except Exception as error:
            # One API, cache, or parsing error should not stop later examples.
            error_count += 1
            print("Category: ERROR")
            print(f"Reason: {type(error).__name__}: {error}")

    attempted_count = len(selected_examples)
    correct_count = category_counts["correct"]
    close_count = category_counts["numerically_close"]

    strict_accuracy = (
        correct_count / attempted_count * 100
        if attempted_count > 0
        else 0.0
    )
    correct_or_close_rate = (
        (correct_count + close_count) / attempted_count * 100
        if attempted_count > 0
        else 0.0
    )

    summary = {
        "attempted": attempted_count,
        "correct": correct_count,
        "numerically_close": close_count,
        "unsupported": category_counts["unsupported"],
        "incorrect": category_counts["incorrect"],
        "unsupported_claims": unsupported_claim_count,
        "errors": error_count,
        # Keep the old key name for callers of the first MVP version.
        "accuracy": strict_accuracy,
        "strict_accuracy": strict_accuracy,
        "acceptable_rate": correct_or_close_rate,
        "correct_or_close_rate": correct_or_close_rate,
    }

    print("\nSummary")
    print("-" * 48)
    print(f"Attempted: {attempted_count}")
    print(f"Correct: {summary['correct']}")
    print(f"Numerically close: {summary['numerically_close']}")
    print(f"Unsupported: {summary['unsupported']}")
    print(f"Incorrect: {summary['incorrect']}")
    print(f"Outputs failing support check: {summary['unsupported_claims']}")
    print(f"Errors: {summary['errors']}")
    print(f"Strict accuracy: {strict_accuracy:.1f}%")
    print(f"Correct-or-close rate: {correct_or_close_rate:.1f}%")

    return summary


def main():
    """Read command-line options and run the small evaluation."""

    parser = argparse.ArgumentParser(
        description=(
            "Evaluate OpenAI on a small FinQA oracle-context sample. "
            "Only examples missing from the local cache make API requests."
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
    parser.add_argument(
        "--cache",
        type=Path,
        default=DEFAULT_CACHE_FILE,
        help="Local JSON file used to save and reuse model responses.",
    )

    request_mode = parser.add_mutually_exclusive_group()
    request_mode.add_argument(
        "--offline",
        action="store_true",
        help="Use saved responses only and never call the OpenAI API.",
    )
    request_mode.add_argument(
        "--refresh",
        action="store_true",
        help="Ignore saved responses and request fresh OpenAI answers.",
    )

    arguments = parser.parse_args()

    if arguments.limit < 1:
        parser.error("--limit must be at least 1.")

    try:
        examples = load_examples(arguments.data)
        run_evaluation(
            examples,
            arguments.limit,
            cache_file=arguments.cache,
            offline=arguments.offline,
            refresh=arguments.refresh,
        )
    except (OSError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
