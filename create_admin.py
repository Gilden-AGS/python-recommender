import os

import bcrypt
import mysql.connector
from dotenv import load_dotenv

load_dotenv()


def get_db():
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DATABASE", "nutrition_expert"),
    )


def main():
    username = os.getenv("ADMIN_USERNAME", "admin")
    email = os.getenv("ADMIN_EMAIL", "admin@example.com")
    password = os.getenv("ADMIN_PASSWORD", "admin12345").encode("utf-8")
    password_hash = bcrypt.hashpw(password, bcrypt.gensalt()).decode("utf-8")

    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO users (username, email, password_hash, role)
            VALUES (%s,%s,%s,'admin')
            ON DUPLICATE KEY UPDATE
              email=VALUES(email),
              password_hash=VALUES(password_hash),
              role='admin'
            """,
            (username, email, password_hash),
        )
    except Exception:
        # Fallback for older DBs without users.email column.
        cur.execute(
            """
            INSERT INTO users (username, password_hash, role)
            VALUES (%s,%s,'admin')
            ON DUPLICATE KEY UPDATE
              password_hash=VALUES(password_hash),
              role='admin'
            """,
            (username, password_hash),
        )
    conn.commit()
    cur.close()
    conn.close()

    print(f"Admin ensured. username={username} password={password.decode('utf-8')}")


if __name__ == "__main__":
    main()

