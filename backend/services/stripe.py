"""
Stripe integration service for Open Feis.

This module provides Stripe Connect integration for payment processing.
It supports multiple organizers each with their own connected Stripe account.

IMPORTANT: This is currently in STUB MODE. Actual Stripe API calls are
commented out until a Stripe account is configured. The service provides
a "test mode" experience that simulates successful payments.

To enable real Stripe:
1. Set STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET environment variables
2. Configure a Stripe Connect platform account
3. Update the is_stripe_configured() function to return True

Payment Flow:
1. Parent clicks "Pay Now"
2. Frontend calls /api/v1/checkout/create-session
3. Backend creates Stripe Checkout Session (or returns test URL in stub mode)
4. Parent completes payment on Stripe
5. Stripe webhook calls /api/v1/checkout/webhook
6. Backend marks order as paid
"""

import os
from datetime import datetime
from typing import Optional, List, Tuple
from dataclasses import dataclass
from uuid import UUID
from sqlmodel import Session, select

from backend.scoring_engine.models_platform import (
    Feis, Order, Entry, FeisSettings, PaymentStatus
)
from backend.services.cart import CartTotals

# Stripe import - commented out until needed
# import stripe


@dataclass
class CheckoutSessionResult:
    """Result of creating a checkout session."""
    success: bool
    checkout_url: Optional[str]  # URL to redirect user to
    session_id: Optional[str]  # Stripe session ID (or test ID)
    error: Optional[str]
    is_test_mode: bool  # True if using stub/test mode


@dataclass
class StripeOnboardingResult:
    """Result of creating an organizer onboarding link."""
    success: bool
    onboarding_url: Optional[str]
    error: Optional[str]
    is_test_mode: bool


def is_stripe_configured() -> bool:
    """
    Check if Stripe is properly configured.
    
    Returns True if all required Stripe credentials are present.
    When False, the system operates in "test mode" with simulated payments.
    """
    secret_key = os.environ.get("STRIPE_SECRET_KEY")
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET")
    
    # Both must be present and not empty placeholder values
    if not secret_key or secret_key.startswith("sk_test_placeholder"):
        return False
    if not webhook_secret or webhook_secret.startswith("whsec_placeholder"):
        return False
    
    return True


def get_stripe_mode() -> str:
    """
    Get the current Stripe mode for display purposes.
    
    Returns one of: 'live', 'test', 'disabled'
    """
    if not is_stripe_configured():
        return 'disabled'
    
    secret_key = os.environ.get("STRIPE_SECRET_KEY", "")
    if secret_key.startswith("sk_live_"):
        return 'live'
    return 'test'


def is_organizer_connected(feis: Feis, session: Session) -> Tuple[bool, Optional[str]]:
    """
    Check if the feis organizer has connected their Stripe account.
    
    For Stripe Connect, each organizer needs to complete onboarding
    to receive payments for their feis.
    
    Returns (is_connected, stripe_account_id)
    """
    # Check feis-level Stripe settings
    settings = session.exec(
        select(FeisSettings).where(FeisSettings.feis_id == feis.id)
    ).first()
    
    if settings and settings.stripe_account_id and settings.stripe_onboarding_complete:
        return True, settings.stripe_account_id
    
    # Fall back to legacy feis.stripe_account_id
    if feis.stripe_account_id:
        return True, feis.stripe_account_id
    
    return False, None


def create_checkout_session(
    session: Session,
    order: Order,
    cart_totals: CartTotals,
    success_url: str,
    cancel_url: str
) -> CheckoutSessionResult:
    """
    Create a Stripe Checkout Session for an order.
    
    If Stripe is not configured, returns a test mode result that
    simulates a successful checkout experience.
    
    Args:
        session: Database session
        order: The Order to pay for
        cart_totals: Calculated cart totals with line items
        success_url: URL to redirect to on successful payment
        cancel_url: URL to redirect to if payment is cancelled
    
    Returns:
        CheckoutSessionResult with checkout URL or error
    """
    feis = session.get(Feis, order.feis_id)
    if not feis:
        return CheckoutSessionResult(
            success=False,
            checkout_url=None,
            session_id=None,
            error="Feis not found",
            is_test_mode=True
        )
    
    # Check if Stripe is configured
    if not is_stripe_configured():
        # Test mode - simulate successful session creation
        test_session_id = f"test_sess_{order.id}"
        
        # In test mode, redirect directly to success with a special flag
        # The frontend will detect this and show a "test payment" confirmation
        test_checkout_url = f"{success_url}?session_id={test_session_id}&test_mode=true"
        
        return CheckoutSessionResult(
            success=True,
            checkout_url=test_checkout_url,
            session_id=test_session_id,
            error=None,
            is_test_mode=True
        )
    
    # Check if organizer has connected Stripe
    is_connected, stripe_account_id = is_organizer_connected(feis, session)
    if not is_connected:
        return CheckoutSessionResult(
            success=False,
            checkout_url=None,
            session_id=None,
            error="This feis has not set up payment processing yet. Please choose 'Pay at Door' or contact the organizer.",
            is_test_mode=False
        )
    
    # =========================================================
    # STRIPE INTEGRATION - CURRENTLY STUBBED
    # Uncomment and configure when ready to accept real payments
    # =========================================================
    
    # import stripe
    # stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
    #
    # try:
    #     # Build line items for Stripe
    #     line_items = []
    #     for item in cart_totals.line_items:
    #         line_items.append({
    #             "price_data": {
    #                 "currency": "usd",
    #                 "unit_amount": item.unit_price_cents,
    #                 "product_data": {
    #                     "name": item.name,
    #                     "description": item.description or "",
    #                 },
    #             },
    #             "quantity": item.quantity,
    #         })
    #
    #     # Add family discount as a negative line item if applicable
    #     if cart_totals.family_discount_cents > 0:
    #         line_items.append({
    #             "price_data": {
    #                 "currency": "usd",
    #                 "unit_amount": -cart_totals.family_discount_cents,
    #                 "product_data": {
    #                     "name": "Family Cap Discount",
    #                     "description": f"Family maximum of ${cart_totals.family_cap_cents / 100:.2f} applied",
    #                 },
    #             },
    #             "quantity": 1,
    #         })
    #
    #     # Add late fee if applicable
    #     if cart_totals.late_fee_cents > 0:
    #         line_items.append({
    #             "price_data": {
    #                 "currency": "usd",
    #                 "unit_amount": cart_totals.late_fee_cents,
    #                 "product_data": {
    #                     "name": "Late Registration Fee",
    #                     "description": f"Applied after {cart_totals.late_fee_date}",
    #                 },
    #             },
    #             "quantity": 1,
    #         })
    #
    #     # Create checkout session
    #     checkout_session = stripe.checkout.Session.create(
    #         payment_method_types=["card"],
    #         line_items=line_items,
    #         mode="payment",
    #         success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}",
    #         cancel_url=cancel_url,
    #         stripe_account=stripe_account_id,  # Stripe Connect
    #         metadata={
    #             "order_id": str(order.id),
    #             "feis_id": str(feis.id),
    #         }
    #     )
    #
    #     # Store session ID on order
    #     order.stripe_checkout_session_id = checkout_session.id
    #     session.add(order)
    #     session.commit()
    #
    #     return CheckoutSessionResult(
    #         success=True,
    #         checkout_url=checkout_session.url,
    #         session_id=checkout_session.id,
    #         error=None,
    #         is_test_mode=False
    #     )
    #
    # except stripe.error.StripeError as e:
    #     return CheckoutSessionResult(
    #         success=False,
    #         checkout_url=None,
    #         session_id=None,
    #         error=str(e),
    #         is_test_mode=False
    #     )
    
    # Fallback for when Stripe is "configured" but we haven't uncommented the code yet
    return CheckoutSessionResult(
        success=False,
        checkout_url=None,
        session_id=None,
        error="Stripe integration is configured but not yet activated. Please use 'Pay at Door'.",
        is_test_mode=False
    )


def handle_checkout_success(
    session: Session,
    checkout_session_id: str,
    is_test_mode: bool = False
) -> Tuple[bool, Optional[Order], Optional[str]]:
    """
    Handle successful checkout (either from webhook or test mode redirect).
    
    Marks the order as paid and updates entries.
    
    Args:
        session: Database session
        checkout_session_id: The Stripe session ID (or test session ID)
        is_test_mode: Whether this is a test mode payment
    
    Returns:
        (success, order, error_message)
    """
    # For test mode, extract order ID from session ID
    if is_test_mode and checkout_session_id.startswith("test_sess_"):
        order_id_str = checkout_session_id.replace("test_sess_", "")
        try:
            order = session.get(Order, UUID(order_id_str))
        except ValueError:
            return False, None, "Invalid test session ID"
    else:
        # Real Stripe - look up by session ID
        order = session.exec(
            select(Order).where(Order.stripe_checkout_session_id == checkout_session_id)
        ).first()
    
    if not order:
        return False, None, "Order not found"
    
    if order.status == PaymentStatus.COMPLETED:
        # Already processed - idempotent success
        return True, order, None
    
    # Mark order as paid
    order.status = PaymentStatus.COMPLETED
    order.paid_at = datetime.utcnow()
    session.add(order)
    
    # Mark all entries as paid
    entries = session.exec(
        select(Entry).where(Entry.order_id == order.id)
    ).all()
    
    for entry in entries:
        entry.paid = True
        entry.pay_later = False
        session.add(entry)
    
    session.commit()
    session.refresh(order)
    
    return True, order, None


def handle_webhook(
    session: Session,
    payload: bytes,
    signature: str
) -> Tuple[bool, str]:
    """
    Handle incoming Stripe webhook.
    
    Verifies the webhook signature and processes the event.
    
    Args:
        session: Database session
        payload: Raw request body
        signature: Stripe-Signature header value
    
    Returns:
        (success, message)
    """
    if not is_stripe_configured():
        return False, "Stripe not configured"
    
    # =========================================================
    # STRIPE WEBHOOK HANDLING - CURRENTLY STUBBED
    # Uncomment when ready to accept real webhooks
    # =========================================================
    
    # import stripe
    # webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET")
    #
    # try:
    #     event = stripe.Webhook.construct_event(
    #         payload, signature, webhook_secret
    #     )
    # except ValueError:
    #     return False, "Invalid payload"
    # except stripe.error.SignatureVerificationError:
    #     return False, "Invalid signature"
    #
    # # Handle the event
    # if event["type"] == "checkout.session.completed":
    #     checkout_session = event["data"]["object"]
    #     success, order, error = handle_checkout_success(
    #         session, checkout_session["id"], is_test_mode=False
    #     )
    #     if not success:
    #         return False, error or "Unknown error"
    #     return True, f"Order {order.id} marked as paid"
    #
    # elif event["type"] == "checkout.session.expired":
    #     # Session expired without payment
    #     checkout_session = event["data"]["object"]
    #     order = session.exec(
    #         select(Order).where(Order.stripe_checkout_session_id == checkout_session["id"])
    #     ).first()
    #     if order and order.status == PaymentStatus.PENDING:
    #         order.status = PaymentStatus.FAILED
    #         session.add(order)
    #         session.commit()
    #     return True, "Session expiry handled"
    #
    # # Unhandled event type
    # return True, f"Unhandled event type: {event['type']}"
    
    return False, "Webhook handling not yet implemented"


def create_organizer_onboarding_link(
    session: Session,
    feis_id: UUID,
    return_url: str,
    refresh_url: str
) -> StripeOnboardingResult:
    """
    Create a Stripe Connect onboarding link for a feis organizer.
    
    This is used to connect an organizer's Stripe account to receive
    payments for their feis.
    
    Args:
        session: Database session
        feis_id: The feis to connect
        return_url: URL to return to after onboarding
        refresh_url: URL to refresh the onboarding link
    
    Returns:
        StripeOnboardingResult with onboarding URL
    """
    if not is_stripe_configured():
        # Test mode - simulate onboarding
        return StripeOnboardingResult(
            success=True,
            onboarding_url=f"{return_url}?test_onboarding=true&feis_id={feis_id}",
            error=None,
            is_test_mode=True
        )
    
    # =========================================================
    # STRIPE CONNECT ONBOARDING - CURRENTLY STUBBED
    # Uncomment when ready to onboard real organizers
    # =========================================================
    
    # import stripe
    # stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
    #
    # feis = session.get(Feis, feis_id)
    # if not feis:
    #     return StripeOnboardingResult(
    #         success=False,
    #         onboarding_url=None,
    #         error="Feis not found",
    #         is_test_mode=False
    #     )
    #
    # settings = session.exec(
    #     select(FeisSettings).where(FeisSettings.feis_id == feis_id)
    # ).first()
    #
    # try:
    #     # Create or retrieve connected account
    #     if settings and settings.stripe_account_id:
    #         account = stripe.Account.retrieve(settings.stripe_account_id)
    #     else:
    #         account = stripe.Account.create(
    #             type="standard",
    #             metadata={"feis_id": str(feis_id)},
    #         )
    #         # Save the account ID
    #         if not settings:
    #             settings = FeisSettings(feis_id=feis_id)
    #         settings.stripe_account_id = account.id
    #         session.add(settings)
    #         session.commit()
    #
    #     # Create account link for onboarding
    #     account_link = stripe.AccountLink.create(
    #         account=account.id,
    #         refresh_url=refresh_url,
    #         return_url=return_url,
    #         type="account_onboarding",
    #     )
    #
    #     return StripeOnboardingResult(
    #         success=True,
    #         onboarding_url=account_link.url,
    #         error=None,
    #         is_test_mode=False
    #     )
    #
    # except stripe.error.StripeError as e:
    #     return StripeOnboardingResult(
    #         success=False,
    #         onboarding_url=None,
    #         error=str(e),
    #         is_test_mode=False
    #     )
    
    return StripeOnboardingResult(
        success=False,
        onboarding_url=None,
        error="Stripe Connect onboarding not yet implemented",
        is_test_mode=False
    )


def check_onboarding_status(
    session: Session,
    feis_id: UUID
) -> Tuple[bool, str]:
    """
    Check if an organizer has completed Stripe onboarding.
    
    Returns (is_complete, status_message)
    """
    feis = session.get(Feis, feis_id)
    if not feis:
        return False, "Feis not found"
    
    settings = session.exec(
        select(FeisSettings).where(FeisSettings.feis_id == feis_id)
    ).first()
    
    if not settings or not settings.stripe_account_id:
        return False, "Stripe account not connected"
    
    if settings.stripe_onboarding_complete:
        return True, "Stripe account connected and ready"
    
    if not is_stripe_configured():
        return False, "Stripe not configured (test mode)"
    
    # =========================================================
    # CHECK REAL STRIPE ACCOUNT STATUS - CURRENTLY STUBBED
    # =========================================================
    
    # import stripe
    # stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
    #
    # try:
    #     account = stripe.Account.retrieve(settings.stripe_account_id)
    #     if account.details_submitted and account.charges_enabled:
    #         settings.stripe_onboarding_complete = True
    #         session.add(settings)
    #         session.commit()
    #         return True, "Stripe account connected and ready"
    #     else:
    #         return False, "Stripe account setup incomplete"
    # except stripe.error.StripeError as e:
    #     return False, str(e)
    
    return False, "Stripe integration pending activation"

