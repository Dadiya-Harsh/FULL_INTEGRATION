import unittest
import nltk
from utils import parse_response

class TestUtils(unittest.TestCase):

    def setUp(self):
        # Download vader_lexicon before running tests
        try:
            nltk.data.find('sentiment.vader_lexicon')
        except LookupError:
            nltk.download('vader_lexicon')

    def test_parse_response_valid_json(self):
        response_text = '''
        {
            "sentiment_score": 0.85,
            "skills": ["Leadership", "Communication"],
            "tasks": [
                {
                    "task": "Prepare the report",
                    "assigned_by": "Manager",
                    "assigned_to": "John",
                    "deadline": "Friday",
                    "status": "Pending"
                }
            ]
        }
        '''
        sentiment, skills, tasks = parse_response(response_text)
        self.assertEqual(sentiment, 0.85)
        self.assertEqual(skills, ["Leadership", "Communication"])
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["task"], "Prepare the report")

if __name__ == "__main__":
    unittest.main()