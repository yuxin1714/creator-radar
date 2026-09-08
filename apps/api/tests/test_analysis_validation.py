import unittest
from app.services.analysis_validation import validate_analysis


class AnalysisValidationTests(unittest.TestCase):
    def setUp(self):
        self.result = dict(summary="Summary", hook="Hook", structure=["Opening"], key_points=["Point"], content_score=76, score_reasons=["Reason"], evidence=[dict(claim="Claim", quote="原文短句")])

    def test_exact_source_evidence_passes(self):
        self.assertEqual(validate_analysis(self.result, "这里是原文短句。")['content_score'], 76)

    def test_invented_quote_rejected(self):
        with self.assertRaises(ValueError):
            validate_analysis(self.result, "完全不同的原文")

    def test_invalid_scores_and_missing_fields_rejected(self):
        for score in [-1, 101, True, "76"]:
            with self.subTest(score=score), self.assertRaises(ValueError):
                validate_analysis({**self.result, 'content_score':score}, "原文短句")
        with self.assertRaises(ValueError):
            validate_analysis({'summary':'Only summary'}, '原文短句')
