"""
Hotel Reservation Web App - Flask Application
Stores bookings in bookings.json with mobile-friendly UI
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for
import json
import os
from datetime import datetime, timedelta
import uuid

app = Flask(__name__)

# Room types with pricing (per night)
ROOM_TYPES = {
    "Standard": 100,
    "Deluxe": 150,
    "Suite": 200
}

# Default availability per room type (number of rooms available)
ROOM_INVENTORY = {
    "Standard": 5,
    "Deluxe": 3,
    "Suite": 2
}

BOOKINGS_FILE = "bookings.json"


# ============================================================================
# Utility Functions
# ============================================================================

def get_bookings():
    """Read all bookings from JSON file."""
    if not os.path.exists(BOOKINGS_FILE):
        return []
    
    try:
        with open(BOOKINGS_FILE, 'r') as f:
            data = json.load(f)
            return data.get("bookings", [])
    except (json.JSONDecodeError, IOError):
        return []


def save_bookings(bookings):
    """Write bookings to JSON file."""
    with open(BOOKINGS_FILE, 'w') as f:
        json.dump({"bookings": bookings}, f, indent=2)


def generate_reference_number():
    """Generate unique booking reference number (e.g., REF-A1B2C3D4)."""
    return f"REF-{uuid.uuid4().hex[:8].upper()}"


def parse_date(date_str):
    """Parse date string (YYYY-MM-DD) to datetime object."""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def date_range(start_date, end_date):
    """Generate list of dates between start and end (inclusive of start, exclusive of end)."""
    current = start_date
    dates = []
    while current < end_date:
        dates.append(current)
        current += timedelta(days=1)
    return dates


def get_booked_rooms(check_in, check_out, room_type=None):
    """
    Get count of booked rooms for given date range and optionally room type.
    Args:
        check_in: datetime.date object
        check_out: datetime.date object
        room_type: optional room type name; if None, returns dict with all types
    Returns:
        int (if room_type specified) or dict with room type as key, booked count as value
    """
    bookings = get_bookings()
    booked = {} if room_type is None else 0
    
    # Initialize counts
    if room_type is None:
        for rtype in ROOM_TYPES.keys():
            booked[rtype] = 0
    
    # Check each booking
    for booking in bookings:
        booking_check_in = parse_date(booking.get("check_in"))
        booking_check_out = parse_date(booking.get("check_out"))
        booking_room_type = booking.get("room_type")
        booking_qty = booking.get("quantity", 1)
        
        if not booking_check_in or not booking_check_out:
            continue
        
        # Check for overlap: booking overlaps if check_in < booking_check_out AND check_out > booking_check_in
        if check_in < booking_check_out and check_out > booking_check_in:
            if room_type is None:
                booked[booking_room_type] = booked.get(booking_room_type, 0) + booking_qty
            elif room_type == booking_room_type:
                booked += booking_qty
    
    return booked


def get_available_rooms(check_in, check_out):
    """
    Get available room counts for each room type for the given date range.
    Returns dict: {"Standard": 5, "Deluxe": 3, "Suite": 2}
    """
    booked = get_booked_rooms(check_in, check_out)
    available = {}
    
    for room_type, inventory in ROOM_INVENTORY.items():
        booked_count = booked.get(room_type, 0)
        available[room_type] = inventory - booked_count
    
    return available


def calculate_total_cost(room_type, check_in, check_out, quantity=1):
    """Calculate total cost for a booking."""
    nights = (check_out - check_in).days
    if nights < 1:
        return 0
    price_per_night = ROOM_TYPES.get(room_type, 0)
    return price_per_night * nights * quantity


# ============================================================================
# Routes
# ============================================================================

@app.route("/")
def index():
    """Home page - show search form."""
    return render_template("search.html")


@app.route("/search", methods=["POST"])
def search():
    """
    Handle room search by date range.
    Expects: check_in (YYYY-MM-DD), check_out (YYYY-MM-DD)
    Returns: Rooms available for those dates
    """
    check_in_str = request.form.get("check_in", "").strip()
    check_out_str = request.form.get("check_out", "").strip()
    
    # Validate inputs
    check_in = parse_date(check_in_str)
    check_out = parse_date(check_out_str)
    
    if not check_in or not check_out:
        return render_template("search.html", error="Invalid date format. Use YYYY-MM-DD.")
    
    if check_out <= check_in:
        return render_template("search.html", error="Check-out date must be after check-in date.")
    
    # Get available rooms
    available = get_available_rooms(check_in, check_out)
    
    # Check if any rooms are available
    if all(count <= 0 for count in available.values()):
        return render_template("search.html", error="No rooms available for the selected dates.")
    
    # Pass data to room selection page
    nights = (check_out - check_in).days
    return render_template(
        "rooms.html",
        check_in=check_in_str,
        check_out=check_out_str,
        nights=nights,
        available=available,
        room_types=ROOM_TYPES
    )


@app.route("/booking", methods=["GET", "POST"])
def booking():
    """
    Show booking form or process booking.
    GET: Show form with prefilled dates/room type
    POST: Create booking and show confirmation
    """
    if request.method == "GET":
        check_in = request.args.get("check_in")
        check_out = request.args.get("check_out")
        room_type = request.args.get("room_type")
        quantity = request.args.get("quantity", 1, type=int)
        
        if not all([check_in, check_out, room_type]):
            return redirect(url_for("index"))
        
        check_in_date = parse_date(check_in)
        check_out_date = parse_date(check_out)
        
        if not check_in_date or not check_out_date:
            return redirect(url_for("index"))
        
        nights = (check_out_date - check_in_date).days
        price_per_night = ROOM_TYPES.get(room_type, 0)
        total_cost = calculate_total_cost(room_type, check_in_date, check_out_date, quantity)
        
        return render_template(
            "booking.html",
            check_in=check_in,
            check_out=check_out,
            room_type=room_type,
            quantity=quantity,
            nights=nights,
            price_per_night=price_per_night,
            total_cost=total_cost
        )
    
    # POST: Create booking
    guest_name = request.form.get("guest_name", "").strip()
    guest_email = request.form.get("guest_email", "").strip()
    check_in = request.form.get("check_in", "").strip()
    check_out = request.form.get("check_out", "").strip()
    room_type = request.form.get("room_type", "").strip()
    quantity = request.form.get("quantity", 1, type=int)
    
    # Validate inputs
    if not guest_name:
        return jsonify({"error": "Guest name is required"}), 400
    
    if not guest_email or "@" not in guest_email:
        return jsonify({"error": "Valid email is required"}), 400
    
    check_in_date = parse_date(check_in)
    check_out_date = parse_date(check_out)
    
    if not check_in_date or not check_out_date or check_out_date <= check_in_date:
        return jsonify({"error": "Invalid dates"}), 400
    
    if room_type not in ROOM_TYPES:
        return jsonify({"error": "Invalid room type"}), 400
    
    if quantity < 1:
        return jsonify({"error": "Quantity must be at least 1"}), 400
    
    # Check availability at time of booking
    available = get_available_rooms(check_in_date, check_out_date)
    if available.get(room_type, 0) < quantity:
        return jsonify({"error": "Not enough rooms available for selected dates"}), 400
    
    # Create booking
    reference = generate_reference_number()
    total_cost = calculate_total_cost(room_type, check_in_date, check_out_date, quantity)
    
    booking_record = {
        "reference": reference,
        "guest_name": guest_name,
        "guest_email": guest_email,
        "check_in": check_in,
        "check_out": check_out,
        "room_type": room_type,
        "quantity": quantity,
        "total_cost": total_cost,
        "created_at": datetime.now().isoformat()
    }
    
    bookings = get_bookings()
    bookings.append(booking_record)
    save_bookings(bookings)
    
    return redirect(url_for("confirmation", reference=reference))


@app.route("/confirmation/<reference>")
def confirmation(reference):
    """Show booking confirmation with reference number."""
    bookings = get_bookings()
    booking = next((b for b in bookings if b.get("reference") == reference), None)
    
    if not booking:
        return render_template("confirmation.html", error="Booking not found.")
    
    check_in_date = parse_date(booking["check_in"])
    check_out_date = parse_date(booking["check_out"])
    nights = (check_out_date - check_in_date).days if check_in_date and check_out_date else 0
    
    return render_template(
        "confirmation.html",
        booking=booking,
        nights=nights
    )


@app.route("/cancel", methods=["GET", "POST"])
def cancel():
    """
    Show cancellation form or process cancellation.
    GET: Show form to enter reference number
    POST: Cancel booking if reference exists
    """
    if request.method == "GET":
        return render_template("cancel.html")
    
    # POST: Process cancellation
    reference = request.form.get("reference", "").strip().upper()
    
    if not reference:
        return render_template("cancel.html", error="Please enter a reference number.")
    
    bookings = get_bookings()
    booking = next((b for b in bookings if b.get("reference") == reference), None)
    
    if not booking:
        return render_template("cancel.html", error=f"No booking found with reference {reference}.")
    
    # Remove booking
    bookings = [b for b in bookings if b.get("reference") != reference]
    save_bookings(bookings)
    
    return render_template(
        "cancel.html",
        success=True,
        reference=reference,
        guest_name=booking.get("guest_name")
    )


# ============================================================================
# Error Handlers
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return render_template("search.html", error="Page not found."), 404


@app.errorhandler(500)
def server_error(error):
    """Handle 500 errors."""
    return render_template("search.html", error="A server error occurred. Please try again."), 500


# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
