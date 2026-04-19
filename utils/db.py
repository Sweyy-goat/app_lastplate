from flask_mysqldb import MySQL

mysql = MySQL()

def set_mysql_timezone():
    try:
        cur = mysql.connection.cursor()
        cur.execute("SET time_zone = '+05:30'")
        cur.close()
    except Exception as e:
        print("MySQL timezone setup skipped:", e)
