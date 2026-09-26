import random
from typing import Any, Dict

# In-memory mock databases seeded with sample customer data
MOCK_ORDERS: Dict[str, Dict[str, Any]] = {
    "ORD-101": {
        "order_id": "ORD-101",
        "customer_email": "sarah@example.com",
        "status": "shipped",
        "carrier": "USPS",
        "tracking_number": "9400111899562537829102",
        "estimated_delivery": "In 2 business days",
        "items": [{"name": "Colombia Huila (12oz)", "grind": "Whole Bean", "quantity": 2}],
    },
    "ORD-102": {
        "order_id": "ORD-102",
        "customer_email": "marcus@example.com",
        "status": "processing",
        "carrier": None,
        "tracking_number": None,
        "estimated_delivery": "Ships within 24 hours",
        "items": [{"name": "Ethiopia Yirgacheffe (12oz)", "grind": "Medium / Drip", "quantity": 1}],
    },
    "ORD-103": {
        "order_id": "ORD-103",
        "customer_email": "elena@example.com",
        "status": "delivered",
        "carrier": "FedEx",
        "tracking_number": "782910245612",
        "estimated_delivery": "Delivered yesterday at 2:15 PM",
        "items": [{"name": "House Blend (12oz)", "grind": "French Press", "quantity": 1}],
    },
}

MOCK_SUBSCRIPTIONS: Dict[str, Dict[str, Any]] = {
    "sarah@example.com": {
        "email": "sarah@example.com",
        "status": "active",
        "plan": "Starter",
        "frequency": "every 4 weeks",
        "next_shipment_date": "2026-10-10",
        "roast": "House Blend",
        "bags_per_shipment": 1,
        "is_paused": False,
    },
    "marcus@example.com": {
        "email": "marcus@example.com",
        "status": "active",
        "plan": "Regular",
        "frequency": "every 2 weeks",
        "next_shipment_date": "2026-10-02",
        "roast": "Ethiopia Yirgacheffe",
        "bags_per_shipment": 1,
        "is_paused": False,
    },
    "david@example.com": {
        "email": "david@example.com",
        "status": "paused",
        "plan": "Enthusiast",
        "frequency": "every 2 weeks",
        "resume_date": "2026-11-01",
        "roast": "Colombia Huila",
        "bags_per_shipment": 2,
        "is_paused": True,
    },
}

PLAN_PRICING: Dict[str, Dict[str, Any]] = {
    "starter": {
        "plan": "Starter",
        "frequency": "1 bag (12oz) every 4 weeks",
        "price_per_bag": "$16.00",
        "discount": "0%",
        "shipping": "$4.95 flat rate (standard 3-5 business days)",
        "default_roast": "House Blend (swappable anytime)",
    },
    "regular": {
        "plan": "Regular",
        "frequency": "1 bag (12oz) every 2 weeks",
        "price_per_bag": "$15.00",
        "discount": "5% discount",
        "shipping": "$4.95 flat rate (standard 3-5 business days)",
        "default_roast": "Any roast selectable",
    },
    "enthusiast": {
        "plan": "Enthusiast",
        "frequency": "2 bags (12oz each) every 2 weeks",
        "price_per_bag": "$14.00",
        "discount": "12% discount",
        "shipping": "Free shipping included",
        "default_roast": "Any roast selectable",
    },
}


def _should_simulate_failure(_force_failure: bool = False) -> bool:
    """Simulate a ~10% failure chance or force failure for testing."""
    if _force_failure:
        return True
    return random.random() < 0.10


def check_order_status(order_id: str, _force_failure: bool = False) -> Dict[str, Any]:
    """Look up the status and shipment details for a customer order."""
    if _should_simulate_failure(_force_failure):
        return {"error": "service_timeout", "message": "Aurelio order management service timed out."}

    normalized_id = order_id.strip().upper()
    order = MOCK_ORDERS.get(normalized_id)
    if not order:
        return {"error": "not_found", "message": f"Order '{order_id}' was not found in our system."}
    return {"success": True, "order": order}


def check_subscription_status(email: str, _force_failure: bool = False) -> Dict[str, Any]:
    """Check subscription details, next billing/shipment date, and status by email."""
    if _should_simulate_failure(_force_failure):
        return {"error": "service_timeout", "message": "Aurelio subscription service timed out."}

    normalized_email = email.strip().lower()
    sub = MOCK_SUBSCRIPTIONS.get(normalized_email)
    if not sub:
        return {"error": "not_found", "message": f"No active subscription found for '{email}'."}
    return {"success": True, "subscription": sub}


def pause_subscription(email: str, months: int, _force_failure: bool = False) -> Dict[str, Any]:
    """Pause an active customer subscription for 1 to 3 months."""
    if _should_simulate_failure(_force_failure):
        return {"error": "service_timeout", "message": "Aurelio billing service timed out."}

    normalized_email = email.strip().lower()
    sub = MOCK_SUBSCRIPTIONS.get(normalized_email)
    if not sub:
        return {"error": "not_found", "message": f"Cannot pause: no subscription found for '{email}'."}

    if months < 1 or months > 3:
        return {
            "error": "invalid_duration",
            "message": f"Subscriptions can only be paused for 1 to 3 months. Requested: {months} months.",
        }

    sub["is_paused"] = True
    sub["status"] = "paused"
    sub["paused_for_months"] = months
    return {
        "success": True,
        "message": f"Subscription for {email} successfully paused for {months} month(s).",
        "subscription": sub,
    }


def get_plan_pricing(plan_name: str, _force_failure: bool = False) -> Dict[str, Any]:
    """Get tier details, per-bag pricing, discounts, and shipping rules for a subscription plan."""
    if _should_simulate_failure(_force_failure):
        return {"error": "service_timeout", "message": "Pricing service timed out."}

    key = plan_name.strip().lower()
    # Handle common variations
    if "starter" in key:
        matched_key = "starter"
    elif "regular" in key:
        matched_key = "regular"
    elif "enthusiast" in key:
        matched_key = "enthusiast"
    else:
        matched_key = key

    plan = PLAN_PRICING.get(matched_key)
    if not plan:
        return {
            "error": "not_found",
            "message": f"Plan '{plan_name}' not found. Available plans: Starter, Regular, Enthusiast.",
            "available_plans": list(PLAN_PRICING.keys()),
        }
    return {"success": True, "plan": plan}
