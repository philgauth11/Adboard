from unittest.mock import patch, MagicMock
from fetchers.google_fetcher import fetch_campaigns, fetch_adsets

def _mock_campaign_row(campaign_id=1, campaign_name="Brand", date_str="2026-04-01",
                       impressions=5000, clicks=100, ctr=0.02, avg_cpc=500000,
                       cost_micros=50000000, conversions=10.0, conv_value=300.0):
    row = MagicMock()
    row.campaign.id = campaign_id
    row.campaign.name = campaign_name
    row.segments.date = date_str
    row.metrics.impressions = impressions
    row.metrics.clicks = clicks
    row.metrics.ctr = ctr
    row.metrics.average_cpc = avg_cpc       # micros: 500000 = $0.50
    row.metrics.cost_micros = cost_micros   # micros: 50000000 = $50
    row.metrics.conversions = conversions
    row.metrics.conversions_value = conv_value
    return row

@patch("fetchers.google_fetcher._build_client")
def test_fetch_campaigns_returns_normalized_rows(mock_build):
    mock_service = MagicMock()
    mock_build.return_value.get_service.return_value = mock_service
    mock_service.search.return_value = [_mock_campaign_row()]

    rows = fetch_campaigns("1234567890", days=30)
    assert len(rows) == 1
    r = rows[0]
    assert r["date"] == "2026-04-01"
    assert r["campaign_id"] == "1"
    assert r["spend"] == 50.0
    assert r["roas"] == 6.0   # 300 / 50
    assert r["purchases"] == 10

def _mock_adgroup_row():
    row = _mock_campaign_row()
    row.ad_group = MagicMock()
    row.ad_group.id = 99
    row.ad_group.name = "Ad Group A"
    return row

@patch("fetchers.google_fetcher._build_client")
def test_fetch_adsets_includes_adgroup_fields(mock_build):
    mock_service = MagicMock()
    mock_build.return_value.get_service.return_value = mock_service
    mock_service.search.return_value = [_mock_adgroup_row()]

    rows = fetch_adsets("1234567890", days=30)
    assert rows[0]["adset_id"] == "99"
    assert rows[0]["adset_name"] == "Ad Group A"
