from typing import Any, Dict
from langchain_core.tools import tool

from app.tools import mock_api


@tool
def check_order_status(order_id: str) -> Dict[str, Any]:
    """Look up shipping, tracking, and item details for an existing Aurelio Coffee order using the order ID (e.g. ORD-101). Use whenever a customer asks about their order status or delivery."""
    return mock_api.check_order_status(order_id=order_id)


@tool
def check_subscription_status(email: str) -> Dict[str, Any]:
    """Check a customer's coffee subscription status, current plan tier, next scheduled shipment date, and selected roast by customer email address."""
    return mock_api.check_subscription_status(email=email)


@tool
def pause_subscription(email: str, months: int) -> Dict[str, Any]:
    """Pause an active customer coffee subscription by customer email for 1, 2, or 3 months. Use when a customer requests to pause or hold their recurring subscription."""
    return mock_api.pause_subscription(email=email, months=months)


@tool
def get_plan_pricing(plan_name: str) -> Dict[str, Any]:
    """Retrieve pricing, discounts, shipping conditions, and frequency details for an Aurelio subscription plan (Starter, Regular, or Enthusiast). Use when customers ask about subscription costs or comparison."""
    return mock_api.get_plan_pricing(plan_name=plan_name)


AURELIO_TOOLS = [
    check_order_status,
    check_subscription_status,
    pause_subscription,
    get_plan_pricing,
]
