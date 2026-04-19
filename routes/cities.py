from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required
from utils.db import mysql
import MySQLdb.cursors

cities_bp = Blueprint("cities", __name__)

@cities_bp.route("/api/cities", methods=["GET"])
@jwt_required()   # optional (remove if public)
def get_cities():
    try:
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

        cur.execute("""
            SELECT name 
            FROM cities 
            WHERE is_active = 1 
            ORDER BY name
        """)

        cities = cur.fetchall()
        cur.close()

        return jsonify({
            "status": "success",
            "data": cities
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
