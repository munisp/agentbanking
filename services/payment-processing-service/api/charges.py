from fastapi import APIRouter, HTTPException, responses
from utils import create_logger

charges_router = APIRouter()

logger = create_logger(__name__)


@charges_router.get("/withdrawal/{id_type}/{id_value}")
def get_withdrawal_charges(
    id_type: str,
    id_value: str,
    currency: str = "NGN",
    amount: str = "0.00",
):
    """Get withdrawal charges for a payer.

    This endpoint returns the withdrawal charges that should be applied
    for a transfer from a given account. For now, returns minimal charges.
    """
    try:
        logger.info(
            f"Get withdrawal charges id_type={id_type} id_value={id_value} "
            f"currency={currency} amount={amount}"
        )

        # For now, return minimal charge (0.5% of amount or minimum 50 base units)
        try:
            amount_value = float(amount)
        except (ValueError, TypeError):
            amount_value = 0.0

        # Calculate charge as 0.5% of amount, minimum 50
        calculated_charge = max(amount_value * 0.005, 50.0)

        return responses.JSONResponse(
            content={
                "amount": str(calculated_charge),
                "currency": currency,
            },
            status_code=200,
        )

    except Exception as e:
        logger.error(f"Unexpected error during get_withdrawal_charges: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Get withdrawal charges failed.",
        )
