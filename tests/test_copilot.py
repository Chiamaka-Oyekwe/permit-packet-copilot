import json
from datetime import date

import pytest

from copilot import extract
from copilot.narrative import draft_cover_letter
from copilot.packet import check_packet
from copilot.rules import (applies, build_checklist, business_days_between,
                           lead_time_check, list_cities, load_city)


def ids(checklist):
    return {r["id"] for r in checklist}


def test_every_city_file_is_well_formed():
    assert list_cities() == ["dallas", "fort_worth", "richardson"]
    for slug in list_cities():
        assert extract.validate(load_city(slug)["requirements"]) == []


def test_conditions():
    job = {"method": "bore", "lane_closure": True, "pavement_age_years": 1}
    assert applies(None, job)
    assert applies({"field": "method", "op": "in", "value": ["bore", "trench"]}, job)
    assert applies({"all": [{"field": "lane_closure", "op": "eq", "value": True},
                            {"field": "pavement_age_years", "op": "lt", "value": 2}]}, job)
    assert not applies({"any": [{"field": "method", "op": "eq", "value": "aerial"}]}, job)


def test_dallas_downtown_bore_needs_tcp_profile_and_bond():
    job = {"method": "bore", "lane_closure": True, "street_class": "downtown", "new_facility": True}
    got = ids(build_checklist(load_city("dallas"), job))
    assert {"DAL-TCP", "DAL-PROFILE", "DAL-BOND", "DAL-UG", "DAL-BORE"} <= got
    assert "DAL-WAIVER" not in got and "DAL-EMERG" not in got


def test_dallas_aerial_no_closure_is_short():
    job = {"method": "aerial", "lane_closure": False, "sidewalk_closure": False}
    got = ids(build_checklist(load_city("dallas"), job))
    assert not {"DAL-TCP", "DAL-BOND", "DAL-UG", "DAL-BORE"} & got
    assert {"DAL-APP", "DAL-PLANS"} <= got


def test_residential_closure_offers_waiver():
    job = {"method": "aerial", "lane_closure": True, "street_class": "residential"}
    assert "DAL-WAIVER" in ids(build_checklist(load_city("dallas"), job))


def test_fort_worth_new_pavement_and_acreage():
    job = {"method": "trench", "pavement_cut": True, "pavement_age_years": 1, "disturbed_acres": 1.2}
    got = ids(build_checklist(load_city("fort_worth"), job))
    assert {"FTW-NEWPAVE", "FTW-SWPPP", "FTW-BORE", "FTW-LOCATE"} <= got
    old = ids(build_checklist(load_city("fort_worth"), {**job, "pavement_age_years": 5, "disturbed_acres": 0.2}))
    assert not {"FTW-NEWPAVE", "FTW-SWPPP"} & old


def test_emergency_swaps_lead_time_for_notice():
    got = ids(build_checklist(load_city("richardson"), {"emergency": True}))
    assert "RIC-EMERG" in got
    got = ids(build_checklist(load_city("dallas"), {"emergency": True}))
    assert "DAL-EMERG" in got and "DAL-LEAD" not in got


def test_business_days_skip_weekends():
    assert business_days_between(date(2026, 11, 13), date(2026, 11, 16)) == 1  # Fri to Mon
    assert business_days_between(date(2026, 11, 9), date(2026, 11, 13)) == 4
    assert business_days_between(date(2026, 11, 13), date(2026, 11, 13)) == 0


def test_lead_time_verdict():
    cl = build_checklist(load_city("fort_worth"), {})
    late = lead_time_check(cl, date(2026, 11, 11), date(2026, 11, 18))
    assert late == {"needed": 10, "have": 5, "ok": False}
    assert lead_time_check(cl, date(2026, 11, 11), date(2026, 11, 25))["ok"]
    assert lead_time_check(build_checklist(load_city("richardson"), {}), date(2026, 11, 11), date(2026, 11, 12)) is None


def test_packet_check_finds_the_gap():
    job = {"method": "bore", "lane_closure": True, "street_class": "downtown", "new_facility": True}
    cl = build_checklist(load_city("dallas"), job)
    files = ["ROW_Permit_Application_signed.pdf", "Elm_St_Construction_Plans_11x17.pdf",
             "Elm_St_Profile_Sheets.pdf", "TCP_Phase1_Phase2.pdf", "Contractor_List.pdf", "Site_Photos.zip"]
    result = check_packet(cl, files)
    assert {m["id"] for m in result["missing"]} == {"DAL-UG", "DAL-BOND"}
    assert result["unmatched"] == ["Site_Photos.zip"]


def test_a_traffic_control_plan_does_not_count_as_construction_plans():
    cl = build_checklist(load_city("dallas"), {"method": "aerial", "lane_closure": True})
    missing = {m["id"] for m in check_packet(cl, ["Traffic_Control_Plan.pdf"])["missing"]}
    assert "DAL-PLANS" in missing and "DAL-TCP" not in missing


def test_closeout_documents_are_not_flagged_missing():
    cl = build_checklist(load_city("fort_worth"), {})
    assert "FTW-ASBUILT" not in {m["id"] for m in check_packet(cl, [])["missing"]}


def test_cover_letter_flags_missing_enclosures():
    city = load_city("dallas")
    job = {"facility_owner": "Example Fiber LLC", "location": "Elm St", "method": "bore",
           "length_ft": 640, "lane_closure": True, "new_facility": True}
    cl = build_checklist(city, job)
    letter = draft_cover_letter(city, job, cl, check_packet(cl, ["application.pdf"]))
    assert "approximately 640 feet" in letter and "directional bore" in letter
    assert "Performance bond, letter of credit or cash deposit  [NOT YET IN PACKET]" in letter
    assert "Permit application signed by the facility owner\n" in letter


class FakeClient:
    """Stands in for the Anthropic client so the test needs no API key."""
    def __init__(self, text):
        self._text = text
        self.messages = self
        self.prompt = None

    def create(self, **kw):
        self.prompt = kw["messages"][0]["content"]
        return type("Msg", (), {"content": [type("Block", (), {"text": self._text})()]})()


def test_extract_parses_and_validates_a_draft():
    draft = [{"id": "X-TCP", "kind": "document", "title": "Traffic control plan", "detail": "d",
              "when": {"field": "lane_closure", "op": "eq", "value": True}, "match": ["tcp"],
              "source": {"label": "L", "cite": "Sec. 1", "url": "https://example.com"}}]
    client = FakeClient("```json\n" + json.dumps(draft) + "\n```")
    out = extract.extract("Testville", "L", "https://example.com", "ordinance text", client=client)
    assert out == draft and "ordinance text" in client.prompt


def test_extract_rejects_a_draft_with_no_citation():
    bad = [{"id": "X", "kind": "notice", "title": "t", "detail": "d", "when": {"field": "nope", "op": "eq", "value": 1},
            "source": {"label": "L", "url": "u"}}]
    with pytest.raises(ValueError) as e:
        extract.extract("T", "L", "u", "text", client=FakeClient(json.dumps(bad)))
    assert "no citation" in str(e.value) and "unknown field" in str(e.value)
