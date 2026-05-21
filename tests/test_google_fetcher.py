from unittest.mock import MagicMock, patch
from fetchers.google_fetcher import fetch_campaigns, _parse_row


def _mock_row(spend_micros=100_000_000, conversions=5.0, conversions_value=500.0,
              impressions=10000, clicks=200, ctr=0.02, avg_cpc=500_000,
              campaign_id=1, campaign_name="Spring", date_str="2026-04-01"):
    row = MagicMock()
    row.metrics.cost_micros = spend_micros
    row.metrics.conversions = conversions
    row.metrics.conversions_value = conversions_value
    row.metrics.impressions = impressions
    row.metrics.clicks = clicks
    row.metrics.ctr = ctr
    row.metrics.average_cpc = avg_cpc
    row.campaign.id = campaign_id
    row.campaign.name = campaign_name
    row.segments.date = date_str
    return row


def test_parse_row_includes_leads():
    row = _mock_row(conversions=7.0)
    result = _parse_row(row)
    assert result["leads"] == 7


def test_parse_row_leads_equals_purchases():
    row = _mock_row(conversions=4.0)
    result = _parse_row(row)
    assert result["leads"] == result["purchases"]


def test_parse_row_calculates_roas():
    row = _mock_row(spend_micros=100_000_000, conversions_value=500.0)
    result = _parse_row(row)
    assert result["roas"] == 5.0


def test_parse_row_zero_spend():
    row = _mock_row(spend_micros=0)
    result = _parse_row(row)
    assert result["roas"] == 0.0
    assert result["cpm"] == 0.0


@patch("fetchers.google_fetcher._build_client")
def test_fetch_campaigns_returns_leads(mock_build):
    service = MagicMock()
    mock_build.return_value.get_service.return_value = service
    service.search.return_value = [_mock_row(conversions=9.0)]
    rows = fetch_campaigns("123-456-7890", days=30)
    assert len(rows) == 1
    assert rows[0]["leads"] == 9
    assert rows[0]["purchases"] == 9
