import os
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adaccount import AdAccount

INSIGHT_FIELDS = [
    "date_start", "impressions", "reach", "clicks", "ctr", "cpc",
    "spend", "actions", "action_values", "frequency", "cpm",
]

def _extract_action(actions, action_type):
    if not actions:
        return 0.0
    for a in actions:
        if a.get("action_type") == action_type:
            return float(a.get("value", 0))
    return 0.0

def _extract_action_primary(actions):
    """Fallback to 'purchase' if 'offsite_conversion.fb_pixel_purchase' is not available."""
    val = _extract_action(actions, "offsite_conversion.fb_pixel_purchase")
    return val if val else _extract_action(actions, "purchase")

def _compute_roas(action_values, spend):
    revenue = _extract_action_primary(action_values)
    spend_val = float(spend) if spend else 0
    return round(revenue / spend_val, 2) if spend_val else 0.0

def _parse_row(row, extra_fields=None):
    row = dict(row)
    spend = row.get("spend", 0)
    actions = row.get("actions", [])
    action_values = row.get("action_values", [])
    result = {
        "date": row.get("date_start"),
        "campaign_id": row.get("campaign_id"),
        "campaign_name": row.get("campaign_name"),
        "impressions": int(row.get("impressions", 0)),
        "reach": int(row.get("reach", 0)),
        "frequency": round(float(row.get("frequency", 0)), 2),
        "clicks": int(row.get("clicks", 0)),
        "ctr": round(float(row.get("ctr", 0)), 2),
        "cpc": round(float(row.get("cpc", 0)), 2),
        "cpm": round(float(row.get("cpm", 0)), 2),
        "spend": round(float(spend), 2),
        "purchases": int(_extract_action_primary(actions)),
        "revenue": round(_extract_action_primary(action_values), 2),
        "roas": _compute_roas(action_values, spend),
    }
    if extra_fields:
        result.update(extra_fields(row))
    return result

def fetch_campaigns(account_id, date_preset="last_30d", access_token=None):
    token = access_token or os.environ.get("META_ACCESS_TOKEN")
    if not token:
        raise ValueError("META_ACCESS_TOKEN environment variable is not set")
    FacebookAdsApi.init(access_token=token)
    account = AdAccount(account_id)
    insights = account.get_insights(
        fields=["campaign_id", "campaign_name"] + INSIGHT_FIELDS,
        params={"date_preset": date_preset, "time_increment": 1, "level": "campaign"},
    )
    return [_parse_row(r) for r in insights]

def fetch_adsets(account_id, date_preset="last_30d", access_token=None):
    token = access_token or os.environ.get("META_ACCESS_TOKEN")
    if not token:
        raise ValueError("META_ACCESS_TOKEN environment variable is not set")
    FacebookAdsApi.init(access_token=token)
    account = AdAccount(account_id)
    insights = account.get_insights(
        fields=["campaign_id", "campaign_name", "adset_id", "adset_name"] + INSIGHT_FIELDS,
        params={"date_preset": date_preset, "time_increment": 1, "level": "adset"},
    )
    return [_parse_row(r, lambda row: {"adset_id": row.get("adset_id"), "adset_name": row.get("adset_name")}) for r in insights]
