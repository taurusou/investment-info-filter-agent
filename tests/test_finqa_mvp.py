import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from finqa_mvp import (
    DEFAULT_DATA_FILE,
    answers_match,
    load_examples,
    normalize_answer,
    run_evaluation,
)
from services.model_service import answer_finqa_example


def make_example(example_id="example-1", expected_answer=0.25):
    """Create one small FinQA-shaped record for unit tests."""

    return {
        "id": example_id,
        "pre_text": ["The report states that revenue increased."],
        "post_text": [],
        "table": [
            ["year", "revenue"],
            ["2025", "100"],
            ["2026", "125"],
        ],
        "qa": {
            "question": "What was the percentage increase in revenue?",
            "exe_ans": expected_answer,
            # These fields must never be copied into the API prompt.
            "program": "SECRET_PROGRAM_SHOULD_NOT_APPEAR",
        },
    }


class FinQAServiceTests(unittest.TestCase):
    @patch("services.model_service._call_openai")
    def test_answers_example_without_leaking_gold_data(self, mock_call):
        example = make_example(expected_answer=987654.321)
        mock_call.return_value = """
        {
          "answer": "25%",
          "calculation": "(125 - 100) / 100 * 100 = 25%"
        }
        """

        result = answer_finqa_example(example)

        self.assertEqual(result["answer"], "25%")
        self.assertIn("(125 - 100)", result["calculation"])

        # The first API argument is the user prompt.
        prompt = mock_call.call_args.args[0]
        self.assertIn("The report states", prompt)
        self.assertIn("2025 | 100", prompt)
        self.assertIn("percentage increase", prompt)
        self.assertNotIn("987654.321", prompt)
        self.assertNotIn("SECRET_PROGRAM_SHOULD_NOT_APPEAR", prompt)

    @patch("services.model_service._call_openai")
    def test_rejects_invalid_example_before_api_call(self, mock_call):
        invalid_example = make_example()
        del invalid_example["table"]

        with self.assertRaises(ValueError):
            answer_finqa_example(invalid_example)

        mock_call.assert_not_called()

    @patch("services.model_service._call_openai")
    def test_requires_calculation_in_model_response(self, mock_call):
        mock_call.return_value = '{"answer": "25%"}'

        with self.assertRaisesRegex(ValueError, "calculation"):
            answer_finqa_example(make_example())


class FinQAScoringTests(unittest.TestCase):
    def test_normalizes_financial_number_formats(self):
        self.assertEqual(normalize_answer("$1,234.50"), 1234.5)
        self.assertEqual(normalize_answer("($25)"), -25.0)
        self.assertEqual(normalize_answer("YES"), "yes")

    def test_matches_percentage_with_decimal_gold_answer(self):
        self.assertTrue(answers_match("93.5%", 0.935))

    def test_allows_small_rounding_difference(self):
        self.assertTrue(answers_match("24.69", 24.69136))

    def test_rejects_invalid_or_non_finite_answer(self):
        self.assertIsNone(normalize_answer("not available"))
        self.assertFalse(answers_match("NaN", 0))

    def test_loads_included_sample(self):
        examples = load_examples(DEFAULT_DATA_FILE)

        self.assertEqual(len(examples), 3)
        self.assertEqual(examples[0]["id"], "V/2008/page_17.pdf-1")

    def test_evaluation_continues_after_one_api_error(self):
        examples = [
            make_example("correct", 0.25),
            make_example("error", 0.25),
            make_example("incorrect", 0.50),
        ]

        def fake_answer_function(example):
            if example["id"] == "error":
                raise RuntimeError("Temporary API error")

            return {
                "answer": "25%",
                "calculation": "(125 - 100) / 100 = 25%",
            }

        # Hide the report printed by the evaluator during the unit test.
        output = io.StringIO()
        with redirect_stdout(output):
            summary = run_evaluation(
                examples,
                limit=3,
                answer_function=fake_answer_function,
            )

        self.assertEqual(summary["attempted"], 3)
        self.assertEqual(summary["correct"], 1)
        self.assertEqual(summary["incorrect"], 1)
        self.assertEqual(summary["errors"], 1)
        self.assertAlmostEqual(summary["accuracy"], 100 / 3)


if __name__ == "__main__":
    unittest.main()
