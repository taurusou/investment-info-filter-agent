import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from finqa_mvp import (
    DEFAULT_DATA_FILE,
    answers_match,
    compare_answers,
    find_cached_response,
    load_examples,
    load_response_cache,
    make_empty_cache,
    normalize_answer,
    run_evaluation,
    save_response_cache,
    score_model_response,
    store_cached_response,
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
            "exe_ans_scale": "ratio",
            # These fields must never be copied into the API prompt.
            "program": "SECRET_PROGRAM_SHOULD_NOT_APPEAR",
        },
    }


def supported_response(answer="25%"):
    """Return a response whose operands all appear in make_example()."""

    return {
        "answer": answer,
        "calculation": "(125 - 100) / 100 * 100",
        "evidence": ["125", "100"],
    }


class FinQAServiceTests(unittest.TestCase):
    @patch("services.model_service._call_openai")
    def test_answers_example_without_leaking_gold_data(self, mock_call):
        example = make_example(expected_answer=987654.321)
        mock_call.return_value = """
        {
          "answer": "25%",
          "calculation": "(125 - 100) / 100 * 100",
          "evidence": ["125", "100"]
        }
        """

        result = answer_finqa_example(example)

        self.assertEqual(result["answer"], "25%")
        self.assertIn("(125 - 100)", result["calculation"])
        self.assertEqual(result["evidence"], ["125", "100"])

        # The first API argument is the user prompt.
        prompt = mock_call.call_args.args[0]
        self.assertIn("The report states", prompt)
        self.assertIn("2025 | 100", prompt)
        self.assertIn("percentage increase", prompt)
        self.assertIn('"evidence"', prompt)
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
    def test_missing_support_fields_becomes_unsupported(self, mock_call):
        # A valid final answer should remain scorable even if the model forgets
        # the optional quality-audit fields.
        mock_call.return_value = '{"answer": "25%"}'

        example = make_example()
        result = answer_finqa_example(example)
        score = score_model_response(example, result)

        self.assertEqual(result["calculation"], "")
        self.assertEqual(result["evidence"], [])
        self.assertEqual(score["category"], "unsupported")


class FinQAScoringTests(unittest.TestCase):
    def test_normalizes_financial_number_formats(self):
        self.assertEqual(normalize_answer("$1,234.50"), 1234.5)
        self.assertEqual(normalize_answer("($25)"), -25.0)
        self.assertEqual(normalize_answer("YES"), "yes")

    def test_matches_percentage_with_decimal_ratio_gold(self):
        self.assertEqual(
            compare_answers("93.5%", 0.935, "ratio"),
            "correct",
        )

    def test_percentage_scale_metadata_rejects_unit_error(self):
        self.assertEqual(
            compare_answers("0.935%", 0.935, "ratio"),
            "incorrect",
        )
        self.assertEqual(
            compare_answers("127.4%", 127.4, "number"),
            "incorrect",
        )

    def test_handles_percentage_point_gold_and_rounding(self):
        # FinQA also stores some percentage answers as percentage points.
        self.assertEqual(
            compare_answers("24.69%", 24.69136, "percentage_points"),
            "numerically_close",
        )

    def test_small_rounding_difference_is_close_not_strict(self):
        self.assertEqual(
            compare_answers("24.69", 24.69136),
            "numerically_close",
        )
        self.assertTrue(answers_match("24.69", 24.69136))

    def test_rejects_invalid_non_finite_and_wrong_answers(self):
        self.assertIsNone(normalize_answer("not available"))
        self.assertFalse(answers_match("NaN", 0))
        self.assertEqual(compare_answers("95%", 0.935), "incorrect")

    def test_scores_supported_strict_answer_as_correct(self):
        score = score_model_response(make_example(), supported_response())

        self.assertEqual(score["category"], "correct")
        self.assertTrue(score["supported"])

    def test_scores_supported_rounded_answer_as_numerically_close(self):
        example = make_example(expected_answer=0.251)
        score = score_model_response(example, supported_response("25%"))

        self.assertEqual(score["category"], "numerically_close")

    def test_scores_correct_looking_answer_with_fake_evidence_as_unsupported(self):
        response = {
            "answer": "25%",
            "calculation": "999 / 3996 * 100",
            "evidence": ["999", "3996"],
        }

        score = score_model_response(make_example(), response)

        self.assertEqual(score["category"], "unsupported")
        self.assertFalse(score["supported"])
        self.assertIn("not found", score["reason"])

    def test_scores_uncited_calculation_operand_as_unsupported(self):
        response = {
            "answer": "25%",
            "calculation": "125 / 500 * 100",
            "evidence": ["125"],
        }

        score = score_model_response(make_example(), response)

        self.assertEqual(score["category"], "unsupported")
        self.assertIn("500", score["reason"])

    def test_scores_wrong_arithmetic_as_unsupported(self):
        response = {
            "answer": "25%",
            "calculation": "125 + 100",
            "evidence": ["125", "100"],
        }

        score = score_model_response(make_example(), response)

        self.assertEqual(score["category"], "unsupported")
        self.assertIn("does not produce", score["reason"])

    def test_scores_non_arithmetic_explanation_as_unsupported(self):
        response = {
            "answer": "25%",
            "calculation": "I used the evidence",
            "evidence": ["125"],
        }

        score = score_model_response(make_example(), response)

        self.assertEqual(score["category"], "unsupported")

    def test_answer_cannot_be_used_as_an_uncited_operand(self):
        response = {
            "answer": "25%",
            "calculation": "25 * 1",
            "evidence": ["100"],
        }

        score = score_model_response(make_example(), response)

        self.assertEqual(score["category"], "unsupported")
        self.assertIn("25", score["reason"])

    def test_constant_only_calculation_with_irrelevant_evidence_is_unsupported(self):
        example = make_example(expected_answer=2)
        example["qa"]["exe_ans_scale"] = "number"
        response = {
            "answer": "2",
            "calculation": "1 + 1",
            "evidence": ["125"],
        }

        score = score_model_response(example, response)

        self.assertEqual(score["category"], "unsupported")
        self.assertIn("not used", score["reason"])

    def test_percent_evidence_keeps_its_unit(self):
        example = make_example(expected_answer=1)
        example["qa"]["exe_ans_scale"] = "number"
        example["table"] = [
            ["name", "value"],
            ["rate", "0.25%"],
            ["factor", "4"],
        ]
        response = {
            "answer": "1",
            "calculation": "0.25 * 4",
            "evidence": ["0.25", "4"],
        }

        score = score_model_response(example, response)

        self.assertEqual(score["category"], "unsupported")
        self.assertIn("0.25", score["reason"])

    def test_accounting_negative_is_not_treated_as_positive(self):
        example = make_example(expected_answer=25)
        example["qa"]["exe_ans_scale"] = "number"
        example["table"] = [["loss"], ["($25)"]]
        response = {
            "answer": "25",
            "calculation": "25 * 1",
            "evidence": ["25"],
        }

        score = score_model_response(example, response)

        self.assertEqual(score["category"], "unsupported")
        self.assertIn("not found", score["reason"])

    def test_percent_input_allows_conversion_for_non_percent_answer(self):
        expected_answer = 9896 / 23.6 * 100
        example = make_example(expected_answer=expected_answer)
        example["qa"]["question"] = "What were total operating expenses?"
        example["qa"]["exe_ans_scale"] = "number"
        example["table"] = [
            ["metric", "value"],
            ["operating income", "9896"],
            ["operating margin", "23.6%"],
        ]
        response = {
            "answer": str(expected_answer),
            "calculation": "9896 / 23.6 * 100",
            "evidence": ["9896", "23.6%"],
        }

        score = score_model_response(example, response)

        self.assertEqual(score["category"], "correct")
        self.assertTrue(score["supported"])

    def test_equals_sign_is_rejected_in_v2_calculation(self):
        response = supported_response()
        response["calculation"] = "125 - 100 = 999"

        score = score_model_response(make_example(), response)

        self.assertEqual(score["category"], "unsupported")
        self.assertIn("equals sign", score["reason"])

    def test_subtraction_without_spaces_is_parsed_correctly(self):
        response = {
            "answer": "25%",
            "calculation": "(125-100)/100*100",
            "evidence": ["125", "100"],
        }

        score = score_model_response(make_example(), response)

        self.assertEqual(score["category"], "correct")

    def test_wrong_answer_remains_incorrect_when_evidence_is_bad(self):
        response = {
            "answer": "80%",
            "calculation": "999 / 1250 * 100",
            "evidence": ["999", "1250"],
        }

        score = score_model_response(make_example(), response)

        self.assertEqual(score["category"], "incorrect")
        self.assertFalse(score["supported"])

    def test_evidence_matching_uses_whole_numbers_not_substrings(self):
        example = make_example()
        example["table"] = [["value"], ["160"]]
        response = {
            "answer": "25%",
            "calculation": "60 / 240 * 100",
            "evidence": ["60", "240"],
        }

        score = score_model_response(example, response)

        self.assertEqual(score["category"], "unsupported")

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

            return supported_response()

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
        self.assertEqual(summary["unsupported_claims"], 0)
        self.assertAlmostEqual(summary["strict_accuracy"], 100 / 3)

    def test_summary_counts_bad_evidence_even_when_answer_is_incorrect(self):
        response = {
            "answer": "80%",
            "calculation": "999 / 1250 * 100",
            "evidence": ["999", "1250"],
        }

        with redirect_stdout(io.StringIO()):
            summary = run_evaluation(
                [make_example()],
                limit=1,
                answer_function=lambda unused_example: response,
            )

        self.assertEqual(summary["incorrect"], 1)
        self.assertEqual(summary["unsupported"], 0)
        self.assertEqual(summary["unsupported_claims"], 1)

    def test_missing_answer_scale_skips_api_call(self):
        example = make_example()
        del example["qa"]["exe_ans_scale"]
        call_count = 0

        def fake_answer_function(unused_example):
            nonlocal call_count
            call_count += 1
            return supported_response()

        with redirect_stdout(io.StringIO()):
            summary = run_evaluation(
                [example],
                limit=1,
                answer_function=fake_answer_function,
            )

        self.assertEqual(call_count, 0)
        self.assertEqual(summary["errors"], 1)

    def test_yes_no_example_is_rejected_before_api_call(self):
        example = make_example(expected_answer="yes")
        call_count = 0

        def fake_answer_function(unused_example):
            nonlocal call_count
            call_count += 1
            return supported_response()

        with redirect_stdout(io.StringIO()):
            summary = run_evaluation(
                [example],
                limit=1,
                answer_function=fake_answer_function,
            )

        self.assertEqual(call_count, 0)
        self.assertEqual(summary["errors"], 1)


class FinQACacheTests(unittest.TestCase):
    def test_cache_save_and_load_round_trip(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            cache_file = Path(temporary_directory) / "responses.json"
            example = make_example()
            cache = make_empty_cache()

            store_cached_response(
                cache,
                example,
                supported_response(),
                model_name="test-model",
            )
            save_response_cache(cache_file, cache)
            loaded_cache = load_response_cache(cache_file)

            loaded_response = find_cached_response(loaded_cache, example)
            self.assertEqual(loaded_response["answer"], "25%")
            self.assertEqual(loaded_response["evidence"], ["125", "100"])
            record = loaded_cache["responses"][example["id"]]
            self.assertEqual(record["model"], "test-model")

    def test_second_run_reuses_cache_without_another_api_call(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            cache_file = Path(temporary_directory) / "responses.json"
            example = make_example()
            call_count = 0

            def fake_answer_function(unused_example):
                nonlocal call_count
                call_count += 1
                return supported_response()

            with redirect_stdout(io.StringIO()):
                first_summary = run_evaluation(
                    [example],
                    limit=1,
                    answer_function=fake_answer_function,
                    cache_file=cache_file,
                    model_name="test-model",
                )
                second_summary = run_evaluation(
                    [example],
                    limit=1,
                    answer_function=fake_answer_function,
                    cache_file=cache_file,
                    offline=True,
                    model_name="test-model",
                )

            self.assertEqual(call_count, 1)
            self.assertEqual(first_summary["correct"], 1)
            self.assertEqual(second_summary["correct"], 1)

    def test_refresh_bypasses_an_existing_cache_entry(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            cache_file = Path(temporary_directory) / "responses.json"
            example = make_example()
            cache = make_empty_cache()
            store_cached_response(
                cache,
                example,
                supported_response(),
                model_name="old-model",
            )
            save_response_cache(cache_file, cache)
            call_count = 0

            def fake_answer_function(unused_example):
                nonlocal call_count
                call_count += 1
                return supported_response()

            with redirect_stdout(io.StringIO()):
                run_evaluation(
                    [example],
                    limit=1,
                    answer_function=fake_answer_function,
                    cache_file=cache_file,
                    refresh=True,
                    model_name="new-model",
                )

            refreshed_cache = load_response_cache(cache_file)
            record = refreshed_cache["responses"][example["id"]]
            self.assertEqual(call_count, 1)
            self.assertEqual(record["model"], "new-model")

    def test_offline_cache_miss_never_calls_answer_function(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            cache_file = Path(temporary_directory) / "responses.json"
            call_count = 0

            def fake_answer_function(unused_example):
                nonlocal call_count
                call_count += 1
                return supported_response()

            with redirect_stdout(io.StringIO()):
                summary = run_evaluation(
                    [make_example()],
                    limit=1,
                    answer_function=fake_answer_function,
                    cache_file=cache_file,
                    offline=True,
                )

            self.assertEqual(call_count, 0)
            self.assertEqual(summary["errors"], 1)

    def test_changed_question_does_not_reuse_old_response(self):
        example = make_example()
        cache = make_empty_cache()
        store_cached_response(
            cache,
            example,
            supported_response(),
            model_name="test-model",
        )

        changed_example = make_example()
        changed_example["qa"]["question"] = "A different question?"

        self.assertIsNone(find_cached_response(cache, changed_example))

    def test_changed_report_data_does_not_reuse_old_response(self):
        example = make_example()
        cache = make_empty_cache()
        store_cached_response(
            cache,
            example,
            supported_response(),
            model_name="test-model",
        )

        changed_example = make_example()
        changed_example["table"][2][1] = "130"

        self.assertIsNone(
            find_cached_response(
                cache,
                changed_example,
                model_name="test-model",
            )
        )

    def test_changed_model_does_not_reuse_old_response(self):
        example = make_example()
        cache = make_empty_cache()
        store_cached_response(
            cache,
            example,
            supported_response(),
            model_name="old-model",
        )

        self.assertIsNone(
            find_cached_response(
                cache,
                example,
                model_name="new-model",
            )
        )

    def test_changed_prompt_version_does_not_reuse_old_response(self):
        example = make_example()
        cache = make_empty_cache()
        store_cached_response(
            cache,
            example,
            supported_response(),
            model_name="test-model",
        )
        cache["responses"][example["id"]]["prompt_version"] = "old-prompt"

        self.assertIsNone(
            find_cached_response(
                cache,
                example,
                model_name="test-model",
            )
        )

    @patch("finqa_mvp.save_response_cache", side_effect=OSError("disk full"))
    def test_cache_write_failure_keeps_quality_result(self, unused_save):
        with tempfile.TemporaryDirectory() as temporary_directory:
            cache_file = Path(temporary_directory) / "responses.json"
            output = io.StringIO()

            with redirect_stdout(output):
                summary = run_evaluation(
                    [make_example()],
                    limit=1,
                    answer_function=lambda unused_example: supported_response(),
                    cache_file=cache_file,
                    model_name="test-model",
                )

            self.assertEqual(summary["correct"], 1)
            self.assertEqual(summary["errors"], 0)
            self.assertIn("Cache warning", output.getvalue())

    def test_invalid_cache_json_raises_clear_error(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            cache_file = Path(temporary_directory) / "responses.json"
            cache_file.write_text("not valid JSON", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "not valid JSON"):
                load_response_cache(cache_file)

    def test_old_cache_format_raises_clear_error(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            cache_file = Path(temporary_directory) / "responses.json"
            cache_file.write_text(
                '{"format_version": 1, "responses": {}}',
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "format_version"):
                load_response_cache(cache_file)


if __name__ == "__main__":
    unittest.main()
