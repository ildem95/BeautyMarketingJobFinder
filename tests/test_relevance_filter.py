import unittest

from shared.models import JobPosting
from relevance_filter import prefilter_job


def make_job(title, location="Milano, Italy", description="", contract_type=None):
    return JobPosting(
        company="Beauty Co",
        title=title,
        location=location,
        url="https://example.com/job",
        source="test",
        description=description,
        contract_type=contract_type,
    )


class RelevancePrefilterTest(unittest.TestCase):
    def test_rejects_foreign_location_before_llm(self):
        job = make_job("Brand Manager", location="Kuala Lumpur, Malaysia")

        result = prefilter_job(job)

        self.assertFalse(result.should_classify)
        self.assertIn("sede fuori target", result.reason)

    def test_rejects_internships_before_llm(self):
        job = make_job("Marketing Internship", description="Stage curriculare nel team brand.")

        result = prefilter_job(job)

        self.assertFalse(result.should_classify)
        self.assertIn("stage", result.reason)

    def test_keeps_relevant_milan_brand_role(self):
        job = make_job(
            "Junior Brand Manager Dermocosmesi",
            location="Milano, Provincia di Milano",
            description="Ruolo nel team marketing per lancio prodotti skincare.",
        )

        result = prefilter_job(job)

        self.assertTrue(result.should_classify)


if __name__ == "__main__":
    unittest.main()
