from flask import Flask, jsonify
from flask_cors import CORS
from utils.db import mysql, set_mysql_timezone
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_jwt_extended import JWTManager
import os

app = Flask(__name__)

# 🔥 CORS
CORS(app)

# 🔥 Proxy fix (Railway)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)

# 🔥 Load config
app.config.from_pyfile("config.py")

# 🔥 MySQL config (Railway env vars)
app.config['MYSQL_HOST'] = os.getenv("MYSQLHOST")
app.config['MYSQL_USER'] = os.getenv("MYSQLUSER")
app.config['MYSQL_PASSWORD'] = os.getenv("MYSQLPASSWORD")
app.config['MYSQL_DB'] = os.getenv("MYSQLDATABASE")
app.config['MYSQL_PORT'] = int(os.getenv("MYSQLPORT"))

# 🔥 Init MySQL (ONLY ONCE)
mysql.init_app(app)

# 🔥 JWT
app.config["JWT_SECRET_KEY"] = app.config["SECRET_KEY"]
jwt = JWTManager(app)

# 🔥 Rate limiter
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["100 per minute"]
)

# 🔥 Secret key
app.secret_key = app.config["SECRET_KEY"]

# 🔥 DB setup
with app.app_context():
    try:
        set_mysql_timezone()
    except Exception as e:
        print("Timezone init skipped:", e)
# ================= BLUEPRINTS =================

from routes.auth import auth_bp
app.register_blueprint(auth_bp)

from routes.cities import cities_bp
app.register_blueprint(cities_bp)

from routes.reserve_seat import reserve_seat_bp
app.register_blueprint(reserve_seat_bp)

from routes.restaurant import restaurant_bp
app.register_blueprint(restaurant_bp)

from routes.browse import browse_bp
app.register_blueprint(browse_bp)

from routes.order import order_bp
app.register_blueprint(order_bp)

from routes.savings import savings_bp
app.register_blueprint(savings_bp)

from routes.secret import secret_bp
app.register_blueprint(secret_bp)


# ================= ERROR HANDLER =================

@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({
        "status": "error",
        "message": "Too many requests"
    }), 429


# ================= MAIN =================

if __name__ == "__main__":
    app.run(debug=True)
