"""Reusable source-shaped data frames for deterministic tests."""

from __future__ import annotations

import pandas as pd


def minimal_source_frames() -> dict[str, pd.DataFrame]:
    """Create the minimal source frames value used by these tests."""

    transactions = pd.DataFrame(
        [
            {
                "household_id": "1",
                "store_id": "10",
                "basket_id": "100",
                "product_id": "1000",
                "quantity": 2.0,
                "sales_value": 5.0,
                "retail_disc": 0.0,
                "coupon_disc": 0.0,
                "coupon_match_disc": 0.0,
                "week": 1,
                "transaction_timestamp": "2017-01-01T10:00:00",
            },
            {
                "household_id": "1",
                "store_id": "10",
                "basket_id": "100",
                "product_id": "2000",
                "quantity": 1.0,
                "sales_value": 3.0,
                "retail_disc": 1.0,
                "coupon_disc": 0.5,
                "coupon_match_disc": 0.0,
                "week": 1,
                "transaction_timestamp": "2017-01-01T10:00:00",
            },
            {
                "household_id": "2",
                "store_id": "11",
                "basket_id": "200",
                "product_id": "1000",
                "quantity": 1.0,
                "sales_value": 4.0,
                "retail_disc": 0.0,
                "coupon_disc": 0.0,
                "coupon_match_disc": 0.0,
                "week": 2,
                "transaction_timestamp": "2017-01-08T12:00:00",
            },
        ]
    )
    promotions = pd.DataFrame(
        [
            {
                "product_id": "1000",
                "store_id": "10",
                "display_location": "0",
                "mailer_location": "A",
                "week": 1,
            },
            {
                "product_id": "1000",
                "store_id": "10",
                "display_location": "3",
                "mailer_location": "0",
                "week": 1,
            },
            {
                "product_id": "1000",
                "store_id": "10",
                "display_location": "5",
                "mailer_location": "A",
                "week": 1,
            },
        ]
    )
    products = pd.DataFrame(
        [
            {
                "product_id": "1000",
                "manufacturer_id": "9",
                "department": "GROCERY",
                "brand": "National",
                "product_category": "SOUP",
                "product_type": "CANNED",
                "package_size": "10 OZ",
            },
            {
                "product_id": "2000",
                "manufacturer_id": "8",
                "department": "GROCERY",
                "brand": "Private",
                "product_category": None,
                "product_type": None,
                "package_size": None,
            },
        ]
    )
    demographics = pd.DataFrame(
        [{"household_id": "1", "age": "35-44", "income": "50-74K"}]
    )
    campaigns = pd.DataFrame([{"campaign_id": "1", "household_id": "1"}])
    campaign_descriptions = pd.DataFrame(
        [
            {
                "campaign_id": "1",
                "campaign_type": "Type A",
                "start_date": "2017-01-01",
                "end_date": "2017-01-31",
            }
        ]
    )
    coupons = pd.DataFrame(
        [{"coupon_upc": "900", "product_id": "1000", "campaign_id": "1"}]
    )
    coupon_redemptions = pd.DataFrame(
        [
            {
                "household_id": "1",
                "coupon_upc": "900",
                "campaign_id": "1",
                "redemption_date": "2017-01-15",
            }
        ]
    )
    return {
        "transactions": transactions,
        "promotions": promotions,
        "products": products,
        "demographics": demographics,
        "campaigns": campaigns,
        "campaign_descriptions": campaign_descriptions,
        "coupons": coupons,
        "coupon_redemptions": coupon_redemptions,
    }
