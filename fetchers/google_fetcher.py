import os
from datetime import date, timedelta
from google.ads.googleads.client import GoogleAdsClient

def _build_client():
    required = [
        "GOOGLE_ADS_DEVELOPER_TOKEN",
        "GOOGLE_ADS_CLIENT_ID",
        "GOOGLE_ADS_CLIENT_SECRET",
        "GOOGLE_ADS_REFRESH_TOKEN",
    ]
    missing = [k for k in required if k not in os.environ]
    if missing:
        raise EnvironmentError(f"Missing required env vars: {', '.join(missing)}")
    return GoogleAdsClient.load_from_dict({
        "developer_token": os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"],
        "client_id": os.environ["GOOGLE_ADS_CLIENT_ID"],
        "client_secret": os.environ["GOOGLE_ADS_CLIENT_SECRET"],
        "refresh_token": os.environ["GOOGLE_ADS_REFRESH_TOKEN"],
        "use_proto_plus": True,
    })

def _date_range(days):
    end = date.today()
    start = end - timedelta(days=days)
    return start.isoformat(), end.isoformat()

def _parse_row(row, extra_fields=None):
    spend = row.metrics.cost_micros / 1_000_000
    revenue = float(row.metrics.conversions_value)
    impressions = row.metrics.impressions
    result = {
        "date": row.segments.date,
        "campaign_id": str(row.campaign.id),
        "campaign_name": row.campaign.name,
        "impressions": impressions,
        "reach": 0,
        "frequency": 0.0,
        "clicks": row.metrics.clicks,
        "ctr": round(float(row.metrics.ctr) * 100, 2),
        "cpc": round(row.metrics.average_cpc / 1_000_000, 2),
        "cpm": round(spend / impressions * 1000, 2) if impressions else 0.0,
        "spend": round(spend, 2),
        "purchases": int(row.metrics.conversions),
        "revenue": round(revenue, 2),
        "roas": round(revenue / spend, 2) if spend else 0.0,
    }
    if extra_fields:
        result.update(extra_fields(row))
    return result

def fetch_campaigns(customer_id, days=30):
    client = _build_client()
    service = client.get_service("GoogleAdsService")
    start, end = _date_range(days)
    query = f"""
        SELECT campaign.id, campaign.name, segments.date,
               metrics.impressions, metrics.clicks, metrics.ctr,
               metrics.average_cpc, metrics.cost_micros,
               metrics.conversions, metrics.conversions_value
        FROM campaign
        WHERE segments.date BETWEEN '{start}' AND '{end}'
          AND campaign.status != 'REMOVED'
    """
    return [_parse_row(r) for r in service.search(customer_id=customer_id, query=query)]

def fetch_adsets(customer_id, days=30):
    client = _build_client()
    service = client.get_service("GoogleAdsService")
    start, end = _date_range(days)
    query = f"""
        SELECT campaign.id, campaign.name, ad_group.id, ad_group.name, segments.date,
               metrics.impressions, metrics.clicks, metrics.ctr,
               metrics.average_cpc, metrics.cost_micros,
               metrics.conversions, metrics.conversions_value
        FROM ad_group
        WHERE segments.date BETWEEN '{start}' AND '{end}'
          AND ad_group.status != 'REMOVED'
    """
    return [_parse_row(r, lambda row: {"adset_id": str(row.ad_group.id), "adset_name": row.ad_group.name})
            for r in service.search(customer_id=customer_id, query=query)]
