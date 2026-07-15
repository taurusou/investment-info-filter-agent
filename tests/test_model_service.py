import unittest

from services.model_service import _extract_json_payload


class ModelServiceTests(unittest.TestCase):
    def test_extract_json_payload_from_markdown_block(self):
        raw_response = '''```json
{
  "ticker": "AAPL",
  "items": [
    {
      "title": "Apple unveils new AI features",
      "label": "Positive"
    }
  ]
}
```'''

        payload = _extract_json_payload(raw_response)

        self.assertEqual(payload["ticker"], "AAPL")
        self.assertEqual(payload["items"][0]["label"], "Positive")


if __name__ == "__main__":
    unittest.main()
