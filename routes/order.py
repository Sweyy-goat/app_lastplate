from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from utils.db import mysql
import MySQLdb.cursors
import math
import razorpay, os, random
import time
from utils.emailer import send_email
from app import limiter

order_bp = Blueprint("order", __name__)

razorpay_client = razorpay.Client(auth=(
    os.getenv("RAZORPAY_KEY_ID"),
    os.getenv("RAZORPAY_KEY_SECRET")
))

# ================= CHECKOUT DETAILS API =================
# Flutter calls this to get the data needed to draw the Checkout UI
@order_bp.route("/api/checkout/<int:food_id>", methods=["GET"])
@jwt_required()
def get_checkout_details(food_id):
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("""
        SELECT f.id, f.name, f.price, f.available_quantity,
               r.name AS restaurant_name
        FROM foods f
        JOIN restaurants r ON f.restaurant_id = r.id
        WHERE f.id=%s AND f.is_active=1
    """, (food_id,))
    food = cur.fetchone()

    if not food or food["available_quantity"] <= 0:
        return jsonify({"error": "Food unavailable or out of stock"}), 404

    return jsonify(food), 200


# ================= CREATE ORDER API =================
@order_bp.route("/api/create-order", methods=["POST"])
@limiter.limit("10 per minute")
@jwt_required()
def create_order():
    # Extract user ID from JWT token instead of session
    current_user = get_jwt_identity()
    user_id = current_user["id"]

    data = request.json
    food_id = int(data.get("food_id"))
    quantity = int(data.get("quantity", 1))
    email = data.get("email")

    if not food_id or not email:
        return jsonify({"error": "Missing required fields"}), 400

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    # Check stock and get price
    cur.execute("SELECT price, restaurant_id, available_quantity FROM foods WHERE id=%s FOR UPDATE", (food_id,))
    food = cur.fetchone()

    if not food or food["available_quantity"] < quantity:
        return jsonify({"error": "Insufficient stock"}), 400

    # 2. MARKUP CALCULATION (Price + 15%)
    base_price = float(food["price"])
    platform_unit_price = math.ceil(base_price * 1.15) 
    total_amount_paise = int(platform_unit_price * quantity * 100)

    # Create Razorpay Order
    razorpay_order = razorpay_client.order.create({
        "amount": total_amount_paise,
        "currency": "INR",
        "payment_capture": 1
    })

    # Save PENDING order to DB
    cur.execute("""
        INSERT INTO orders
        (user_id, food_id, quantity, restaurant_id,
         total_amount, user_email, status, payment_status, razorpay_order_id)
        VALUES (%s,%s,%s,%s,%s,%s,'PENDING','PENDING',%s)
    """, (
        user_id,
        food_id,
        quantity,
        food["restaurant_id"],
        platform_unit_price * quantity, 
        email,
        razorpay_order["id"]
    ))

    mysql.connection.commit()
    
    # Return the data Flutter needs to open the Razorpay SDK
    return jsonify({
        "success": True,
        "razorpay_order_id": razorpay_order["id"],
        "amount": total_amount_paise,
        "key": os.getenv("RAZORPAY_KEY_ID")
    }), 200


# ================= VERIFY PAYMENT API =================
@order_bp.route("/api/verify-payment", methods=["POST"])
@limiter.limit("20 per minute")
@jwt_required()
def verify_payment():
    data = request.json
    
    # Flutter should send these three exact keys from the Razorpay SDK
    required_keys = ["razorpay_order_id", "razorpay_payment_id", "razorpay_signature"]
    if not all(k in data for k in required_keys):
        return jsonify({"success": False, "error": "Missing signature data"}), 400

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # 1. Verify Signature
    try:
        razorpay_client.utility.verify_payment_signature({
            'razorpay_order_id': data['razorpay_order_id'],
            'razorpay_payment_id': data['razorpay_payment_id'],
            'razorpay_signature': data['razorpay_signature']
        })
    except razorpay.errors.SignatureVerificationError:
        return jsonify({"success": False, "error": "Invalid payment signature"}), 400

    # Fetch order details
    cur.execute("""
        SELECT o.*, f.name AS food_name, f.price AS res_unit_price, 
               r.name AS restaurant_name, r.gpay_upi, r.mobile AS res_mobile, r.email AS res_email, r.location_link AS res_location
        FROM orders o
        JOIN foods f ON o.food_id = f.id
        JOIN restaurants r ON f.restaurant_id = r.id
        WHERE o.razorpay_order_id=%s AND o.payment_status='PENDING'
        FOR UPDATE
    """, (data["razorpay_order_id"],))
    order = cur.fetchone()

    if not order:
        return jsonify({"success": False, "error": "Order not found or already paid"}), 400

    # 2. Stock Update
    cur.execute("""
        UPDATE foods 
        SET available_quantity = available_quantity - %s 
        WHERE id=%s AND available_quantity >= %s
    """, (order["quantity"], order["food_id"], order["quantity"]))

    if cur.rowcount == 0:
        mysql.connection.rollback()
        # Note: If stock runs out during payment, you need a refund flow here.
        return jsonify({"success": False, "error": "Out of stock during payment processing"}), 409

    # 3. GENERATE OTP & Update Order
    otp = str(random.randint(100000, 999999))

    cur.execute("""
        UPDATE orders 
        SET payment_status='PAID', 
            status='CONFIRMED', 
            razorpay_payment_id=%s, 
            pickup_otp=%s 
        WHERE id=%s
    """, (data["razorpay_payment_id"], otp, order["id"]))

    mysql.connection.commit()

    # --- FINANCIAL REPORTING & EMAILS ---
    # (Your exact email logic remains here. In a production app, consider moving 
    # these send_email() calls to a background task so the API responds to Flutter instantly).
    
    qty = order["quantity"]
    total_paid_by_user = float(order["total_amount"]) 
    res_unit_price = float(order["res_unit_price"])
    res_total_payout = res_unit_price * qty
    
    # ... [Keep your exact send_email code block here] ...

    # Return success and OTP back to the Flutter app
    return jsonify({"success": True, "pickup_otp": otp}), 200
