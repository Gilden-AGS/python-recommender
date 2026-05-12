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
    default_password = os.getenv("EXPERT_PASSWORD", "expert12345").encode("utf-8")

    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT id, contact_email FROM experts")
    experts = cur.fetchall()

    for e in experts:
        expert_id = int(e["id"])
        login_email = e.get("contact_email")

        # Skip if email missing.
        if not login_email:
            continue

        cur.execute("SELECT id FROM expert_users WHERE expert_id=%s", (expert_id,))
        if cur.fetchone():
            continue

        password_hash = bcrypt.hashpw(default_password, bcrypt.gensalt()).decode("utf-8")
        cur.execute(
            """
            INSERT INTO expert_users (expert_id, login_email, login_username, password_hash)
            VALUES (%s,%s,NULL,%s)
            """,
            (expert_id, login_email, password_hash),
        )

    conn.commit()
    cur.close()
    conn.close()

    print("Expert accounts created/ensured.")


if __name__ == "__main__":
    main()

