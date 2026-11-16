import os
import uuid
from functools import wraps
import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or os.urandom(32)

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "database": os.environ.get("DB_NAME", "public_transport_db"),
    "user": os.environ.get("DB_USER", "postgres"),
    "password": os.environ.get("DB_PASSWORD", ""),
    "port": os.environ.get("DB_PORT", "5432"),
}

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")


# DATABASE CONNECTION

def db():
    return psycopg2.connect(**DB_CONFIG)


def query_all(sql, params=()):
    conn = db()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            return cur.fetchall()
    finally:
        conn.close()


def query_one(sql, params=()):
    rows = query_all(sql, params)
    return rows[0] if rows else None


def execute(sql, params=()):
    conn = db()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
    finally:
        conn.close()


# INITIAL DATABASE SETUP

def init_schema():

    execute("""
        ALTER TABLE buses
        ADD COLUMN IF NOT EXISTS owner_name VARCHAR(100)
    """)

    execute("""
        ALTER TABLE passengers
        ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255)
    """)

    execute("""
        ALTER TABLE schedules
        ADD COLUMN IF NOT EXISTS available_seats INTEGER
    """)

    execute("""
        CREATE TABLE IF NOT EXISTS admins (
            admin_id SERIAL PRIMARY KEY,
            username VARCHAR(80) UNIQUE NOT NULL,
            password_text VARCHAR(200) NOT NULL
        )
    """)

    
    execute("""
        CREATE TABLE IF NOT EXISTS payments (
            payment_id SERIAL PRIMARY KEY,
            booking_id INTEGER UNIQUE NOT NULL
                REFERENCES bookings(booking_id),
            passenger_id INTEGER NOT NULL
                REFERENCES passengers(passenger_id),
            amount NUMERIC(10,2) NOT NULL,
            payment_method VARCHAR(30) NOT NULL,
            payment_status VARCHAR(40) NOT NULL,
            transaction_ref VARCHAR(100) UNIQUE NOT NULL,
            paid_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Initialize available seats for existing schedules.
    execute("""
        UPDATE schedules s
        SET available_seats = GREATEST(
            b.total_seats - COALESCE((
                SELECT SUM(bk.seats_booked)
                FROM bookings bk
                WHERE bk.schedule_id = s.schedule_id
                  AND bk.status = 'Confirmed'
            ), 0), 0
        )
        FROM buses b
        WHERE s.bus_id = b.bus_id
          AND s.available_seats IS NULL
    """)

    existing = query_one(
        "SELECT admin_id FROM admins WHERE username=%s",
        (ADMIN_USERNAME,)
    )

    if not existing:
        execute(
            "INSERT INTO admins (username, password_text) VALUES (%s,%s)",
            (ADMIN_USERNAME, ADMIN_PASSWORD)
        )


# LOGIN PROTECTION

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            flash("Please log in as administrator.", "warning")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper


def passenger_login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("passenger_id"):
            flash("Please login as passenger.", "warning")
            return redirect(url_for("passenger_login"))
        return fn(*args, **kwargs)
    return wrapper


# COMMON BOOKING FUNCTION

def create_booking(passenger_id, schedule_id, seats):

    if seats < 1:
        raise ValueError("Enter a valid number of seats.")

    conn = db()

    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT available_seats
                    FROM schedules
                    WHERE schedule_id = %s
                    FOR UPDATE
                """, (schedule_id,))

                row = cur.fetchone()

                if not row:
                    raise ValueError("Schedule not found.")

                available = row[0]

                if available is None or seats > available:
                    raise ValueError("Not enough available seats.")

                cur.execute("""
                    INSERT INTO bookings
                    (passenger_id, schedule_id, seats_booked, status)
                    VALUES (%s, %s, %s, 'Confirmed')
                    RETURNING booking_id
                """, (passenger_id, schedule_id, seats))

                booking_id = cur.fetchone()[0]

                cur.execute("""
                    UPDATE schedules
                    SET available_seats = available_seats - %s
                    WHERE schedule_id = %s
                """, (seats, schedule_id))

        return booking_id, available - seats

    finally:
        conn.close()


# DEMO PAYMENT AND BOOKING

def create_paid_booking(passenger_id, schedule_id, seats, payment_method):

    if seats < 1:
        raise ValueError("Invalid seat count.")

    if payment_method not in [
        "UPI Demo", "Card Demo", "Net Banking Demo"
    ]:
        raise ValueError("Invalid payment method.")

    conn = db()

    try:
        with conn:
            with conn.cursor() as cur:

                cur.execute("""
                    SELECT s.available_seats, r.distance_km
                    FROM schedules s
                    JOIN routes r ON s.route_id = r.route_id
                    WHERE s.schedule_id = %s
                    FOR UPDATE OF s
                """, (schedule_id,))

                row = cur.fetchone()

                if not row:
                    raise ValueError("Schedule not found.")

                available, distance = row

                if available is None or seats > available:
                    raise ValueError("Not enough available seats.")

                amount = round(float(distance) * 2 * seats, 2)

                cur.execute("""
                    INSERT INTO bookings
                    (passenger_id, schedule_id, seats_booked, status)
                    VALUES (%s, %s, %s, 'Confirmed')
                    RETURNING booking_id
                """, (passenger_id, schedule_id, seats))

                booking_id = cur.fetchone()[0]

                cur.execute("""
                    UPDATE schedules
                    SET available_seats = available_seats - %s
                    WHERE schedule_id = %s
                """, (seats, schedule_id))

                transaction_ref = (
                    "DEMO-" + uuid.uuid4().hex[:12].upper()
                )

                cur.execute("""
                    INSERT INTO payments
                    (booking_id, passenger_id, amount,
                     payment_method, payment_status, transaction_ref)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    booking_id,
                    passenger_id,
                    amount,
                    payment_method,
                    "Paid (Demo)",
                    transaction_ref
                ))

        return booking_id, available - seats, amount, transaction_ref

    finally:
        conn.close()


# HOME PAGE


@app.route("/")
def home():

    counts = query_one("""
        SELECT
            (SELECT COUNT(*) FROM buses) AS buses,
            (SELECT COUNT(*) FROM routes) AS routes,
            (SELECT COUNT(*) FROM schedules) AS schedules,
            (SELECT COUNT(*) FROM bookings) AS bookings,
            (SELECT COUNT(*) FROM passengers) AS passengers
    """)

    return render_template(
        "index.html",
        counts=counts
    )

# ADMIN LOGIN

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        admin = query_one("""
            SELECT admin_id
            FROM admins
            WHERE username = %s AND password_text = %s
        """, (username, password))

        if admin:
            session.clear()
            session["admin"] = username
            flash("Admin login successful.", "success")
            return redirect(url_for("home"))

        flash("Invalid username or password.", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("home"))


# BUS MANAGEMENT

@app.route("/buses")
def buses():

    rows = query_all("""
        SELECT bus_id, bus_number, bus_name, owner_name, total_seats
        FROM buses
        ORDER BY bus_id
    """)

    return render_template("buses.html", buses=rows)


@app.route("/buses/add", methods=["POST"])
@login_required
def add_bus():

    execute("""
        INSERT INTO buses
        (bus_number, bus_name, total_seats, owner_name)
        VALUES (%s, %s, %s, %s)
    """, (
        request.form["bus_number"],
        request.form["bus_name"],
        int(request.form["total_seats"]),
        request.form.get("owner_name") or None
    ))

    flash("Bus added.", "success")
    return redirect(url_for("buses"))


@app.route("/buses/delete/<int:item_id>", methods=["POST"])
@login_required
def delete_bus(item_id):

    try:
        execute("DELETE FROM buses WHERE bus_id=%s", (item_id,))
        flash("Bus deleted.", "success")
    except Exception:
        flash(
            "This bus is linked to a schedule. Remove or change that schedule first.",
            "warning"
        )

    return redirect(url_for("buses"))


# ROUTE MANAGEMENT

@app.route("/routes")
def routes():

    rows = query_all("""
        SELECT route_id, source, destination, distance_km
        FROM routes
        ORDER BY route_id
    """)

    return render_template("routes.html", routes=rows)


@app.route("/routes/add", methods=["POST"])
@login_required
def add_route():

    execute("""
        INSERT INTO routes (source, destination, distance_km)
        VALUES (%s, %s, %s)
    """, (
        request.form["source"],
        request.form["destination"],
        float(request.form["distance_km"])
    ))

    flash("Route added.", "success")
    return redirect(url_for("routes"))


@app.route("/routes/delete/<int:item_id>", methods=["POST"])
@login_required
def delete_route(item_id):

    try:
        execute("DELETE FROM routes WHERE route_id=%s", (item_id,))
        flash("Route deleted.", "success")
    except Exception:
        flash(
            "This route is linked to a schedule. Remove or change that schedule first.",
            "warning"
        )

    return redirect(url_for("routes"))


# SCHEDULE MANAGEMENT

@app.route("/schedules")
def schedules():

    rows = query_all("""
        SELECT s.schedule_id, b.bus_number,
               r.source, r.destination,
               s.departure_time, s.arrival_time,
               s.travel_date, s.available_seats
        FROM schedules s
        JOIN buses b ON s.bus_id = b.bus_id
        JOIN routes r ON s.route_id = r.route_id
        ORDER BY s.travel_date, s.departure_time
    """)

    bus_list = query_all("""
        SELECT bus_id, bus_number
        FROM buses
        ORDER BY bus_number
    """)

    route_list = query_all("""
        SELECT route_id, source, destination
        FROM routes
        ORDER BY route_id
    """)

    return render_template(
        "schedules.html",
        schedules=rows,
        buses=bus_list,
        routes=route_list
    )


@app.route("/schedules/add", methods=["POST"])
@login_required
def add_schedule():

    bus_id = int(request.form["bus_id"])

    conn = db()

    try:
        with conn:
            with conn.cursor() as cur:

                cur.execute("""
                    INSERT INTO schedules
                    (bus_id, route_id, departure_time,
                     arrival_time, travel_date, available_seats)
                    SELECT bus_id, %s, %s, %s, %s, total_seats
                    FROM buses
                    WHERE bus_id = %s
                """, (
                    int(request.form["route_id"]),
                    request.form["departure_time"],
                    request.form["arrival_time"],
                    request.form["travel_date"],
                    bus_id
                ))

                if cur.rowcount == 0:
                    raise ValueError("Bus not found.")

        flash("Schedule added.", "success")

    except Exception as e:
        flash("Schedule could not be added: " + str(e), "danger")

    finally:
        conn.close()

    return redirect(url_for("schedules"))


@app.route("/schedules/delete/<int:item_id>", methods=["POST"])
@login_required
def delete_schedule(item_id):

    try:
        execute(
            "DELETE FROM schedules WHERE schedule_id=%s",
            (item_id,)
        )
        flash("Schedule deleted.", "success")

    except Exception:
        flash(
            "This schedule has bookings and cannot be deleted.",
            "warning"
        )

    return redirect(url_for("schedules"))


# PASSENGER MANAGEMENT - ADMIN

@app.route("/passengers")
@login_required
def passengers():

    rows = query_all("""
        SELECT passenger_id, passenger_name, phone
        FROM passengers
        ORDER BY passenger_id
    """)

    return render_template("passengers.html", passengers=rows)


@app.route("/passengers/add", methods=["POST"])
@login_required
def add_passenger():

    execute("""
        INSERT INTO passengers (passenger_name, phone)
        VALUES (%s, %s)
    """, (
        request.form["passenger_name"],
        request.form.get("phone", "")
    ))

    flash("Passenger added.", "success")
    return redirect(url_for("passengers"))


@app.route("/passengers/delete/<int:item_id>", methods=["POST"])
@login_required
def delete_passenger(item_id):

    try:
        execute(
            "DELETE FROM passengers WHERE passenger_id=%s",
            (item_id,)
        )
        flash("Passenger deleted.", "success")

    except Exception:
        flash(
            "This passenger has bookings and cannot be deleted.",
            "warning"
        )

    return redirect(url_for("passengers"))


# ADMIN BOOKING MANAGEMENT

@app.route("/bookings")
@login_required
def bookings():

    rows = query_all("""
        SELECT bk.booking_id, p.passenger_name, b.bus_number,
               r.source, r.destination, bk.seats_booked,
               bk.booking_date, bk.status
        FROM bookings bk
        JOIN passengers p ON bk.passenger_id = p.passenger_id
        JOIN schedules s ON bk.schedule_id = s.schedule_id
        JOIN buses b ON s.bus_id = b.bus_id
        JOIN routes r ON s.route_id = r.route_id
        ORDER BY bk.booking_id ASC
    """)

    passenger_list = query_all("""
        SELECT passenger_id, passenger_name
        FROM passengers
        ORDER BY passenger_name
    """)

    schedule_list = query_all("""
        SELECT s.schedule_id, b.bus_number,
               r.source, r.destination, s.travel_date,
               s.available_seats
        FROM schedules s
        JOIN buses b ON s.bus_id = b.bus_id
        JOIN routes r ON s.route_id = r.route_id
        ORDER BY s.travel_date
    """)

    return render_template(
        "bookings.html",
        bookings=rows,
        passengers=passenger_list,
        schedules=schedule_list
    )


@app.route("/bookings/add", methods=["POST"])
@login_required
def add_booking():

    try:
        booking_id, remaining = create_booking(
            int(request.form["passenger_id"]),
            int(request.form["schedule_id"]),
            int(request.form["seats_booked"])
        )

        flash(
            "Booking created. Booking ID: " + str(booking_id) +
            ". Remaining seats: " + str(remaining),
            "success"
        )

    except Exception as e:
        flash("Booking failed: " + str(e), "warning")

    return redirect(url_for("bookings"))


@app.route("/bookings/cancel/<int:item_id>", methods=["POST"])
@login_required
def cancel_admin_booking(item_id):

    try:
        seats = cancel_booking_transaction(item_id)

        flash(
            "Booking cancelled. Seats restored: " + str(seats),
            "success"
        )

    except Exception as e:
        flash("Cancellation failed: " + str(e), "warning")

    return redirect(url_for("bookings"))


# DATA ANALYSIS

@app.route("/analysis")
@login_required
def analysis():

    data = query_all("""
        SELECT r.source, r.destination,
               COUNT(bk.booking_id) AS bookings,
               COALESCE(SUM(bk.seats_booked), 0) AS seats_booked
        FROM routes r
        LEFT JOIN schedules s ON s.route_id = r.route_id
        LEFT JOIN bookings bk
          ON bk.schedule_id = s.schedule_id
         AND bk.status = 'Confirmed'
        GROUP BY r.route_id, r.source, r.destination
        ORDER BY bookings DESC, r.source
    """)

    total_seats = sum(int(row["seats_booked"]) for row in data)
    busiest = data[0] if data else None

    df = pd.DataFrame([dict(x) for x in data])

    route_count = len(df)
    average = (
        round(float(df["bookings"].mean()), 2)
        if not df.empty else 0
    )

    return render_template(
        "analysis.html",
        data=data,
        total_seats=total_seats,
        busiest=busiest,
        route_count=route_count,
        average=average
    )


# PASSENGER REGISTRATION

@app.route("/passenger/register", methods=["GET", "POST"])
def passenger_register():

    if request.method == "POST":

        name = request.form.get("passenger_name", "").strip()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")

        if not name or not phone or len(password) < 8:
            flash(
                "Enter all details. Password must be at least 8 characters.",
                "warning"
            )
            return redirect(url_for("passenger_register"))

        existing = query_one(
            "SELECT passenger_id FROM passengers WHERE phone=%s",
            (phone,)
        )

        if existing:
            flash("Phone number already registered.", "warning")
            return redirect(url_for("passenger_register"))

        password_hash = generate_password_hash(password)

        execute("""
            INSERT INTO passengers
            (passenger_name, phone, password_hash)
            VALUES (%s, %s, %s)
        """, (name, phone, password_hash))

        flash("Registration successful. Please login.", "success")
        return redirect(url_for("passenger_login"))

    return render_template("passenger_register.html")


# PASSENGER LOGIN

@app.route("/passenger/login", methods=["GET", "POST"])
def passenger_login():

    if request.method == "POST":

        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")

        passenger = query_one("""
            SELECT passenger_id, passenger_name, password_hash
            FROM passengers
            WHERE phone = %s
        """, (phone,))

        if passenger and passenger["password_hash"] and check_password_hash(
            passenger["password_hash"], password
        ):

            session.clear()
            session["passenger_id"] = passenger["passenger_id"]
            session["passenger_name"] = passenger["passenger_name"]

            return redirect(url_for("passenger_dashboard"))

        flash("Invalid phone number or password.", "danger")

    return render_template("passenger_login.html")


# PASSENGER DASHBOARD

@app.route("/passenger/dashboard")
@passenger_login_required
def passenger_dashboard():

    passenger_id = session["passenger_id"]

    rows = query_all("""
        SELECT bk.booking_id, b.bus_number,
               r.source, r.destination,
               s.travel_date, s.departure_time,
               bk.seats_booked, bk.status
        FROM bookings bk
        JOIN schedules s ON bk.schedule_id = s.schedule_id
        JOIN buses b ON s.bus_id = b.bus_id
        JOIN routes r ON s.route_id = r.route_id
        WHERE bk.passenger_id = %s
        ORDER BY bk.booking_date DESC
    """, (passenger_id,))

    return render_template(
        "passenger_dashboard.html",
        bookings=rows
    )


# PASSENGER SEARCH

@app.route("/passenger/search", methods=["GET", "POST"])
@passenger_login_required
def passenger_search():

    results = []

    if request.method == "POST":

        source = request.form.get("source", "").strip()
        destination = request.form.get("destination", "").strip()
        travel_date = request.form.get("travel_date", "")

        results = query_all("""
            SELECT s.schedule_id, b.bus_number, b.bus_name,
                   r.source, r.destination, r.distance_km,
                   s.departure_time, s.arrival_time,
                   s.travel_date, s.available_seats
            FROM schedules s
            JOIN buses b ON s.bus_id = b.bus_id
            JOIN routes r ON s.route_id = r.route_id
            WHERE LOWER(r.source) = LOWER(%s)
              AND LOWER(r.destination) = LOWER(%s)
              AND s.travel_date = %s
              AND s.travel_date >= CURRENT_DATE
            ORDER BY s.departure_time
        """, (source, destination, travel_date))

    return render_template(
        "passenger_search.html",
        results=results
    )
@app.route("/passenger/payment", methods=["GET", "POST"])
@passenger_login_required
def passenger_payment():

    pending = session.get("pending_booking")

    if not pending or pending["passenger_id"] != session["passenger_id"]:
        flash("Please select a bus first.", "warning")
        return redirect(url_for("passenger_search"))

    schedule = query_one("""
        SELECT s.schedule_id, s.travel_date,
               s.departure_time, s.available_seats,
               b.bus_number, r.source, r.destination,
               r.distance_km
        FROM schedules s
        JOIN buses b ON s.bus_id = b.bus_id
        JOIN routes r ON s.route_id = r.route_id
        WHERE s.schedule_id = %s
    """, (pending["schedule_id"],))

    if not schedule:
        session.pop("pending_booking", None)
        flash("Schedule not found.", "danger")
        return redirect(url_for("passenger_search"))

    seats = pending["seats"]
    amount = round(float(schedule["distance_km"]) * 2 * seats, 2)

    if request.method == "POST":

        action = request.form.get("action")

        if action == "fail":
            session.pop("pending_booking", None)
            flash("Demo payment failed. No booking was created.", "danger")
            return redirect(url_for("passenger_search"))

        payment_method = request.form.get("payment_method")

        try:
            booking_id, remaining, paid_amount, transaction_ref = (
                create_paid_booking(
                    session["passenger_id"],
                    pending["schedule_id"],
                    seats,
                    payment_method
                )
            )

            session.pop("pending_booking", None)

            flash(
                "Demo payment successful! Booking ID: " +
                str(booking_id) +
                ". Transaction: " + transaction_ref +
                ". Remaining seats: " + str(remaining),
                "success"
            )

            return redirect(url_for("passenger_bookings"))

        except Exception as e:
            flash("Payment/booking failed: " + str(e), "danger")
            return redirect(url_for("passenger_payment"))

    return render_template(
        "payment.html",
        schedule=schedule,
        seats=seats,
        amount=amount
    )

# PASSENGER BOOKING

@app.route("/passenger/book/<int:schedule_id>", methods=["POST"])
@passenger_login_required
def passenger_book(schedule_id):

    seats = request.form.get("seats", type=int)

    if not seats or seats < 1:
        flash("Enter valid seats.", "warning")
        return redirect(url_for("passenger_search"))

    schedule = query_one("""
        SELECT schedule_id, available_seats
        FROM schedules
        WHERE schedule_id = %s
    """, (schedule_id,))

    if not schedule:
        flash("Schedule not found.", "danger")
        return redirect(url_for("passenger_search"))

    if schedule["available_seats"] is None or seats > schedule["available_seats"]:
        flash("Not enough seats available.", "warning")
        return redirect(url_for("passenger_search"))

    session["pending_booking"] = {
        "passenger_id": session["passenger_id"],
        "schedule_id": schedule_id,
        "seats": seats
    }

    return redirect(url_for("passenger_payment"))

# PASSENGER BOOKING CANCELLATION

@app.route("/passenger/cancel/<int:booking_id>", methods=["POST"])
@passenger_login_required
def passenger_cancel(booking_id):

    booking = query_one("""
        SELECT booking_id
        FROM bookings
        WHERE booking_id = %s
          AND passenger_id = %s
    """, (booking_id, session["passenger_id"]))

    if not booking:
        flash("Booking not found.", "danger")
        return redirect(url_for("passenger_bookings"))

    try:
        cancel_booking_transaction(booking_id)
        flash("Booking cancelled successfully.", "success")

    except ValueError as e:
        flash(str(e), "warning")

    except Exception:
        flash("Unable to cancel booking.", "danger")

    return redirect(url_for("passenger_bookings"))



# PASSENGER BOOKINGS

@app.route("/passenger/bookings")
@passenger_login_required
def passenger_bookings():

    rows = query_all("""
        SELECT bk.booking_id, b.bus_number,
               r.source, r.destination, s.travel_date,
               s.departure_time, bk.seats_booked, bk.status
        FROM bookings bk
        JOIN schedules s ON bk.schedule_id = s.schedule_id
        JOIN buses b ON s.bus_id = b.bus_id
        JOIN routes r ON s.route_id = r.route_id
        WHERE bk.passenger_id = %s
        ORDER BY bk.booking_id DESC
    """, (session["passenger_id"],))

    return render_template(
        "passenger_bookings.html",
        bookings=rows
    )
# COMMON CANCELLATION FUNCTION

def cancel_booking_transaction(booking_id):

    conn = db()

    try:
        with conn:
            with conn.cursor() as cur:

                cur.execute("""
                    SELECT schedule_id, seats_booked, status
                    FROM bookings
                    WHERE booking_id = %s
                    FOR UPDATE
                """, (booking_id,))

                booking = cur.fetchone()

                if not booking:
                    raise ValueError("Booking not found.")

                schedule_id, seats, status = booking

                if status != "Confirmed":
                    raise ValueError("Booking is already cancelled.")

                cur.execute("""
                    UPDATE bookings
                    SET status = 'Cancelled'
                    WHERE booking_id = %s
                """, (booking_id,))

                cur.execute("""
                    UPDATE schedules
                    SET available_seats = available_seats + %s
                    WHERE schedule_id = %s
                """, (seats, schedule_id))

                return seats

    finally:
        conn.close()

# PASSENGER LOGOUT

@app.route("/passenger/logout")
def passenger_logout():

    session.pop("passenger_id", None)
    session.pop("passenger_name", None)

    flash("Passenger logged out.", "success")
    return redirect(url_for("passenger_login"))


# ERROR PAGE

@app.errorhandler(404)
def not_found(_):

    return render_template(
        "error.html",
        message="The page you requested was not found."
    ), 404


# START APPLICATION

if __name__ == "__main__":

    try:
        init_schema()
        print("Database ready.")
        print("Open http://127.0.0.1:5000")

    except Exception as exc:
        print("Database setup error:", exc)
        print("Check DB_PASSWORD in app.py.")

    app.run(debug=True)
