import config
from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token,
    jwt_required,
    get_jwt_identity
)
import MySQLdb
import MySQLdb.cursors

# ✅ THIS IS THE FIX
auth_bp = Blueprint("auth", __name__)


# ================= DB =================
import os

def get_connection():
    return MySQLdb.connect(
        host=os.getenv("MYSQLHOST"),
        user=os.getenv("MYSQLUSER"),
        passwd=os.getenv("MYSQLPASSWORD"),
        db=os.getenv("MYSQLDATABASE"),
        port=int(os.getenv("MYSQLPORT")),
        cursorclass=MySQLdb.cursors.DictCursor
    )


# ================= SIGNUP =================
@auth_bp.route("/api/user/signup", methods=["POST"])
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


# ================= LOGIN =================
@auth_bp.route("/api/user/login", methods=["POST"])
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


# ================= PROFILE =================
@auth_bp.route("/api/user/profile", methods=["GET"])
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
