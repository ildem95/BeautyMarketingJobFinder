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


def test_prefilter_rejects_foreign_location_before_llm():
    job = make_job("Brand Manager", location="Kuala Lumpur, Malaysia")

    result = prefilter_job(job)

    assert result.should_classify is False
    assert "sede fuori target" in result.reason


def test_prefilter_rejects_internships_before_llm():
    job = make_job("Marketing Internship", description="Stage curriculare nel team brand.")

    result = prefilter_job(job)

    assert result.should_classify is False
    assert "stage" in result.reason


def test_prefilter_keeps_relevant_milan_brand_role():
    job = make_job(
        "Junior Brand Manager Dermocosmesi",
        location="Milano, Provincia di Milano",
        description="Ruolo nel team marketing per lancio prodotti skincare.",
    )

    result = prefilter_job(job)

    assert result.should_classify is True
