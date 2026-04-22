from unittest.mock import patch, MagicMock
from fetchers.meta_fetcher import fetch_campaigns, fetch_adsets, _extract_action, _compute_roas

def test_extract_action_returns_value():
    actions = [{"action_type": "purchase", "value": "3"}]
    assert _extract_action(actions, "purchase") == 3.0

def test_extract_action_returns_zero_when_missing():
    assert _extract_action([], "purchase") == 0.0
    assert _extract_action(None, "purchase") == 0.0

def test_compute_roas():
    action_values = [{"action_type": "offsite_conversion.fb_pixel_purchase", "value": "500"}]
    assert _compute_roas(action_values, "100") == 5.0

def test_compute_roas_zero_spend():
    assert _compute_roas([], "0") == 0.0

def test_compute_roas_purchase_fallback():
    action_values = [{"action_type": "purchase", "value": "300"}]
    assert _compute_roas(action_values, "100") == 3.0

def _mock_insight_row(campaign_id="111", campaign_name="Spring", adset_id=None, adset_name=None):
    row = {
        "date_start": "2026-04-01",
        "campaign_id": campaign_id,
        "campaign_name": campaign_name,
        "impressions": "10000",
        "reach": "8000",
        "frequency": "1.25",
        "clicks": "200",
        "ctr": "2.0",
        "cpc": "0.50",
        "cpm": "5.00",
        "spend": "100.00",
        "actions": [{"action_type": "purchase", "value": "5"}],
        "action_values": [{"action_type": "offsite_conversion.fb_pixel_purchase", "value": "500"}],
    }
    if adset_id is not None:
        row["adset_id"] = adset_id
        row["adset_name"] = adset_name
    return row

@patch("fetchers.meta_fetcher.AdAccount")
@patch("fetchers.meta_fetcher.FacebookAdsApi")
def test_fetch_campaigns_returns_normalized_rows(mock_api, mock_account):
    mock_account.return_value.get_insights.return_value = [_mock_insight_row()]
    rows = fetch_campaigns("act_123456", access_token="fake_token")
    assert len(rows) == 1
    r = rows[0]
    assert r["date"] == "2026-04-01"
    assert r["campaign_id"] == "111"
    assert r["spend"] == 100.0
    assert r["roas"] == 5.0
    assert r["purchases"] == 5

@patch("fetchers.meta_fetcher.AdAccount")
@patch("fetchers.meta_fetcher.FacebookAdsApi")
def test_fetch_adsets_includes_adset_fields(mock_api, mock_account):
    row = _mock_insight_row(adset_id="222", adset_name="Lookalike")
    mock_account.return_value.get_insights.return_value = [row]
    rows = fetch_adsets("act_123456", access_token="fake_token")
    assert rows[0]["adset_id"] == "222"
    assert rows[0]["adset_name"] == "Lookalike"
