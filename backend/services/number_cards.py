"""
Number Card PDF Generator

Generates printable competitor number cards for Irish Dance feiseanna.
- 2-up layout on US Letter (two 8.5" x 5.5" landscape cards per page)
- Sorted by School Name, then Dancer Name for easy distribution
- QR code links to check-in URL for stage monitors
"""

from io import BytesIO
from typing import List, Optional
from dataclasses import dataclass
from datetime import date

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

import qrcode
from qrcode.image.pil import PilImage


@dataclass
class NumberCardData:
    """Data needed to render a single number card."""
    dancer_id: str
    dancer_name: str
    school_name: Optional[str]
    competitor_number: int
    age_group: str  # e.g., "U10"
    level: str  # e.g., "Prizewinner"
    competition_codes: List[str]  # e.g., ["102", "115", "120"]
    feis_name: str
    feis_date: date


def generate_qr_code(url: str, size: int = 150) -> BytesIO:
    """Generate a QR code image for the given URL."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
    )
    qr.add_data(url)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to bytes
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return buffer


def draw_number_card(
    c: canvas.Canvas,
    card: NumberCardData,
    x_offset: float,
    y_offset: float,
    card_width: float,
    card_height: float,
    base_url: str
) -> None:
    """
    Draw a single number card at the specified position.
    
    Layout (landscape card, 8.5" x 5.5"):
    ┌─────────────────────────────────────────────────────┐
    │ [Age/Level]                              [QR Code]  │  <- Zone C + QR
    │                                                     │
    │                                                     │
    │                    ███  ███                         │
    │                    █  █ █  █                        │  <- Zone A (NUMBER)
    │                    ███  ███                         │
    │                    █    █                           │
    │                    █    █                           │
    │                                                     │
    │ ─────────────────────────────────────────────────── │
    │ Dancer Name                          School Name    │  <- Zone B
    │ Comp: 102, 115, 120                                 │  <- Zone D
    └─────────────────────────────────────────────────────┘
    """
    # Card boundaries
    left = x_offset
    right = x_offset + card_width
    top = y_offset + card_height
    bottom = y_offset
    
    # Margins
    margin = 0.3 * inch
    inner_left = left + margin
    inner_right = right - margin
    inner_top = top - margin
    inner_bottom = bottom + margin
    
    # Draw card border (light gray, for cutting guide)
    c.setStrokeColorRGB(0.8, 0.8, 0.8)
    c.setLineWidth(0.5)
    c.rect(x_offset, y_offset, card_width, card_height)
    
    # Reset to black for content
    c.setStrokeColorRGB(0, 0, 0)
    c.setFillColorRGB(0, 0, 0)
    
    # === ZONE C: Age Group & Level (top-left corner) ===
    c.setFont("Helvetica-Bold", 14)
    level_text = f"{card.age_group} / {card.level}"
    c.drawString(inner_left, inner_top - 14, level_text)
    
    # === QR CODE (top-right corner) ===
    qr_size = 1.0 * inch
    checkin_url = f"{base_url}/checkin/{card.dancer_id}"
    qr_buffer = generate_qr_code(checkin_url)
    qr_image = ImageReader(qr_buffer)
    c.drawImage(
        qr_image,
        inner_right - qr_size,
        inner_top - qr_size - 5,  # slight offset from top
        width=qr_size,
        height=qr_size
    )
    
    # === ZONE A: THE BIG NUMBER (center, 60-70% of card) ===
    # Calculate available vertical space for number
    zone_a_top = inner_top - qr_size - 0.2 * inch
    zone_a_bottom = inner_bottom + 0.8 * inch  # Leave room for Zone B & D
    zone_a_height = zone_a_top - zone_a_bottom
    
    # Make the number as big as possible
    number_str = str(card.competitor_number)
    
    # Dynamic font sizing based on number of digits
    if len(number_str) <= 2:
        font_size = min(zone_a_height * 0.85, 280)
    elif len(number_str) == 3:
        font_size = min(zone_a_height * 0.75, 220)
    else:
        font_size = min(zone_a_height * 0.65, 180)
    
    c.setFont("Helvetica-Bold", font_size)
    
    # Center the number horizontally and vertically in Zone A
    number_width = c.stringWidth(number_str, "Helvetica-Bold", font_size)
    number_x = left + (card_width - number_width) / 2
    number_y = zone_a_bottom + (zone_a_height - font_size) / 2
    
    c.drawString(number_x, number_y, number_str)
    
    # === ZONE B: Dancer Name & School (bottom) ===
    c.setFont("Helvetica", 11)
    
    # Dancer name (left-aligned)
    c.drawString(inner_left, inner_bottom + 0.4 * inch, card.dancer_name)
    
    # School name (right-aligned)
    if card.school_name:
        school_width = c.stringWidth(card.school_name, "Helvetica", 11)
        c.drawRightString(inner_right, inner_bottom + 0.4 * inch, card.school_name)
    
    # === ZONE D: Competition numbers (footer, if space permits) ===
    if card.competition_codes:
        c.setFont("Helvetica", 9)
        comp_text = "Comp: " + ", ".join(card.competition_codes[:10])  # Limit to 10
        if len(card.competition_codes) > 10:
            comp_text += "..."
        c.drawString(inner_left, inner_bottom + 0.1 * inch, comp_text)


def generate_number_cards_pdf(
    cards: List[NumberCardData],
    base_url: str = "https://openfeis.com"
) -> BytesIO:
    """
    Generate a PDF with number cards, 2-up per page.
    
    Cards are sorted by school name (blanks last), then dancer name.
    
    Args:
        cards: List of NumberCardData objects
        base_url: Base URL for QR code check-in links
    
    Returns:
        BytesIO buffer containing the PDF
    """
    if not cards:
        raise ValueError("No cards to generate")
    
    # Sort cards: school name (blanks last), then dancer name
    def sort_key(card: NumberCardData):
        school = card.school_name or "zzz_no_school"  # Blanks sort last
        return (school.lower(), card.dancer_name.lower())
    
    sorted_cards = sorted(cards, key=sort_key)
    
    # Create PDF buffer
    buffer = BytesIO()
    
    # Page setup: US Letter Portrait
    page_width, page_height = letter  # 612 x 792 points
    
    # Card dimensions: 2-up means two landscape cards stacked vertically
    # Each card is 8.5" wide x 5.5" tall
    card_width = page_width  # 8.5 inches = 612 points
    card_height = page_height / 2  # 5.5 inches = 396 points
    
    c = canvas.Canvas(buffer, pagesize=letter)
    
    # Track position (0 = top card, 1 = bottom card)
    position = 0
    
    for card in sorted_cards:
        if position == 0:
            # Top card (y_offset is at half page height)
            y_offset = card_height
        else:
            # Bottom card (y_offset is at 0)
            y_offset = 0
        
        draw_number_card(
            c=c,
            card=card,
            x_offset=0,
            y_offset=y_offset,
            card_width=card_width,
            card_height=card_height,
            base_url=base_url
        )
        
        position += 1
        
        # After 2 cards, start a new page
        if position >= 2:
            c.showPage()
            position = 0
    
    # If we ended with an odd number, the page is already shown
    # But if position > 0, we have an incomplete page that needs to be finalized
    if position > 0:
        c.showPage()
    
    c.save()
    buffer.seek(0)
    return buffer


def generate_single_card_pdf(
    card: NumberCardData,
    base_url: str = "https://openfeis.com"
) -> BytesIO:
    """
    Generate a PDF with a single number card (for reprints).
    
    The card is placed on the top half of a US Letter page.
    """
    buffer = BytesIO()
    
    page_width, page_height = letter
    card_width = page_width
    card_height = page_height / 2
    
    c = canvas.Canvas(buffer, pagesize=letter)
    
    # Draw on top half of page
    draw_number_card(
        c=c,
        card=card,
        x_offset=0,
        y_offset=card_height,  # Top half
        card_width=card_width,
        card_height=card_height,
        base_url=base_url
    )
    
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

