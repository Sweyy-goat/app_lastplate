from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from utils.db import mysql
import MySQLdb.cursors
from app import limiter

reserve_seat_bp = Blueprint("reserve_seat", __name__)

# ================= API =================
@reserve_seat_bp.route("/api/reserve-seat", methods=["POST"])
@limiter.limit("5 per minute")
@jwt_required() # Ensure only logged-in users from the app can reserve
def reserve():
    try:
        data = request.json

        if not data:
            return jsonify({"error": "No data received"}), 400

        # Extract fields from the Flutter payload
        restaurant_id = data.get("restaurant_id") # ✅ Fixed: Now dynamic
        name = data.get("name")
        email = data.get("email")
        phone = data.get("phone")
        date = data.get("date")
        time = data.get("time")
        guests = data.get("guests")
        occasion = data.get("occasion")
        notes = data.get("notes")

        # Validation
        if not all([restaurant_id, name, email, phone, date, time, guests]):
            return jsonify({"error": "Missing required fields"}), 400

        # Optional: You can also extract the logged-in user's ID if you want 
        # to add a `user_id` column to your reservations table later!
        # current_user = get_jwt_identity()
        # user_id = current_user["id"]

        # DB insert
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

        cur.execute("""
            INSERT INTO reservations
            (restaurant_id, name, email, phone, reservation_date, reservation_time, guests, occasion, notes)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            int(restaurant_id),
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

        return jsonify({"success": True, "message": "Table reserved successfully!"}), 201

    except Exception as e:
        print("RESERVATION ERROR:", e)  # shows in Railway logs
        return jsonify({"error": "Server error while processing reservation"}), 500
