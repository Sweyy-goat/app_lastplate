from flask import Flask, render_template
from utils.db import mysql, set_mysql_timezone

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)
app.config.from_pyfile("config.py")

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["100 per minute"]
)

mysql.init_app(app)
app.secret_key = app.config["SECRET_KEY"]

# Run DB initialization once safely
with app.app_context():
    try:
        set_mysql_timezone()
    except Exception as e:
        print("Timezone init skipped:", e)


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

@app.errorhandler(429)
def ratelimit_handler(e):
    return render_template("429.html"), 429


@app.route("/how")
def how():
    return render_template("how.html")


@app.route("/")
def home():
    return render_template("index.html")


if __name__ == "__main__":
    app.run()
