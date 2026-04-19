import os

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")

MYSQL_HOST = os.getenv("MYSQL_HOST")
MYSQL_USER = os.getenv("MYSQL_USER")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")
MYSQL_DB = os.getenv("MYSQL_DB")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", 3306))

MYSQL_CURSORCLASS = "DictCursor"

RAZORPAY_KEY_ID = os.getenv("rzp_test_S2bmctosdabOoM")
RAZORPAY_SECRET = os.getenv("77RfmWU2bJoKhsAknuxti9bi")

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "terminalplate@gmail.com")

