from flask import Blueprint, render_template, request, jsonify
from utils.db import mysql
import MySQLdb.cursors
from app import limiter

reserve_seat_bp = Blueprint("reserve_seat", __name__)

# ================= PAGE =================
@reserve_seat_bp.route("/reserve-seat", strict_slashes=False)
def reserve_page():
    return render_template("restaurant/reserve_seat.html")


# ================= API =================
@reserve_seat_bp.route("/api/reserve-seat", methods=["POST"])
@limiter.limit("5 per minute")
def reserve():
    try:
        # 🔥 Use SAME pattern as your working order.py
        data = request.json

        if not data:
            return jsonify({"error": "No data received"}), 400

        # Extract fields
        name = data.get("name")
        email = data.get("email")
        phone = data.get("phone")
        date = data.get("date")
        time = data.get("time")
        guests = data.get("guests")
        occasion = data.get("occasion")
        notes = data.get("notes")

        # Validation
        if not all([name, email, phone, date, time, guests]):
            return jsonify({"error": "Missing fields"}), 400

        # DB insert
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

        cur.execute("""
            INSERT INTO reservations
            (restaurant_id, name, email, phone, reservation_date, reservation_time, guests, occasion, notes)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            6,  # TEMP HARDCODE (replace later)
            name,
            email,
            phone,
            date,
            time,
            int(guests),
            occasion,
            notes
        ))

        mysql.connection.commit()

        return jsonify({"success": True})

    except Exception as e:
        print("RESERVATION ERROR:", e)  # shows in Railway logs
        return jsonify({"error": "Server error"}), 500
