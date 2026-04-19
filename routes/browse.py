from flask import Blueprint, jsonify
from utils.db import mysql
import MySQLdb.cursors
import math
from datetime import datetime, timedelta
from flask_jwt_extended import jwt_required, get_jwt_identity

browse_bp = Blueprint("browse", __name__)

# ================= FOOD LIST API =================
@browse_bp.route("/api/foods", methods=["GET"])
def food_list():
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    ist_now = datetime.utcnow() + timedelta(hours=5, minutes=30)
    current_time_ist = ist_now.strftime('%H:%M:%S')

    query = """
    SELECT 
        f.id, f.name, f.original_price, f.price, f.available_quantity,
        f.food_type, f.pickup_start, f.pickup_end,
        r.name AS restaurant_name,
        r.address AS restaurant_address,
        r.short_address AS restaurant_short_address,
        r.latitude,
        r.longitude,
        CASE
            WHEN f.pickup_end >= f.pickup_start THEN 
                TIMESTAMPDIFF(MINUTE, CAST(%s AS TIME), f.pickup_end)
            ELSE
                TIMESTAMPDIFF(MINUTE, CAST(%s AS TIME), ADDTIME(f.pickup_end, '24:00:00'))
        END AS minutes_left
    FROM foods f
    JOIN restaurants r ON f.restaurant_id = r.id
    WHERE f.is_active = 1
      AND f.available_quantity > 0
      AND (
          (f.pickup_start <= f.pickup_end AND CAST(%s AS TIME) BETWEEN f.pickup_start AND f.pickup_end)
          OR
          (f.pickup_start > f.pickup_end AND 
                (CAST(%s AS TIME) >= f.pickup_start OR CAST(%s AS TIME) <= f.pickup_end)
          )
      )
    ORDER BY minutes_left ASC;
    """

    cur.execute(query, (
        current_time_ist,
        current_time_ist,
        current_time_ist,
        current_time_ist,
        current_time_ist
    ))

    rows = cur.fetchall()
    cur.close()

    foods = []
    for f in rows:
        restaurant_price = float(f["price"])
        raw_original = float(f["original_price"]) if f.get("original_price") and f["original_price"] > 0 else restaurant_price

        platform_price = math.ceil(restaurant_price * 1.15)
        display_mrp = math.ceil(raw_original * 1.15)

        foods.append({
            "id": f["id"],
            "name": f["name"],
            "food_type": f["food_type"],
            "price": platform_price,
            "mrp": display_mrp,
            "available_quantity": f["available_quantity"],
            "restaurant_name": f["restaurant_name"],
            "restaurant_address": f["restaurant_address"],
            "restaurant_short_address": f.get("restaurant_short_address") or "",
            "minutes_left": max(0, int(f["minutes_left"])),
            "latitude": f["latitude"],
            "longitude": f["longitude"]
        })

    return jsonify({
        "status": "success",
        "data": foods
    })


# ================= CHECK AUTH =================
@browse_bp.route("/api/check-auth", methods=["GET"])
@jwt_required()
def check_auth():
    return jsonify({
        "status": "success",
        "logged_in": True,
        "user_id": get_jwt_identity()
    })


# ================= WALK-IN RESTAURANTS =================
@browse_bp.route("/api/walkin", methods=["GET"])
@jwt_required()
def walkin_list():
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cur.execute("""
        SELECT r.id, r.name, r.address
        FROM restaurants r
        JOIN restaurant_scenes s ON s.restaurant_id = r.id
        GROUP BY r.id
    """)

    restaurants = cur.fetchall()
    cur.close()

    return jsonify({
        "status": "success",
        "data": restaurants
    })


# ================= WALK-IN VIEW =================
@browse_bp.route("/api/restaurant/<int:rid>/walkin", methods=["GET"])
@jwt_required()
def walkin_view(rid):
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cur.execute("""
        SELECT id, image_url 
        FROM restaurant_scenes 
        WHERE restaurant_id = %s
        LIMIT 1
    """, (rid,))
    scene = cur.fetchone()

    if not scene:
        cur.close()
        return jsonify({
            "status": "error",
            "message": "No walk-in scene found"
        }), 404

    cur.execute("""
        SELECT pitch, yaw, seat_number
        FROM restaurant_hotspots
        WHERE scene_id = %s
    """, (scene["id"],))
    hotspots = cur.fetchall()

    cur.close()

    return jsonify({
        "status": "success",
        "scene": scene,
        "hotspots": hotspots
    })
