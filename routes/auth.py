import config
from flask import Flask, request, jsonify
from flask_jwt_extended import (
    JWTManager, create_access_token,
    jwt_required, get_jwt_identity
)
import MySQLdb
import MySQLdb.cursors
import math
from datetime import datetime, timedelta

app = Flask(__name__)

# ================= CONFIG =================
app.config["JWT_SECRET_KEY"] = config.SECRET_KEY
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = 3600

jwt = JWTManager(app)


# ================= DB CONNECTION =================
def get_connection():
    return MySQLdb.connect(
        host=config.MYSQL_HOST,
        user=config.MYSQL_USER,
        passwd=config.MYSQL_PASSWORD,
        db=config.MYSQL_DB,
        port=config.MYSQL_PORT,
        cursorclass=MySQLdb.cursors.DictCursor
    )


# ================= AUTH =================

@app.route("/api/user/signup", methods=["POST"])
def signup():
    conn = None
    cur = None
    try:
        data = request.json
        name = data.get("name")
        email = data.get("email")
        mobile = data.get("mobile")
        password = data.get("password")

        if not all([name, email, mobile, password]):
            return jsonify({"status": "error", "message": "All fields required"}), 400

        conn = get_connection()
        cur = conn.cursor()

        cur.execute("SELECT id FROM users WHERE email=%s", (email,))
        if cur.fetchone():
            return jsonify({"status": "error", "message": "Email exists"}), 400

        cur.execute("SELECT id FROM users WHERE mobile=%s", (mobile,))
        if cur.fetchone():
            return jsonify({"status": "error", "message": "Mobile exists"}), 400

        cur.execute("""
            INSERT INTO users (name, email, mobile, password_hash)
            VALUES (%s, %s, %s, %s)
        """, (name, email, mobile, password))

        conn.commit()

        user_id = cur.lastrowid
        token = create_access_token(identity={"id": user_id, "role": "user"})

        return jsonify({"status": "success", "token": token})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

    finally:
        if cur: cur.close()
        if conn: conn.close()


@app.route("/api/user/login", methods=["POST"])
def login():
    conn = None
    cur = None
    try:
        data = request.json
        mobile = data.get("mobile")
        password = data.get("password")

        conn = get_connection()
        cur = conn.cursor()

        cur.execute("SELECT id, password_hash FROM users WHERE mobile=%s", (mobile,))
        user = cur.fetchone()

        if not user or user["password_hash"] != password:
            return jsonify({"status": "error", "message": "Invalid credentials"}), 401

        token = create_access_token(identity={"id": user["id"], "role": "user"})

        return jsonify({"status": "success", "token": token})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

    finally:
        if cur: cur.close()
        if conn: conn.close()


@app.route("/api/user/profile", methods=["GET"])
@jwt_required()
def profile():
    conn = None
    cur = None
    try:
        user = get_jwt_identity()

        conn = get_connection()
        cur = conn.cursor()

        cur.execute("SELECT name, email, mobile FROM users WHERE id=%s", (user["id"],))
        data = cur.fetchone()

        return jsonify({"status": "success", "data": data})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

    finally:
        if cur: cur.close()
        if conn: conn.close()


# ================= FOODS =================

@app.route("/api/foods", methods=["GET"])
@jwt_required()
def foods():
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        ist_now = datetime.utcnow() + timedelta(hours=5, minutes=30)
        current_time = ist_now.strftime('%H:%M:%S')

        cur.execute("""
        SELECT 
            f.id, f.name, f.original_price, f.price, f.available_quantity,
            r.name AS restaurant_name,
            r.latitude, r.longitude
        FROM foods f
        JOIN restaurants r ON f.restaurant_id = r.id
        WHERE f.is_active = 1 AND f.available_quantity > 0
        """)

        rows = cur.fetchall()

        result = []

        for f in rows:
            price = float(f["price"])
            mrp = float(f["original_price"] or price)

            result.append({
                "id": f["id"],
                "name": f["name"],
                "price": math.ceil(price * 1.15),
                "mrp": math.ceil(mrp * 1.15),
                "restaurant": f["restaurant_name"],
                "latitude": f["latitude"],
                "longitude": f["longitude"]
            })

        return jsonify({"status": "success", "data": result})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

    finally:
        if cur: cur.close()
        if conn: conn.close()


# ================= RUN =================
if __name__ == "__main__":
    app.run(debug=True)
