from flask import Blueprint, jsonify, session, render_template
from utils.db import mysql
import MySQLdb.cursors
from datetime import date, timedelta

savings_bp = Blueprint("savings", __name__)

@savings_bp.route('/savings')
def savings_page():
    return render_template('user/savings.html')

@savings_bp.route('/api/savings', methods=['GET'])
def get_savings():
    user_id = session.get('user_id', 1)
    conn = mysql.connection
    cur = conn.cursor(MySQLdb.cursors.DictCursor)

    # 1. TOTAL MEALS + TOTAL SAVINGS
    cur.execute("""
        SELECT 
            COUNT(o.id) AS meals_rescued,
            COALESCE(SUM((f.original_price - f.price) * o.quantity), 0) AS total_saved
        FROM orders o
        JOIN foods f ON o.food_id = f.id
        WHERE o.user_id = %s
        AND o.status IN ('CONFIRMED', 'PICKED_UP')
        AND o.payment_status = 'PAID'
    """, (user_id,))
    total_stats = cur.fetchone()

    # 2. TODAY SAVINGS
    cur.execute("""
        SELECT 
            COALESCE(SUM((f.original_price - f.price) * o.quantity), 0) AS saved_today
        FROM orders o
        JOIN foods f ON o.food_id = f.id
        WHERE o.user_id = %s
        AND o.status IN ('CONFIRMED', 'PICKED_UP')
        AND o.payment_status = 'PAID'
        AND DATE(o.created_at) = CURDATE()
    """, (user_id,))
    today_stats = cur.fetchone()

    # 3. STREAK CALCULATION
    # Fetch all distinct order dates (most recent first)
    cur.execute("""
        SELECT DISTINCT DATE(o.created_at) AS order_date
        FROM orders o
        WHERE o.user_id = %s
        AND o.status IN ('CONFIRMED', 'PICKED_UP')
        AND o.payment_status = 'PAID'
        ORDER BY order_date DESC
    """, (user_id,))
    order_dates = {row['order_date'] for row in cur.fetchall()}

    today = date.today()
    streak = 0

    # Walk backwards from today; break as soon as a day has no order
    check = today
    while check in order_dates:
        streak += 1
        check -= timedelta(days=1)

    # If user hasn't ordered today yet, also check from yesterday
    # (streak is still "alive" if they ordered yesterday)
    if today not in order_dates:
        check = today - timedelta(days=1)
        temp = 0
        while check in order_dates:
            temp += 1
            check -= timedelta(days=1)
        streak = temp  # streak from yesterday (not broken yet today)

    # Build this week's 7-day grid (Mon → Sun of current week)
    monday = today - timedelta(days=today.weekday())
    week_days = []
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    for i in range(7):
        d = monday + timedelta(days=i)
        week_days.append({
            "day": day_names[i],
            "done": d in order_dates,
            "today": d == today,
            "future": d > today
        })

    # 4. RECENT TRANSACTIONS
    cur.execute("""
        SELECT 
            r.name AS restaurant_name,
            f.name AS food_name,
            o.created_at,
            (f.original_price - f.price) * o.quantity AS amount_saved
        FROM orders o
        JOIN foods f ON o.food_id = f.id
        JOIN restaurants r ON o.restaurant_id = r.id
        WHERE o.user_id = %s
        AND o.status IN ('CONFIRMED', 'PICKED_UP')
        AND o.payment_status = 'PAID'
        ORDER BY o.created_at DESC
        LIMIT 8
    """, (user_id,))
    recent_orders = cur.fetchall()

    total_saved = int(total_stats["total_saved"])
    saved_today = int(today_stats["saved_today"])
    meals = total_stats["meals_rescued"]

    formatted_tx = [{
        "icon": "🥗",
        "type": "credit",
        "name": tx['food_name'],
        "place": tx['restaurant_name'],
        "time": tx['created_at'].strftime("%b %d, %I:%M %p"),
        "amount": f"+₹{int(tx['amount_saved'])}"
    } for tx in recent_orders]

    # City rank (simple: count users who saved more)
    cur.execute("""
        SELECT COUNT(*) + 1 AS rank_pos
        FROM (
            SELECT user_id, SUM((f.original_price - f.price) * o.quantity) AS s
            FROM orders o JOIN foods f ON o.food_id = f.id
            WHERE o.status IN ('CONFIRMED','PICKED_UP') AND o.payment_status='PAID'
            GROUP BY user_id
        ) t
        WHERE t.s > %s
    """, (total_saved,))
    rank_row = cur.fetchone()
    city_rank = rank_row['rank_pos'] if rank_row else 1

    return jsonify({
        "total_saved": total_saved,
        "saved_today": saved_today,
        "meals_rescued": meals,
        "food_kg": round(meals * 0.4, 1),
        "co2_kg": round(meals * 1.2, 1),
        "streak": streak,
        "city_rank": city_rank,
        "referral_code": "RESCUE50",
        "week_days": week_days,
        "milestones": [
            {"icon": "🥗", "name": "First Rescue",      "desc": "Complete your very first rescue",  "reward": "Unlocked!", "progress": 100,                    "unlocked": meals >= 1},
            {"icon": "🌱", "name": "5 Meals Rescued",   "desc": "Rescue 5 meals total",             "reward": "₹40 Off",  "progress": min(meals/5*100, 100),  "unlocked": meals >= 5},
            {"icon": "🌍", "name": "10 Meals Rescued",  "desc": "Rescue 10 meals total",            "reward": "₹75 Off",  "progress": min(meals/10*100, 100), "unlocked": meals >= 10},
            {"icon": "🔥", "name": "7-Day Streak",      "desc": "Rescue every day for a week",      "reward": "₹120 Off", "progress": min(streak/7*100, 100), "unlocked": streak >= 7},
        ],
        "transactions": formatted_tx
    })
