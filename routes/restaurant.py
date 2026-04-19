from flask import Blueprint, render_template, request, jsonify, session, redirect
from utils.db import mysql
import MySQLdb.cursors
import random

restaurant_bp = Blueprint("restaurant", __name__, url_prefix="/restaurant")

def restaurant_required():
    return session.get("role") == "restaurant"

# -----------------------------
# LOGIN PAGE (STEP 1)
# -----------------------------
@restaurant_bp.route("/login", methods=["GET"])
def login_page():
    return render_template("restaurant/login.html")


# -----------------------------
# SEND OTP API (STEP 2)
# -----------------------------
@restaurant_bp.route("/api/send-otp", methods=["POST"])
def send_otp():
    phone = request.json.get("mobile")

    if not phone:
        return jsonify({"success": False, "error": "Mobile number required"}), 400

    otp = random.randint(100000, 999999)

    session["otp"] = otp
    session["otp_mobile"] = phone

    # TODO: Replace with SMS API (MSG91, Fast2SMS, Twilio, etc.)
    print("RESTAURANT OTP:", otp)

    return jsonify({"success": True})


# -----------------------------
# VERIFY OTP PAGE (STEP 3)
# -----------------------------
@restaurant_bp.route("/verify-otp", methods=["GET"])
def verify_otp_page():
    return render_template("restaurant/verify_otp.html")

# 1. Verification Route (Only checks and returns info)
@restaurant_bp.route("/api/verify-otp", methods=["POST"])
def verify_pickup_otp():
    otp = request.json.get("otp")
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    cur.execute("""
        SELECT o.id, o.quantity, u.name as customer_name, f.name as food_name
        FROM orders o
        JOIN users u ON o.user_id = u.id
        JOIN foods f ON o.food_id = f.id
        WHERE o.pickup_otp = %s AND o.status = 'CONFIRMED' AND o.picked_up = 0
        LIMIT 1
    """, (otp,))
    order = cur.fetchone()

    if not order:
        return jsonify({"success": False, "error": "Invalid or expired OTP"}), 400

    return jsonify({
        "success": True,
        "order_id": order["id"],
        "food": order["food_name"],
        "quantity": order["quantity"],
        "customer": order["customer_name"]
    })

# 2. Final Handover Route (Updates the DB)
@restaurant_bp.route("/api/complete-order", methods=["POST"])
def complete_order():
    order_id = request.json.get("order_id")
    cur = mysql.connection.cursor()
    
    # Mark as picked up and clear the OTP so it can't be reused
    cur.execute("""
        UPDATE orders 
        SET picked_up = 1, pickup_otp = NULL 
        WHERE id = %s
    """, (order_id,))
    
    mysql.connection.commit()
    return jsonify({"success": True})

# -----------------------------
# DASHBOARD
# -----------------------------
@restaurant_bp.route("/dashboard")
def dashboard():
    if not restaurant_required():
        return redirect("/restaurant/login")
    return render_template("restaurant/dashboard.html")


# -----------------------------
# ADD FOOD PAGE
# -----------------------------
@restaurant_bp.route("/add-food")
def add_food_page():
    if not restaurant_required():
        return redirect("/restaurant/login")
    return render_template("restaurant/add_food.html")


# -----------------------------
# ADD FOOD API
# -----------------------------
# -----------------------------
# ADD FOOD API
# -----------------------------
@restaurant_bp.route("/api/add-food", methods=["POST"])
def add_food():
    if not restaurant_required():
        return jsonify({"success": False}), 401

    data = request.json
    restaurant_id = session["restaurant_id"]

    try:
        price = int(data.get("price"))
        original_price = int(data.get("original_price"))
        quantity = int(data.get("quantity"))
    except:
        return jsonify({"error": "Invalid numeric values"}), 400

    if price <= 0 or quantity <= 0:
        return jsonify({"error": "Invalid price or quantity"}), 400

    food_type = data.get("food_type")

    if food_type not in ["veg", "egg", "nonveg"]:
        return jsonify({"error": "Invalid food type"}), 400

    cur = mysql.connection.cursor()

    cur.execute("""
        INSERT INTO foods
        (restaurant_id, name, original_price, price,
         available_quantity, pickup_start, pickup_end,
         food_type, is_active, created_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,1,
        CONVERT_TZ(NOW(), '+00:00', '+05:30'))
    """, (
        restaurant_id,
        data["name"],
        original_price,
        price,
        quantity,
        data["pickup_start"],
        data["pickup_end"],
        food_type
    ))

    mysql.connection.commit()

    return jsonify({"success": True})

# -----------------------------
# GET MY FOODS
# -----------------------------
@restaurant_bp.route("/api/my-foods")
def my_foods():
    if not restaurant_required():
        return jsonify([]), 401

    restaurant_id = session["restaurant_id"]

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("""
        SELECT
            id,
            name,
            price,
            available_quantity,
            pickup_start,
            pickup_end,
            is_active
        FROM foods
        WHERE restaurant_id = %s
        ORDER BY pickup_end ASC
    """, (restaurant_id,))

    rows = cur.fetchall()

    foods = []
    for f in rows:
        foods.append({
            "id": f["id"],
            "name": f["name"],
            "price": f["price"],
            "available_quantity": f["available_quantity"],
            "pickup_start": str(f["pickup_start"]),
            "pickup_end": str(f["pickup_end"]),
            "is_active": bool(f["is_active"])
        })

    return jsonify(foods)


# -----------------------------
# CANCEL FOOD
# -----------------------------
@restaurant_bp.route("/api/cancel-food/<int:food_id>", methods=["POST"])
def cancel_food(food_id):
    if not restaurant_required():
        return jsonify({"success": False}), 401

    cur = mysql.connection.cursor()
    cur.execute("""
        UPDATE foods
        SET is_active = 0
        WHERE id = %s AND restaurant_id = %s
    """, (food_id, session["restaurant_id"]))

    mysql.connection.commit()
    return jsonify({"success": True})


# -----------------------------
# UPDATE FOOD QUANTITY
# -----------------------------
@restaurant_bp.route("/api/update-food-quantity/<int:food_id>", methods=["POST"])
def update_food_quantity(food_id):
    if not restaurant_required():
        return jsonify({"success": False}), 401

    data = request.json
    new_qty = int(data["quantity"])

    cur = mysql.connection.cursor()
    cur.execute("""
        UPDATE foods
        SET available_quantity = %s,
            is_active = IF(%s > 0, 1, 0)
        WHERE id = %s AND restaurant_id = %s
    """, (new_qty, new_qty, food_id, session["restaurant_id"]))

    mysql.connection.commit()
    return jsonify({"success": True})
    
@restaurant_bp.route("/api/my-secret-menu")
def my_secret_menu():
    if not restaurant_required():
        return jsonify([]), 401

    rid = session["restaurant_id"]
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cur.execute("""
        SELECT 
            id,
            name,
            price,
            mrp,
            stock,
            img,
            is_today_special,
            created_at
        FROM secret_menu
        WHERE restaurant_id = %s
        ORDER BY created_at DESC
    """, (rid,))

    items = cur.fetchall()
    return jsonify(items)
@restaurant_bp.route("/api/toggle-secret/<int:item_id>", methods=["POST"])
def toggle_secret(item_id):
    if not restaurant_required():
        return jsonify({"success": False}), 401

    rid = session["restaurant_id"]
    cur = mysql.connection.cursor()

    cur.execute("""
        UPDATE secret_menu
        SET is_today_special = NOT is_today_special
        WHERE id = %s AND restaurant_id = %s
    """, (item_id, rid))

    mysql.connection.commit()
    return jsonify({"success": True})
@restaurant_bp.route("/secret-menu")
def secret_menu_page():
    if not restaurant_required():
        return redirect("/restaurant/login")
    return render_template("restaurant/secret_menu.html")
@restaurant_bp.route("/secret-menu/add")
def secret_menu_add_page():
    if not restaurant_required():
        return redirect("/restaurant/login")
    return render_template("restaurant/secret_add.html")
@restaurant_bp.route("/api/secret-menu/add", methods=["POST"])
def api_secret_add():
    if not restaurant_required():
        return jsonify({"success": False}), 401

    data = request.json
    rid = session["restaurant_id"]

    cur = mysql.connection.cursor()

    cur.execute("""
        INSERT INTO secret_menu
        (restaurant_id, name, description, cuisine, mrp, price, stock, img, is_today_special)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,0)
    """, (
        rid,
        data["name"],
        data["description"],
        data["cuisine"],
        data["mrp"],
        data["price"],
        data["stock"],
        data["img"]
    ))

    mysql.connection.commit()
    return jsonify({"success": True})
from flask import render_template, request
from utils.db import mysql
from MySQLdb.cursors import DictCursor

@restaurant_bp.route("/restaurant/<int:id>/walkin")
def walkin(id):
    cur = mysql.connection.cursor(DictCursor)

    # get restaurant info
    cur.execute("SELECT * FROM restaurants WHERE id=%s", (id,))
    restaurant = cur.fetchone()

    # load scenes
    cur.execute("SELECT * FROM restaurant_scenes WHERE restaurant_id=%s", (id,))
    scenes_rows = cur.fetchall()

    scenes = {}

    for row in scenes_rows:
        scene_name = f"scene{row['id']}"

        # load hotspots for this scene
        cur.execute("SELECT * FROM restaurant_hotspots WHERE scene_id=%s", (row["id"],))
        hotspots_rows = cur.fetchall()

        hotspots = []
        for h in hotspots_rows:
            hotspots.append({
                "pitch": h["pitch"],
                "yaw": h["yaw"],
                "text": f"Seat {h['seat_number']}",
                "type": "info",
                "clickHandlerFunc": "selectSeat",
                "clickHandlerArgs": [h["seat_number"]]
            })

        scenes[scene_name] = {
            "type": "equirectangular",
            "panorama": row["image_url"],
            "hotSpots": hotspots
        }

    return render_template(
        "restaurant/walkin.html",
        restaurant=restaurant,
        scenes=scenes
    )
@restaurant_bp.route("/reserve-seat")
def reserve_seat():
    restaurant_id = request.args.get("restaurant")
    seat = request.args.get("seat")
    return render_template(
        "restaurant/reserve_seat.html",
        restaurant_id=restaurant_id,
        seat=seat
    )
@restaurant_bp.route("/walkin")
def walkin_list():
    cur = mysql.connection.cursor(DictCursor)

    # get only restaurants that have 360 scenes
    cur.execute("""
        SELECT DISTINCT r.id, r.name, r.address
        FROM restaurants r
        JOIN restaurant_scenes s ON r.id = s.restaurant_id
        WHERE r.is_active = 1
    """)
    restaurants = cur.fetchall()

    return render_template(
        "restaurant/walkin_list.html",
        restaurants=restaurants
    )
