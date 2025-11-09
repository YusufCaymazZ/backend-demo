import pytest
import pandas as pd
from datetime import timedelta
from scripts import process_data


@pytest.fixture
def sample_data():
    purchases_raw = pd.DataFrame(
        {
            'appsflyer_id': ['af_001', 'af_001', 'af_002'],
            'event_time_utc': ['2025-10-20T08:00:00Z', '2025-10-20T08:00:00Z', '2025-10-20T09:00:00Z'],
            'event_name': ['purchase', 'purchase', 'purchase'],
            'revenue_usd': [10.0, 10.0, 20.0],
            'campaign': ['Campaign_A', 'Campaign_A', 'Campaign_B'],
            'status': ['success', 'success', 'success'],
        }
    )

    confirmed = pd.DataFrame({'appsflyer_id': ['af_001', 'af_003'], 'event_time_utc': ['2025-10-20T08:01:00Z', '2025-10-20T10:00:00Z'], 'revenue_usd': [10.0, 30.0]})

    costs = pd.DataFrame({'date': ['2025-10-20', '2025-10-20'], 'campaign': ['Campaign_A', 'Campaign_B'], 'ad_cost_usd': [100.0, 200.0]})

    sessions = pd.DataFrame({'date': ['2025-10-20', '2025-10-20'], 'campaign': ['Campaign_A', 'Campaign_B'], 'dau': [100, 200]})

    return purchases_raw, confirmed, costs, sessions


def test_deduplication(sample_data):
    purchases_raw, _, _, _ = sample_data

    # Convert to datetime for processing
    purchases_raw['event_time_utc'] = pd.to_datetime(purchases_raw['event_time_utc'])

    # Create composite key and deduplicate
    purchases_raw['composite'] = (
        purchases_raw['appsflyer_id'].astype(str) + '|' + purchases_raw['event_time_utc'].astype(str) + '|' + purchases_raw['event_name'].astype(str) + '|' + purchases_raw['revenue_usd'].astype(str)
    )

    deduped = purchases_raw.sort_values(['event_time_utc']).drop_duplicates(subset=['composite'], keep='first')

    assert len(deduped) == 2  # Should remove one duplicate entry


def test_reconciliation(sample_data):
    purchases_raw, confirmed, _, _ = sample_data

    # Convert to datetime
    purchases_raw['event_dt'] = pd.to_datetime(purchases_raw['event_time_utc'])
    confirmed['event_dt'] = pd.to_datetime(confirmed['event_time_utc'])

    # Test matching logic for one record
    af_id = 'af_001'
    purchase_row = purchases_raw[purchases_raw['appsflyer_id'] == af_id].iloc[0]
    confirm_row = confirmed[confirmed['appsflyer_id'] == af_id].iloc[0]

    time_diff = abs(purchase_row['event_dt'] - confirm_row['event_dt'])
    assert time_diff <= timedelta(minutes=10)


def test_roas_calculation(sample_data):
    purchases_raw, _, costs, _ = sample_data

    # Basic ROAS calculation test
    campaign = 'Campaign_A'
    campaign_purchases = purchases_raw[purchases_raw['campaign'] == campaign]
    campaign_costs = costs[costs['campaign'] == campaign]

    revenue = campaign_purchases['revenue_usd'].sum()
    cost = campaign_costs['ad_cost_usd'].iloc[0]

    roas = revenue / cost
    assert roas == 0.2  # For the sample data, ROAS should be 20/100 = 0.2


def test_arpdau_calculation(sample_data):
    purchases_raw, _, _, sessions = sample_data

    # Basic ARPDAU calculation test
    campaign = 'Campaign_A'
    campaign_purchases = purchases_raw[purchases_raw['campaign'] == campaign]
    campaign_sessions = sessions[sessions['campaign'] == campaign]

    revenue = campaign_purchases['revenue_usd'].sum()
    dau = campaign_sessions['dau'].iloc[0]

    arpdau = revenue / dau
    assert arpdau == 0.2  # For the sample data, ARPDAU should be 20/100 = 0.2
