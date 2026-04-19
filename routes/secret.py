from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from utils.db import mysql
from MySQLdb.cursors import DictCursor
import math, os, time
import razorpay
from utils.emailer import send_email

secret_bp = Blueprint("secret", __name__)

razorpay_client = razorpay.Client(auth=(
    os.getenv("RAZORPAY_KEY_ID"),
    os.getenv("RAZORPAY_KEY_SECRET")
))

# ============================================================
# 1️⃣ RESTAURANTS WITH SECRET MENU TODAY
# ============================================================
@secret_bp.route("/api/secret-menu/restaurants", methods=["GET"])
@jwt_required() # Optional: remove if you want guests to see the list
def secret_restaurants():
    cur = mysql.connection.cursor(DictCursor)

    cur.execute("""
        SELECT 
            r.id AS restaurant_id,
            r.name AS restaurant_name,
            r.address,
            COUNT(sm.id) AS dish_count,
            MIN(sm.price) AS min_price,
            MAX(sm.price) AS max_price
        FROM secret_menu sm
        JOIN restaurants r ON r.id = sm.restaurant_id
        WHERE sm.stock > 0 AND sm.is_today_special = 1
        GROUP BY r.id
        ORDER BY r.name ASC
    """)

    items = cur.fetchall()
    return jsonify({"success": True, "restaurants": items}), 200


# ============================================================
# 2️⃣ SECRET DISHES OF A RESTAURANT
# ============================================================
@secret_bp.route("/api/secret-menu/<int:rid>", methods=["GET"])
@jwt_required()
def secret_menu_by_restaurant(rid):
    cur = mysql.connection.cursor(DictCursor)

    cur.execute("""
        SELECT 
            sm.id,
            sm.name,
            sm.cuisine,
            sm.description,
            sm.price,
            sm.mrp,
            sm.stock,
            sm.img,
            r.name AS restaurant_name
        FROM secret_menu sm
        JOIN restaurants r ON r.id = sm.restaurant_id
        WHERE sm.restaurant_id = %s
          AND sm.stock > 0
          AND sm.is_today_special = 1
        ORDER BY sm.id DESC
    """, (rid,))

    dishes = cur.fetchall()
    return jsonify({"success": True, "dishes": dishes}), 200


# ============================================================
# 3️⃣ GET SECRET CHECKOUT DETAILS
# ============================================================
# Changed from a web page render to a JSON data endpoint
@secret_bp.route("/api/secret/checkout/<int:dish_id>", methods=["GET"])
@jwt_required()
def secret_checkout(dish_id):
    cur = mysql.connection.cursor(DictCursor)

    cur.execute("""
        SELECT sm.id, sm.name, sm.price, sm.stock, r.name AS restaurant_name
        FROM secret_menu sm
        JOIN restaurants r ON r.id = sm.restaurant_id
        WHERE sm.id=%s AND sm.stock > 0
    """, (dish_id,))

    dish = cur.fetchone()

    if not dish:
        return jsonify({"error": "Dish not available or out of stock"}), 404

    return jsonify({"success": True, "dish": dish}), 200


# ============================================================
# 4️⃣ CREATE SECRET ORDER
# ============================================================
@secret_bp.route("/api/secret/create-order", methods=["POST"])
@jwt_required()
def create_secret_order():
    current_user = get_jwt_identity()
    user_id = current_user["id"]

    data = request.json
    dish_id = int(data.get("dish_id"))
    qty = int(data.get("quantity", 1))
    user_phone = data.get("phone")

    if not dish_id or not user_phone:
        return jsonify({"error": "Missing required fields"}), 400

    cur = mysql.connection.cursor(DictCursor)

    # Get user's email from DB
    cur.execute("SELECT email FROM users WHERE id=%s", (user_id,))
    u = cur.fetchone()
    if not u:
        return jsonify({"error": "User record not found"}), 404
    user_email = u["email"]

    # Fetch dish info
    cur.execute("""
        SELECT price, restaurant_id, stock
        FROM secret_menu
        WHERE id=%s
        FOR UPDATE
    """, (dish_id,))
    dish = cur.fetchone()

    if not dish or dish["stock"] < qty:
        return jsonify({"error": "Insufficient stock"}), 400

    # Price with 18% service/markup
    base_price = float(dish["price"])
    final_unit_price = math.ceil(base_price * 1.18)
    amount_paise = int(final_unit_price * qty * 100)

    # Razorpay order
    rp_order = razorpay_client.order.create({
        "amount": amount_paise,
        "currency": "INR",
        "payment_capture": 1
    })

    # Insert pending order
    cur.execute("""
        INSERT INTO secret_orders
        (user_id, dish_id, restaurant_id, quantity,
         user_phone, user_email, total_amount,
         status, payment_status, razorpay_order_id)
        VALUES (%s,%s,%s,%s,%s,%s,%s,'PENDING','PENDING',%s)
    """, (
        user_id, dish_id, dish["restaurant_id"], qty,
        user_phone, user_email,
        final_unit_price * qty,
        rp_order["id"]
    ))

    mysql.connection.commit()

    return jsonify({
        "success": True,
        "razorpay_order_id": rp_order["id"],
        "amount": amount_paise,
        "key": os.getenv("RAZORPAY_KEY_ID")
    }), 200


# ============================================================
# 5️⃣ VERIFY SECRET PAYMENT
# ============================================================
@secret_bp.route("/api/secret/verify-payment", methods=["POST"])
@jwt_required()
def secret_verify_payment():
    data = request.json
    cur = mysql.connection.cursor(DictCursor)

    required_keys = ["razorpay_order_id", "razorpay_payment_id", "razorpay_signature"]
    if not all(k in data for k in required_keys):
        return jsonify({"success": False, "error": "Missing signature data"}), 400

    try:
        razorpay_client.utility.verify_payment_signature({
            'razorpay_order_id': data['razorpay_order_id'],
            'razorpay_payment_id': data['razorpay_payment_id'],
            'razorpay_signature': data['razorpay_signature']
        })
    except razorpay.errors.SignatureVerificationError:
        return jsonify({"success": False, "error": "Invalid signature"}), 400

    # Fetch order data
    cur.execute("""
        SELECT so.*, sm.name AS dish_name, sm.price AS base_price,
               r.name AS restaurant_name, r.email AS res_email,
               r.location_link AS res_location
        FROM secret_orders so
        JOIN secret_menu sm ON so.dish_id = sm.id
        JOIN restaurants r ON sm.restaurant_id = r.id
        WHERE so.razorpay_order_id=%s
          AND so.payment_status='PENDING'
        FOR UPDATE
    """, (data["razorpay_order_id"],))

    order = cur.fetchone()

    if not order:
        return jsonify({"success": False, "error": "Order not found or already paid"}), 400

    qty = order["quantity"]

    # Reduce stock
    cur.execute("""
        UPDATE secret_menu
        SET stock = stock - %s
        WHERE id=%s AND stock >= %s
    """, (qty, order["dish_id"], qty))

    if cur.rowcount == 0:
        mysql.connection.rollback()
        return jsonify({"success": False, "error": "Out of stock during checkout"}), 409

    cur.execute("""
        UPDATE secret_orders
        SET payment_status='PAID',
            status='CONFIRMED',
            razorpay_payment_id=%s
        WHERE id=%s
    """, (data["razorpay_payment_id"], order["id"]))

    mysql.connection.commit()

    collected = float(order["total_amount"])
    restaurant_payout = float(order["base_price"]) * qty

    # --- EMAILS ---
    # To keep your API fast for mobile users, consider moving these emails 
    # to a background task (like Celery) in the future.
    restaurant_email = order["res_email"] or "terminalplate@gmail.com"

    send_email(restaurant_email, f"Secret Menu Order: {order['dish_name']}", f"...html omitted for brevity...")
    time.sleep(0.5)
    
    send_email(order["user_email"], "Your Secret Menu Order is Confirmed", f"...html omitted for brevity...")
    time.sleep(0.5)
    
    send_email("terminalplate@gmail.com", f"Secret Order Report: {order['dish_name']}", f"...html omitted for brevity...")

    return jsonify({"success": True}), 200
