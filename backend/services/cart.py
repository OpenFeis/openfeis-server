"""
Cart calculation service for Open Feis.

Implements the complex pricing logic for feis registration including:
- Family cap calculation (caps qualifying fees per family)
- Late fee auto-application
- Multi-dancer handling (same family shares the cap)
- Fee items (venue levy, merchandise)
"""

from datetime import datetime, date
from typing import List, Optional, Tuple
from dataclasses import dataclass
from uuid import UUID
from sqlmodel import Session, select

from backend.scoring_engine.models_platform import (
    Feis, Competition, Entry, Dancer, User,
    FeisSettings, FeeItem, FeeCategory, Order, OrderItem, PaymentStatus
)


@dataclass
class CartLineItem:
    """A single line item in the cart."""
    id: str  # competition_id or fee_item_id
    type: str  # 'competition' or 'fee_item'
    name: str
    description: Optional[str]
    dancer_id: Optional[str]  # For competitions
    dancer_name: Optional[str]
    unit_price_cents: int
    quantity: int
    total_cents: int
    category: FeeCategory
    

@dataclass
class CartTotals:
    """Calculated cart totals."""
    line_items: List[CartLineItem]
    
    # Subtotals
    qualifying_subtotal_cents: int  # Subject to family cap
    non_qualifying_subtotal_cents: int  # Not subject to cap
    subtotal_cents: int  # Total before discounts
    
    # Discounts
    family_discount_cents: int  # Amount saved by family cap
    family_cap_applied: bool  # Whether cap kicked in
    family_cap_cents: Optional[int]  # What the cap is (for display)
    
    # Late fee
    late_fee_cents: int
    late_fee_applied: bool
    late_fee_date: Optional[date]
    
    # Final
    total_cents: int
    
    # Helper info
    dancer_count: int  # Number of unique dancers
    competition_count: int  # Number of competitions
    
    # Savings info (for display)
    savings_percent: int  # Percentage saved by family cap


def get_feis_settings(session: Session, feis_id: UUID) -> FeisSettings:
    """
    Get or create feis settings.
    
    If settings don't exist for this feis, returns a new instance with defaults
    (but doesn't persist it - that's up to the caller).
    """
    settings = session.exec(
        select(FeisSettings).where(FeisSettings.feis_id == feis_id)
    ).first()
    
    if settings:
        return settings
    
    # Return default settings (not persisted)
    return FeisSettings(feis_id=feis_id)


def get_required_fee_items(session: Session, feis_id: UUID) -> List[FeeItem]:
    """Get all required fee items for a feis (auto-added to every order)."""
    return session.exec(
        select(FeeItem)
        .where(FeeItem.feis_id == feis_id)
        .where(FeeItem.required == True)
        .where(FeeItem.active == True)
    ).all()


def is_late_registration(settings: FeisSettings) -> bool:
    """Check if we're past the late fee date."""
    if not settings.late_fee_date:
        return False
    return date.today() > settings.late_fee_date


def is_registration_open(settings: FeisSettings) -> Tuple[bool, str]:
    """
    Check if registration is currently open.
    
    Returns (is_open, message) tuple.
    """
    now = datetime.utcnow()
    
    if settings.registration_opens and now < settings.registration_opens:
        return False, f"Registration opens on {settings.registration_opens.strftime('%B %d, %Y at %I:%M %p')}"
    
    if settings.registration_closes and now > settings.registration_closes:
        return False, f"Registration closed on {settings.registration_closes.strftime('%B %d, %Y at %I:%M %p')}"
    
    return True, "Registration is open"


def calculate_cart(
    session: Session,
    feis_id: UUID,
    user_id: UUID,
    competition_ids: List[UUID],
    dancer_ids: List[UUID],
    fee_item_quantities: Optional[dict] = None  # {fee_item_id: quantity}
) -> CartTotals:
    """
    Calculate cart totals with family max applied.
    
    This is the core pricing engine. It:
    1. Groups entries by dancer
    2. Calculates qualifying vs non-qualifying fees
    3. Applies family cap to qualifying fees only
    4. Adds late fee if applicable
    5. Adds required fee items
    
    Args:
        session: Database session
        feis_id: The feis being registered for
        user_id: The parent/purchaser (for existing entries lookup)
        competition_ids: List of competition IDs to register for
        dancer_ids: List of dancer IDs (parallel to competition_ids)
        fee_item_quantities: Optional dict of {fee_item_id: quantity} for optional items
    
    Returns:
        CartTotals with full breakdown
    """
    fee_item_quantities = fee_item_quantities or {}
    
    # Get feis and settings
    feis = session.get(Feis, feis_id)
    if not feis:
        raise ValueError(f"Feis {feis_id} not found")
    
    settings = get_feis_settings(session, feis_id)
    
    # Build line items
    line_items: List[CartLineItem] = []
    qualifying_total = 0
    non_qualifying_total = 0
    dancer_set = set()
    
    # Process competitions
    for comp_id, dancer_id in zip(competition_ids, dancer_ids):
        competition = session.get(Competition, comp_id)
        dancer = session.get(Dancer, dancer_id)
        
        if not competition or not dancer:
            continue
        
        dancer_set.add(str(dancer_id))
        
        # Determine price (use competition's price_cents)
        price = competition.price_cents or settings.per_competition_fee_cents
        
        line_items.append(CartLineItem(
            id=str(comp_id),
            type='competition',
            name=competition.name,
            description=f"{competition.level.value.title()} level",
            dancer_id=str(dancer_id),
            dancer_name=dancer.name,
            unit_price_cents=price,
            quantity=1,
            total_cents=price,
            category=competition.fee_category or FeeCategory.QUALIFYING
        ))
        
        # Add to appropriate total
        category = competition.fee_category or FeeCategory.QUALIFYING
        if category == FeeCategory.QUALIFYING:
            qualifying_total += price
        else:
            non_qualifying_total += price
    
    # Add base entry fee per dancer (qualifying)
    base_fee_per_dancer = settings.base_entry_fee_cents
    if base_fee_per_dancer > 0 and len(dancer_set) > 0:
        for dancer_id in dancer_set:
            dancer = session.get(Dancer, UUID(dancer_id))
            if dancer:
                line_items.append(CartLineItem(
                    id=f"base_{dancer_id}",
                    type='base_fee',
                    name=f"Entry Fee - {dancer.name}",
                    description="Per-dancer base entry fee",
                    dancer_id=dancer_id,
                    dancer_name=dancer.name,
                    unit_price_cents=base_fee_per_dancer,
                    quantity=1,
                    total_cents=base_fee_per_dancer,
                    category=FeeCategory.QUALIFYING
                ))
                qualifying_total += base_fee_per_dancer
    
    # Get required fee items
    required_items = get_required_fee_items(session, feis_id)
    for item in required_items:
        line_items.append(CartLineItem(
            id=str(item.id),
            type='fee_item',
            name=item.name,
            description=item.description,
            dancer_id=None,
            dancer_name=None,
            unit_price_cents=item.amount_cents,
            quantity=1,
            total_cents=item.amount_cents,
            category=item.category
        ))
        
        if item.category == FeeCategory.QUALIFYING:
            qualifying_total += item.amount_cents
        else:
            non_qualifying_total += item.amount_cents
    
    # Add optional fee items
    for fee_item_id_str, quantity in fee_item_quantities.items():
        if quantity <= 0:
            continue
        fee_item = session.get(FeeItem, UUID(fee_item_id_str))
        if not fee_item or fee_item.feis_id != feis_id or not fee_item.active:
            continue
        if fee_item.required:
            continue  # Already added above
        
        # Respect max quantity
        quantity = min(quantity, fee_item.max_quantity)
        item_total = fee_item.amount_cents * quantity
        
        line_items.append(CartLineItem(
            id=str(fee_item.id),
            type='fee_item',
            name=fee_item.name,
            description=fee_item.description,
            dancer_id=None,
            dancer_name=None,
            unit_price_cents=fee_item.amount_cents,
            quantity=quantity,
            total_cents=item_total,
            category=fee_item.category
        ))
        
        if fee_item.category == FeeCategory.QUALIFYING:
            qualifying_total += item_total
        else:
            non_qualifying_total += item_total
    
    # Calculate family cap discount
    family_discount = 0
    family_cap_applied = False
    family_cap = settings.family_max_cents
    
    if family_cap is not None and qualifying_total > family_cap:
        family_discount = qualifying_total - family_cap
        qualifying_total = family_cap
        family_cap_applied = True
    
    # Calculate late fee
    late_fee = 0
    late_fee_applied = False
    
    if is_late_registration(settings) and settings.late_fee_cents > 0:
        # Late fee per entry (per competition, not per dancer)
        competition_count = len([li for li in line_items if li.type == 'competition'])
        late_fee = settings.late_fee_cents * competition_count
        late_fee_applied = True
    
    # Calculate totals
    subtotal = qualifying_total + non_qualifying_total
    total = subtotal - family_discount + late_fee
    
    # Calculate savings percentage
    original_qualifying = qualifying_total + family_discount
    savings_percent = 0
    if family_discount > 0 and original_qualifying > 0:
        savings_percent = int((family_discount / original_qualifying) * 100)
    
    return CartTotals(
        line_items=line_items,
        qualifying_subtotal_cents=qualifying_total,
        non_qualifying_subtotal_cents=non_qualifying_total,
        subtotal_cents=subtotal,
        family_discount_cents=family_discount,
        family_cap_applied=family_cap_applied,
        family_cap_cents=family_cap,
        late_fee_cents=late_fee,
        late_fee_applied=late_fee_applied,
        late_fee_date=settings.late_fee_date,
        total_cents=total,
        dancer_count=len(dancer_set),
        competition_count=len([li for li in line_items if li.type == 'competition']),
        savings_percent=savings_percent
    )


def create_order(
    session: Session,
    feis_id: UUID,
    user_id: UUID,
    cart_totals: CartTotals,
    pay_at_door: bool = False
) -> Order:
    """
    Create an order from calculated cart totals.
    
    This creates the Order record and links entries to it.
    For pay_at_door, the order is marked as PAY_AT_DOOR status.
    For online payment, the order is PENDING until Stripe confirms.
    
    Returns the created Order.
    """
    order = Order(
        feis_id=feis_id,
        user_id=user_id,
        subtotal_cents=cart_totals.subtotal_cents,
        qualifying_subtotal_cents=cart_totals.qualifying_subtotal_cents,
        non_qualifying_subtotal_cents=cart_totals.non_qualifying_subtotal_cents,
        family_discount_cents=cart_totals.family_discount_cents,
        late_fee_cents=cart_totals.late_fee_cents,
        total_cents=cart_totals.total_cents,
        status=PaymentStatus.PAY_AT_DOOR if pay_at_door else PaymentStatus.PENDING
    )
    
    session.add(order)
    session.flush()  # Get the order ID
    
    # Create entries for competitions
    for line_item in cart_totals.line_items:
        if line_item.type == 'competition' and line_item.dancer_id:
            entry = Entry(
                dancer_id=UUID(line_item.dancer_id),
                competition_id=UUID(line_item.id),
                order_id=order.id,
                paid=pay_at_door,  # If paying at door, mark as unpaid but registered
                pay_later=pay_at_door
            )
            session.add(entry)
        elif line_item.type == 'fee_item' and line_item.id:
            # Create order item for fee items
            order_item = OrderItem(
                order_id=order.id,
                fee_item_id=UUID(line_item.id),
                quantity=line_item.quantity,
                unit_price_cents=line_item.unit_price_cents,
                total_cents=line_item.total_cents
            )
            session.add(order_item)
    
    session.commit()
    session.refresh(order)
    
    return order


def get_family_total_for_feis(
    session: Session,
    feis_id: UUID,
    user_id: UUID
) -> int:
    """
    Get the total qualifying fees already paid by this family for this feis.
    
    Used to calculate remaining family cap when adding more registrations.
    """
    # Get all dancers for this user
    dancers = session.exec(
        select(Dancer).where(Dancer.parent_id == user_id)
    ).all()
    dancer_ids = [d.id for d in dancers]
    
    if not dancer_ids:
        return 0
    
    # Get all paid orders for this feis from this user
    orders = session.exec(
        select(Order)
        .where(Order.feis_id == feis_id)
        .where(Order.user_id == user_id)
        .where(Order.status.in_([PaymentStatus.COMPLETED, PaymentStatus.PAY_AT_DOOR]))
    ).all()
    
    # Sum up qualifying totals (after cap was applied to each order)
    total = sum(o.qualifying_subtotal_cents for o in orders)
    
    return total

