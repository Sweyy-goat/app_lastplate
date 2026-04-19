from flask import Blueprint, render_template
from utils.db import mysql
import MySQLdb.cursors

cities_bp = Blueprint("cities", __name__)

@cities_bp.route("/cities")
def cities():
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cur.execute("SELECT name FROM cities WHERE is_active = 1 ORDER BY name")
    cities = cur.fetchall()

    return render_template("cities.html", cities=cities)
