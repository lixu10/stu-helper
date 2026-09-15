from app.competition_calendar import EVENTS, public_competition_calendar


def test_calendar_contains_every_policy_competition_for_both_years():
    result = public_competition_calendar()

    assert result["summary"]["uniqueCompetitions"] == 41
    assert result["summary"]["policyEntries"] == 47
    assert len(EVENTS) == 41
    assert len(result["items"]) == 82
    assert {item["year"] for item in result["items"]} == {2026, 2027}


def test_calendar_marks_2027_estimates_and_preserves_known_official_dates():
    result = public_competition_calendar()
    entries = {(item["id"], item["year"]): item for item in result["items"]}

    mcm = entries[("mcm", 2027)]
    assert mcm["status"] == "official"
    assert mcm["startDate"] == "2027-01-28"
    assert mcm["endDate"] == "2027-02-01"

    estimated = entries[("cumcm", 2027)]
    assert estimated["status"] == "estimated"
    assert "推算" in estimated["basis"]
    assert estimated["source"]["url"].startswith("https://")


def test_calendar_sort_dates_put_unknown_events_at_year_end():
    result = public_competition_calendar()
    off_year = next(
        item
        for item in result["items"]
        if item["id"] == "challenge-academic-national" and item["year"] == 2026
    )

    assert off_year["sortDate"] == "2026-12-31"
    assert off_year["status"] == "not-held"
