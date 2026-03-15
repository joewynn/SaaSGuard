"""Customers router – placeholder for Phase 6 Customer 360 endpoint."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/{customer_id}")
async def get_customer(customer_id: str) -> dict[str, str]:
    """Customer 360 profile – implemented in Phase 6."""
    return {"customer_id": customer_id, "status": "endpoint coming in Phase 6"}
