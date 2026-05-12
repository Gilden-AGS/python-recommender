from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import json
import re
import bcrypt
import mysql.connector
from dotenv import load_dotenv
from flask import Flask, abort, redirect, render_template, request, session, url_for, send_from_directory

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "change-this-secret-key")

#region debug lcogging
RUN_ID = "debug_pre_expert_dashboard"
DEBUG_SESSION_ID = "87bbf1"
LOG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "debug-87bbf1.log")


def _debug_log(hypothesis_id: str, location: str, message: str, data: Optional[Dict[str, Any]] = None) -> None:
    payload: Dict[str, Any] = {
        "sessionId": DEBUG_SESSION_ID,
        "runId": RUN_ID,
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data or {},
        "timestamp": int(datetime.utcnow().timestamp() * 1000),
    }
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        # Avoid breaking app if logging fails.
        pass


#endregion debug logging

# Serve images from local project folder: python-recommender/assets/images
ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets", "images")


@app.get("/assets/<path:filename>")
def serve_asset(filename: str):
    return send_from_directory(ASSETS_DIR, filename)


def _list_asset_images() -> List[str]:
    if not os.path.isdir(ASSETS_DIR):
        return []
    out: List[str] = []
    for name in sorted(os.listdir(ASSETS_DIR)):
        lower = name.lower()
        if lower.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")):
            out.append(name)
    return out


@app.context_processor
def inject_asset_images():
    imgs = _list_asset_images()
    return {
        "asset_images": imgs,
        "hero_image": imgs[0] if len(imgs) > 0 else None,
        "secondary_image": imgs[1] if len(imgs) > 1 else (imgs[0] if imgs else None),
    }


@app.context_processor
def inject_nav_user_expert():
    return {"user": current_user(), "expert": current_expert()}


def db_config() -> Dict[str, str]:
    return {
        "host": os.getenv("MYSQLHOST"),
        "port":int(os.getenv("MYSQLPORT", 3306)),
        "user": os.getenv("MYSQLUSER"),
        "password": os.getenv("MYSQLPASSWORD"),
        "database": os.getenv("MYSQLDATABASE"),
    }


def get_db():
    return mysql.connector.connect(**db_config())


def current_user() -> Optional[Dict[str, Any]]:
    uid = session.get("user_id")
    if not uid:
        return None
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT id, username, role FROM users WHERE id=%s", (uid,))
    user = cur.fetchone()
    cur.close()
    conn.close()
    return user


def require_login() -> Dict[str, Any]:
    user = current_user()
    if not user:
        return redirect(url_for("login", next=request.path))
    return user


def require_admin() -> Dict[str, Any]:
    user = current_user()
    if not user:
        return redirect(url_for("login", next=request.path))
    if user["role"] != "admin":
        abort(403)
    return user


def current_expert() -> Optional[Dict[str, Any]]:
    expert_id = session.get("expert_id")
    if not expert_id:
        return None
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    expert: Optional[Dict[str, Any]] = None
    try:
        cur.execute(
            """
            SELECT e.id, e.name, e.specialty, e.contact_email, e.contact_phone, e.bio,
                   COALESCE(eu.can_manage_kb, 0) AS can_manage_kb,
                   eu.linked_user_id
            FROM experts e
            JOIN expert_users eu ON eu.expert_id = e.id
            WHERE e.id=%s
            """,
            (expert_id,),
        )
        expert = cur.fetchone()
    except Exception:
        cur.execute(
            """
            SELECT id, name, specialty, contact_email, contact_phone, bio
            FROM experts
            WHERE id=%s
            """,
            (expert_id,),
        )
        expert = cur.fetchone()
        if expert:
            expert["can_manage_kb"] = 0
            expert["linked_user_id"] = None
    cur.close()
    conn.close()
    if expert and expert.get("can_manage_kb") is None:
        expert["can_manage_kb"] = 0
    if expert and "linked_user_id" not in expert:
        expert["linked_user_id"] = None
    return expert


def require_expert_login() -> Dict[str, Any]:
    expert = current_expert()
    if not expert:
        return redirect(url_for("expert_login", next=request.path))
    return expert


def require_expert_kb() -> Dict[str, Any]:
    expert = require_expert_login()
    if not isinstance(expert, dict):
        return expert
    if not int(expert.get("can_manage_kb") or 0):
        abort(403)
    return expert


def bmi_category(bmi: Optional[float]) -> str:
    if bmi is None:
        return ""
    if bmi < 18.5:
        return "Underweight"
    if bmi < 25:
        return "Normal weight"
    if bmi < 30:
        return "Overweight"
    return "Obese"


def infer_recommendations(symptom_ids: List[int]) -> List[Dict[str, Any]]:
    if not symptom_ids:
        return []

    placeholders = ",".join(["%s"] * len(symptom_ids))
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute(
        f"""
        SELECT d.id, d.code, d.name, d.description, d.general_advice,
               SUM(r.weight) AS score
        FROM rules r
        JOIN diagnoses d ON r.diagnosis_id = d.id
        WHERE r.symptom_id IN ({placeholders})
        GROUP BY d.id, d.code, d.name, d.description, d.general_advice
        ORDER BY score DESC
        """,
        symptom_ids,
    )
    diagnoses = cur.fetchall()
    cur.close()
    conn.close()
    return diagnoses


def foods_for_diagnoses(diagnosis_ids: List[int]) -> Dict[int, List[Dict[str, Any]]]:
    if not diagnosis_ids:
        return {}

    placeholders = ",".join(["%s"] * len(diagnosis_ids))
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute(
        f"""
        SELECT
            df.diagnosis_id,
            f.id AS food_id,
            f.name,
            f.local_name,
            f.category,
            COALESCE(MIN(df.note), '') AS note
        FROM diagnosis_foods df
        JOIN foods f ON df.food_id = f.id
        WHERE df.diagnosis_id IN ({placeholders})
        GROUP BY df.diagnosis_id, f.id, f.name, f.local_name, f.category
        ORDER BY f.category, f.name
        """,
        diagnosis_ids,
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    out: Dict[int, List[Dict[str, Any]]] = {}
    seen_per_diag: Dict[int, set] = {}
    for r in rows:
        diag_id = int(r["diagnosis_id"])
        # Defensive de-duplication for databases that already contain repeated food rows.
        key = (
            str(r.get("name") or "").strip().lower(),
            str(r.get("local_name") or "").strip().lower(),
            str(r.get("category") or "").strip().lower(),
        )
        seen = seen_per_diag.setdefault(diag_id, set())
        if key in seen:
            continue
        seen.add(key)
        out.setdefault(diag_id, []).append(r)
    return out


ALLERGY_KEYWORD_MAP: Dict[str, List[str]] = {
    "peanut": ["peanut", "groundnut", "nkatie"],
    "tree nut": ["cashew", "almond", "walnut", "hazelnut", "nut"],
    "milk": ["milk", "dairy", "cheese", "yoghurt", "yogurt", "butter"],
    "egg": ["egg", "eggs"],
    "fish": ["fish", "tilapia", "tuna", "salmon", "sardine"],
    "shellfish": ["shrimp", "prawn", "crab", "lobster", "shellfish"],
    "wheat": ["wheat", "gluten", "bread", "flour"],
    "soy": ["soy", "soya", "soybean", "tofu"],
    "sesame": ["sesame", "benne"],
}


def _expand_allergy_terms(terms: List[str]) -> List[str]:
    expanded: List[str] = []
    for t in terms:
        raw = str(t or "").strip().lower()
        if not raw:
            continue
        expanded.append(raw)
        tokens = [tok for tok in re.split(r"[/,\s\-]+", raw) if tok]
        expanded.extend(tokens)
        for key, synonyms in ALLERGY_KEYWORD_MAP.items():
            if key in raw or any(key in tok or tok in key for tok in tokens):
                expanded.extend(synonyms)
    # Unique while preserving order.
    seen = set()
    out: List[str] = []
    for term in expanded:
        term = term.strip()
        if term and term not in seen:
            seen.add(term)
            out.append(term)
    return out


def _food_matches_allergy_terms(food: Dict[str, Any], terms: List[str]) -> bool:
    if not terms:
        return False
    blob = " ".join(
        str(x or "")
        for x in (food.get("name"), food.get("local_name"), food.get("category"), food.get("note"))
    ).lower()
    for t in terms:
        s = (t or "").strip().lower()
        if not s:
            continue
        # Ignore ultra-short fragments to avoid false matches.
        if len(s) <= 2:
            continue
        if s in blob:
            return True
    return False


def filter_foods_by_allergies(
    foods_by_diag: Dict[int, List[Dict[str, Any]]], allergy_terms: List[str]
) -> Dict[int, List[Dict[str, Any]]]:
    if not allergy_terms:
        return foods_by_diag
    cleaned = _expand_allergy_terms([t.strip() for t in allergy_terms if t and str(t).strip()])
    if not cleaned:
        return foods_by_diag
    out: Dict[int, List[Dict[str, Any]]] = {}
    for diag_id, foods in foods_by_diag.items():
        out[diag_id] = [f for f in foods if not _food_matches_allergy_terms(f, cleaned)]
    return out


def parse_allergy_notes(notes: Optional[str]) -> List[str]:
    if not notes:
        return []
    return [p.strip() for p in re.split(r"[,;\n]+", notes) if p.strip()]


def get_common_allergens() -> List[Dict[str, Any]]:
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT id, name FROM common_allergens ORDER BY name")
        rows = cur.fetchall()
    except Exception:
        rows = []
    cur.close()
    conn.close()
    return rows or []


def get_user_allergen_ids(user_id: int) -> List[int]:
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("SELECT allergen_id FROM user_allergens WHERE user_id=%s", (user_id,))
        rows = cur.fetchall()
    except Exception:
        rows = []
    cur.close()
    conn.close()
    return [int(r[0]) for r in rows]


def get_user_allergy_terms(user_id: int) -> List[str]:
    terms: List[str] = []
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            """
            SELECT ca.name
            FROM user_allergens ua
            JOIN common_allergens ca ON ca.id = ua.allergen_id
            WHERE ua.user_id=%s
            """,
            (user_id,),
        )
        for row in cur.fetchall() or []:
            terms.append(str(row["name"]))
    except Exception:
        pass
    try:
        cur.execute("SELECT allergies_notes FROM user_profiles WHERE user_id=%s", (user_id,))
        row = cur.fetchone()
        if row and row.get("allergies_notes"):
            terms.extend(parse_allergy_notes(str(row["allergies_notes"])))
    except Exception:
        pass
    cur.close()
    conn.close()
    seen = set()
    out: List[str] = []
    for t in terms:
        k = t.strip().lower()
        if k and k not in seen:
            seen.add(k)
            out.append(t.strip())
    return out


def log_expert_activity(expert_id: int, action: str, detail: Optional[str] = None) -> None:
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO expert_activity_log (expert_id, action, detail) VALUES (%s,%s,%s)",
            (expert_id, action[:120], detail),
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception:
        pass


def log_admin_audit(admin_user_id: int, action: str, detail: Optional[str] = None) -> None:
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO admin_audit_log (admin_user_id, action, detail) VALUES (%s,%s,%s)",
            (admin_user_id, action[:120], detail),
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception:
        pass


def get_profile(user_id: int) -> Dict[str, Any]:
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM user_profiles WHERE user_id=%s", (user_id,))
    profile = cur.fetchone() or {}
    cur.close()
    conn.close()
    return profile


def get_user_condition_ids(user_id: int) -> List[int]:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT symptom_id FROM user_conditions WHERE user_id=%s", (user_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [int(r[0]) for r in rows]


@app.get("/")
def landing():
    return render_template("landing.html")


@app.get("/dashboard")
def dashboard():
    user = current_user()
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT id, name, description FROM symptoms ORDER BY name")
    symptoms = cur.fetchall()
    cur.close()
    conn.close()

    selected = []
    profile = {}
    common_allergens: List[Dict[str, Any]] = []
    selected_allergen_ids: List[int] = []
    allergy_summary = ""
    if user:
        selected = get_user_condition_ids(user["id"])
        profile = get_profile(user["id"])
        common_allergens = get_common_allergens()
        selected_allergen_ids = get_user_allergen_ids(user["id"])
        parts: List[str] = []
        id_set = set(selected_allergen_ids)
        for row in common_allergens:
            if int(row["id"]) in id_set:
                parts.append(str(row["name"]))
        if profile.get("allergies_notes"):
            parts.append(str(profile["allergies_notes"])[:80] + ("…" if len(str(profile["allergies_notes"])) > 80 else ""))
        allergy_summary = ", ".join(parts) if parts else ""

    return render_template(
        "dashboard.html",
        user=user,
        symptoms=symptoms,
        selected_symptom_ids=set(selected),
        profile=profile,
        common_allergens=common_allergens,
        selected_allergen_ids=set(selected_allergen_ids),
        allergy_summary=allergy_summary,
    )


@app.post("/profile/save")
def profile_save():
    user = require_login()
    if not isinstance(user, dict):
        return user

    age = request.form.get("age") or None
    gender = request.form.get("gender") or None
    weight_kg = request.form.get("weight_kg") or None
    height_m = request.form.get("height_m") or None
    activity_level = request.form.get("activity_level") or None
    diet_preference = request.form.get("diet_preference") or None
    allergies_notes = (request.form.get("allergies_notes") or "").strip() or None
    allergen_ids = []
    for x in request.form.getlist("allergens"):
        try:
            allergen_ids.append(int(x))
        except Exception:
            pass

    bmi_val: Optional[float] = None
    try:
        if weight_kg and height_m:
            bmi_val = float(weight_kg) / (float(height_m) ** 2)
    except Exception:
        bmi_val = None

    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO user_profiles (user_id, age, gender, weight_kg, height_m, bmi, activity_level, diet_preference, allergies_notes)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE
              age=VALUES(age),
              gender=VALUES(gender),
              weight_kg=VALUES(weight_kg),
              height_m=VALUES(height_m),
              bmi=VALUES(bmi),
              activity_level=VALUES(activity_level),
              diet_preference=VALUES(diet_preference),
              allergies_notes=VALUES(allergies_notes)
            """,
            (user["id"], age, gender, weight_kg, height_m, bmi_val, activity_level, diet_preference, allergies_notes),
        )
    except Exception:
        cur.execute(
            """
            INSERT INTO user_profiles (user_id, age, gender, weight_kg, height_m, bmi, activity_level, diet_preference)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE
              age=VALUES(age),
              gender=VALUES(gender),
              weight_kg=VALUES(weight_kg),
              height_m=VALUES(height_m),
              bmi=VALUES(bmi),
              activity_level=VALUES(activity_level),
              diet_preference=VALUES(diet_preference)
            """,
            (user["id"], age, gender, weight_kg, height_m, bmi_val, activity_level, diet_preference),
        )
    try:
        cur.execute("DELETE FROM user_allergens WHERE user_id=%s", (user["id"],))
        if allergen_ids:
            cur.executemany(
                "INSERT INTO user_allergens (user_id, allergen_id) VALUES (%s,%s)",
                [(user["id"], aid) for aid in allergen_ids],
            )
    except Exception:
        pass
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for("dashboard"))


@app.post("/conditions/save")
def conditions_save():
    user = require_login()
    if not isinstance(user, dict):
        return user

    symptom_ids = [int(x) for x in request.form.getlist("symptoms")]
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM user_conditions WHERE user_id=%s", (user["id"],))
    if symptom_ids:
        cur.executemany(
            "INSERT INTO user_conditions (user_id, symptom_id) VALUES (%s,%s)",
            [(user["id"], sid) for sid in symptom_ids],
        )
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for("dashboard"))


@app.post("/recommend")
def recommend():
    user = current_user()

    symptom_ids = [int(x) for x in request.form.getlist("symptoms")]
    if not symptom_ids and user:
        symptom_ids = get_user_condition_ids(user["id"])

    diagnoses = infer_recommendations(symptom_ids)
    diag_ids = [int(d["id"]) for d in diagnoses]
    foods_by_diag = foods_for_diagnoses(diag_ids)
    allergy_terms: List[str] = []
    if user:
        allergy_terms = get_user_allergy_terms(int(user["id"]))
    foods_by_diag = filter_foods_by_allergies(foods_by_diag, allergy_terms)

    bmi_val = request.form.get("bmi") or None
    bmi_cat = request.form.get("bmi_category") or None
    activity_level = request.form.get("activity_level") or None
    diet_preference = request.form.get("diet_preference") or None

    run_id: Optional[int] = None
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO recommendation_runs (user_id, bmi, bmi_category, diet_preference, activity_level)
            VALUES (%s,%s,%s,%s,%s)
            """,
            (user["id"] if user else None, bmi_val, bmi_cat, diet_preference, activity_level),
        )
        run_id = cur.lastrowid
        if run_id and diagnoses:
            cur.executemany(
                """
                INSERT INTO recommendation_run_diagnoses (run_id, diagnosis_id, score)
                VALUES (%s,%s,%s)
                """,
                [(run_id, int(d["id"]), int(d["score"] or 0)) for d in diagnoses],
            )
        conn.commit()
        cur.close()
        conn.close()
    except Exception:
        run_id = None

    return render_template(
        "recommendations.html",
        user=user,
        diagnoses=diagnoses,
        foods_by_diag=foods_by_diag,
        bmi=bmi_val,
        bmi_category=bmi_cat,
        run_id=run_id,
        allergy_filter_active=bool(allergy_terms),
    )


@app.get("/history")
def history():
    user = require_login()
    if not isinstance(user, dict):
        return user

    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute(
        """
        SELECT id, bmi, bmi_category, diet_preference, activity_level, created_at
        FROM recommendation_runs
        WHERE user_id=%s
        ORDER BY created_at DESC
        LIMIT 50
        """,
        (user["id"],),
    )
    runs = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("history.html", user=user, runs=runs)


@app.get("/run/<int:run_id>")
def run_view(run_id: int):
    user = require_login()
    if not isinstance(user, dict):
        return user

    conn = get_db()
    cur = conn.cursor(dictionary=True)

    cur.execute(
        """
        SELECT id, bmi, bmi_category, diet_preference, activity_level
        FROM recommendation_runs
        WHERE id=%s AND user_id=%s
        """,
        (run_id, user["id"]),
    )
    run = cur.fetchone()
    if not run:
        cur.close()
        conn.close()
        abort(404)

    cur.execute(
        """
        SELECT d.id, d.code, d.name, d.description, d.general_advice, rrd.score
        FROM recommendation_run_diagnoses rrd
        JOIN diagnoses d ON d.id = rrd.diagnosis_id
        WHERE rrd.run_id=%s
        ORDER BY rrd.score DESC
        """,
        (run_id,),
    )
    diagnoses = cur.fetchall()

    diag_ids = [int(d["id"]) for d in diagnoses]
    foods_by_diag = foods_for_diagnoses(diag_ids)
    allergy_terms = get_user_allergy_terms(int(user["id"]))
    foods_by_diag = filter_foods_by_allergies(foods_by_diag, allergy_terms)

    cur.close()
    conn.close()

    return render_template(
        "recommendations.html",
        user=user,
        diagnoses=diagnoses,
        foods_by_diag=foods_by_diag,
        bmi=run.get("bmi"),
        bmi_category=run.get("bmi_category"),
        run_id=run.get("id"),
        allergy_filter_active=bool(allergy_terms),
    )


@app.get("/timeline")
def timeline():
    user = require_login()
    if not isinstance(user, dict):
        return user

    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute(
        """
        SELECT rr.id AS run_id, rr.created_at, rrd.score, d.name AS diagnosis_name
        FROM recommendation_runs rr
        JOIN recommendation_run_diagnoses rrd ON rrd.run_id = rr.id
        JOIN diagnoses d ON d.id = rrd.diagnosis_id
        WHERE rr.user_id=%s
        ORDER BY rr.created_at DESC, rrd.score DESC
        LIMIT 200
        """,
        (user["id"],),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("timeline.html", user=user, rows=rows)


@app.get("/login")
def login():
    if current_user():
        return redirect(url_for("dashboard"))
    return render_template("login.html", error=None, next=request.args.get("next") or "")


@app.post("/login")
def login_post():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").encode("utf-8")
    next_url = request.form.get("next") or url_for("dashboard")

    #region agent log
    _debug_log(
        "H1_login_called",
        "app.py:login_post:start",
        "login_post called",
        {"username_present": bool(username), "password_len": len(password)},
    )
    #endregion agent log

    conn = get_db()
    cur = conn.cursor(dictionary=True)
    try:
        # Login supports either username OR email (same input field name).
        cur.execute(
            "SELECT id, username, password_hash, role FROM users WHERE username=%s OR email=%s",
            (username, username),
        )
        user = cur.fetchone()
    except Exception:
        # Fallback for older DBs without users.email column.
        cur.execute("SELECT id, username, password_hash, role FROM users WHERE username=%s", (username,))
        user = cur.fetchone()
    cur.close()
    conn.close()

    #region agent log
    _debug_log(
        "H2_login_user_lookup",
        "app.py:login_post:after_fetch",
        "user lookup result",
        {"user_found": bool(user), "role": user.get("role") if user else None},
    )
    #endregion agent log

    if not user:
        return render_template("login.html", error="Invalid credentials", next=next_url)

    if not bcrypt.checkpw(password, user["password_hash"].encode("utf-8")):
        #region agent log
        _debug_log(
            "H3_login_checkpw",
            "app.py:login_post:checkpw",
            "password check failed",
            {"username": username, "role": user.get("role")},
        )
        #endregion agent log
        return render_template("login.html", error="Invalid credentials", next=next_url)

    #region agent log
    _debug_log(
        "H4_login_checkpw",
        "app.py:login_post:checkpw",
        "password check ok",
        {"username": username, "role": user.get("role")},
    )
    #endregion agent log

    session["user_id"] = int(user["id"])

    #region agent log
    _debug_log(
        "H5_login_session_set",
        "app.py:login_post:session",
        "session user_id set",
        {"user_id": user["id"], "role": user.get("role")},
    )
    #endregion agent log
    return redirect(next_url)


@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.get("/register")
def register():
    if current_user():
        return redirect(url_for("dashboard"))
    return render_template("register.html", error=None)


@app.post("/register")
def register_post():
    username = request.form.get("username", "").strip()
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "").strip()

    #region agent log
    _debug_log(
        "H1_register_called",
        "app.py:register_post:start",
        "register_post called",
        {"username_present": bool(username), "password_len": len(password)},
    )
    #endregion agent log

    if not username or not email or not password:
        #region agent log
        _debug_log(
            "H2_register_missing_fields",
            "app.py:register_post:validate",
            "missing fields",
            {"username_present": bool(username), "password_len": len(password)},
        )
        #endregion agent log
        return render_template("register.html", error="Username, email, and password are required.")
    if len(password) < 6:
        #region agent log
        _debug_log(
            "H3_register_short_password",
            "app.py:register_post:validate",
            "password too short",
            {"password_len": len(password)},
        )
        #endregion agent log
        return render_template("register.html", error="Password must be at least 6 characters.")

    if "@" not in email or "." not in email:
        return render_template("register.html", error="Please enter a valid email address.")

    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    conn = get_db()
    cur = conn.cursor(dictionary=True)
    try:
        # Prevent duplicate emails.
        cur.execute("SELECT id FROM users WHERE email=%s", (email,))
        if cur.fetchone():
            cur.close()
            conn.close()
            return render_template("register.html", error="That email is already in use. Try another one.")
        cur.execute(
            """
            INSERT INTO users (username, email, password_hash, role)
            VALUES (%s,%s,%s,'user')
            ON DUPLICATE KEY UPDATE
              email=VALUES(email),
              password_hash=VALUES(password_hash),
              role='user'
            """,
            (username, email, password_hash),
        )
    except Exception:
        # Fallback for older DBs without users.email column.
        cur.execute(
            """
            INSERT INTO users (username, password_hash, role)
            VALUES (%s,%s,'user')
            ON DUPLICATE KEY UPDATE
              password_hash=VALUES(password_hash),
              role='user'
            """,
            (username, password_hash),
        )
    cur.execute("SELECT id, role FROM users WHERE username=%s", (username,))
    user = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()

    #region agent log
    _debug_log(
        "H4_register_db_result",
        "app.py:register_post:after_insert",
        "register db result",
        {"user_found": bool(user), "role": user.get("role") if user else None},
    )
    #endregion agent log

    session["user_id"] = int(user["id"])
    return redirect(url_for("dashboard"))


@app.get("/consult")
def consult():
    user = require_login()
    if not isinstance(user, dict):
        return user

    conn = get_db()
    cur = conn.cursor(dictionary=True)
    # Social/contact columns may not exist until migration; use fallback selection.
    try:
        cur.execute(
            """
            SELECT id, name, specialty, contact_email, contact_phone,
                   contact_whatsapp, contact_linkedin, contact_facebook, contact_instagram, bio
            FROM experts
            ORDER BY name
            """
        )
    except Exception:
        cur.execute(
            "SELECT id, name, specialty, contact_email, contact_phone, bio FROM experts ORDER BY name"
        )
    experts = cur.fetchall()
    # expert_response column may not exist until migration
    try:
        cur.execute(
            """
            SELECT cr.id, cr.expert_id, e.name AS expert_name, cr.status, cr.user_message,
                   cr.admin_response, cr.expert_response, cr.created_at
            FROM consultation_requests cr
            JOIN experts e ON e.id = cr.expert_id
            WHERE cr.user_id=%s
            ORDER BY cr.created_at DESC
            LIMIT 50
            """,
            (user["id"],),
        )
    except Exception:
        cur.execute(
            """
            SELECT cr.id, cr.expert_id, e.name AS expert_name, cr.status, cr.user_message,
                   cr.admin_response, NULL AS expert_response, cr.created_at
            FROM consultation_requests cr
            JOIN experts e ON e.id = cr.expert_id
            WHERE cr.user_id=%s
            ORDER BY cr.created_at DESC
            LIMIT 50
            """,
            (user["id"],),
        )
    my_requests = cur.fetchall()
    cur.close()
    conn.close()

    return render_template("consult.html", user=user, experts=experts, my_requests=my_requests, error=None)


@app.post("/consult/send")
def consult_send():
    user = require_login()
    if not isinstance(user, dict):
        return user

    expert_id_raw = request.form.get("expert_id")
    message = (request.form.get("message") or "").strip()
    error = None

    try:
        expert_id = int(expert_id_raw)
    except Exception:
        expert_id = None

    if not expert_id:
        error = "Please select a nutrition expert."
    elif not message:
        error = "Please write your question/message."

    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute(
        "SELECT id, name, specialty, contact_email, contact_phone, bio FROM experts ORDER BY name"
    )
    experts = cur.fetchall()
    cur.execute(
        """
        SELECT cr.id, cr.expert_id, e.name AS expert_name, cr.status, cr.user_message,
               cr.admin_response, cr.created_at
        FROM consultation_requests cr
        JOIN experts e ON e.id = cr.expert_id
        WHERE cr.user_id=%s
        ORDER BY cr.created_at DESC
        LIMIT 50
        """,
        (user["id"],),
    )
    my_requests = cur.fetchall()

    if not error:
        cur.execute(
            """
            INSERT INTO consultation_requests (user_id, expert_id, user_message)
            VALUES (%s,%s,%s)
            """,
            (user["id"], expert_id, message),
        )
        conn.commit()
    cur.close()
    conn.close()

    return render_template(
        "consult.html",
        user=user,
        experts=experts,
        my_requests=my_requests,
        error=error,
    )


@app.get("/admin")
def admin():
    user = require_admin()
    if not isinstance(user, dict):
        return user

    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM symptoms ORDER BY name")
    symptoms = cur.fetchall()
    cur.execute("SELECT * FROM diagnoses ORDER BY name")
    diagnoses = cur.fetchall()
    cur.execute("SELECT * FROM foods ORDER BY category, name")
    foods = cur.fetchall()

    cur.execute(
        "SELECT id, name, specialty, contact_email, contact_phone, bio FROM experts ORDER BY name"
    )
    experts = cur.fetchall()

    try:
        cur.execute(
            """
            SELECT cr.id, u.username, e.name AS expert_name, e.specialty, cr.status,
                   cr.user_message, cr.admin_response, cr.expert_response, cr.created_at
            FROM consultation_requests cr
            JOIN users u ON u.id = cr.user_id
            JOIN experts e ON e.id = cr.expert_id
            ORDER BY cr.created_at DESC
            LIMIT 100
            """
        )
    except Exception:
        cur.execute(
            """
            SELECT cr.id, u.username, e.name AS expert_name, e.specialty, cr.status,
                   cr.user_message, cr.admin_response, NULL AS expert_response, cr.created_at
            FROM consultation_requests cr
            JOIN users u ON u.id = cr.user_id
            JOIN experts e ON e.id = cr.expert_id
            ORDER BY cr.created_at DESC
            LIMIT 100
            """
        )
    consultations = cur.fetchall()

    cur.execute(
        """
        SELECT r.id, r.symptom_id, r.diagnosis_id, s.name AS symptom_name, d.name AS diagnosis_name, r.weight
        FROM rules r
        JOIN symptoms s ON s.id = r.symptom_id
        JOIN diagnoses d ON d.id = r.diagnosis_id
        ORDER BY s.name, d.name
        """
    )
    rules = cur.fetchall()

    cur.execute("SELECT id, username, email, role, created_at FROM users ORDER BY id DESC LIMIT 200")
    admin_users = cur.fetchall()

    try:
        cur.execute(
            """
            SELECT e.id AS expert_id, e.name AS expert_name, e.specialty,
                   eu.login_email, eu.login_username,
                   COALESCE(eu.can_manage_kb, 0) AS can_manage_kb, eu.linked_user_id
            FROM experts e
            LEFT JOIN expert_users eu ON eu.expert_id = e.id
            ORDER BY e.name
            """
        )
    except Exception:
        cur.execute(
            """
            SELECT e.id AS expert_id, e.name AS expert_name, e.specialty,
                   eu.login_email, eu.login_username, 0 AS can_manage_kb, NULL AS linked_user_id
            FROM experts e
            LEFT JOIN expert_users eu ON eu.expert_id = e.id
            ORDER BY e.name
            """
        )
    expert_accounts = cur.fetchall()

    stats: Dict[str, int] = {}
    try:
        cur.execute("SELECT COUNT(*) AS c FROM users")
        stats["users"] = int(cur.fetchone()["c"])
        cur.execute("SELECT COUNT(*) AS c FROM foods")
        stats["foods"] = int(cur.fetchone()["c"])
        cur.execute("SELECT COUNT(*) AS c FROM symptoms")
        stats["symptoms"] = int(cur.fetchone()["c"])
        cur.execute("SELECT COUNT(*) AS c FROM diagnoses")
        stats["diagnoses"] = int(cur.fetchone()["c"])
        cur.execute("SELECT COUNT(*) AS c FROM rules")
        stats["rules"] = int(cur.fetchone()["c"])
        cur.execute("SELECT COUNT(*) AS c FROM consultation_requests")
        stats["consultations"] = int(cur.fetchone()["c"])
    except Exception:
        stats = {}

    audit_rows: List[Dict[str, Any]] = []
    try:
        cur.execute(
            """
            SELECT a.id, a.action, a.detail, a.created_at, u.username AS admin_username
            FROM admin_audit_log a
            JOIN users u ON u.id = a.admin_user_id
            ORDER BY a.created_at DESC
            LIMIT 40
            """
        )
        audit_rows = cur.fetchall() or []
    except Exception:
        audit_rows = []

    cur.close()
    conn.close()

    expert_login_rows = any(
        bool(r.get("login_email") or r.get("login_username")) for r in (expert_accounts or [])
    )

    return render_template(
        "admin.html",
        user=user,
        symptoms=symptoms,
        diagnoses=diagnoses,
        foods=foods,
        experts=experts,
        consultations=consultations,
        rules=rules,
        admin_users=admin_users,
        expert_accounts=expert_accounts,
        expert_login_rows=expert_login_rows,
        stats=stats,
        audit_rows=audit_rows,
        error=None,
    )


@app.post("/admin/consultation/update")
def admin_consultation_update():
    user = require_admin()
    if not isinstance(user, dict):
        return user

    request_id_raw = request.form.get("request_id")
    status = request.form.get("status") or "pending"
    admin_response = (request.form.get("admin_response") or "").strip() or None

    try:
        request_id = int(request_id_raw)
    except Exception:
        abort(400)

    if status not in ("pending", "accepted", "rejected", "completed"):
        status = "pending"

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE consultation_requests
        SET status=%s, admin_response=%s
        WHERE id=%s
        """,
        (status, admin_response, request_id),
    )
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for("admin"))


@app.post("/admin/symptom/add")
def admin_symptom_add():
    user = require_admin()
    if not isinstance(user, dict):
        return user

    code = (request.form.get("code") or "").strip() or None
    name = (request.form.get("name") or "").strip()
    description = (request.form.get("description") or "").strip() or None
    if not name:
        abort(400)

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO symptoms (code, name, description) VALUES (%s,%s,%s)",
        (code, name, description),
    )
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for("admin"))


@app.post("/admin/diagnosis/add")
def admin_diagnosis_add():
    user = require_admin()
    if not isinstance(user, dict):
        return user

    code = (request.form.get("code") or "").strip() or None
    name = (request.form.get("name") or "").strip()
    description = (request.form.get("description") or "").strip() or None
    advice = (request.form.get("general_advice") or "").strip() or None
    if not name:
        abort(400)

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO diagnoses (code, name, description, general_advice) VALUES (%s,%s,%s,%s)",
        (code, name, description, advice),
    )
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for("admin"))


@app.post("/admin/food/add")
def admin_food_add():
    user = require_admin()
    if not isinstance(user, dict):
        return user

    name = (request.form.get("name") or "").strip()
    local_name = (request.form.get("local_name") or "").strip() or None
    category = (request.form.get("category") or "").strip() or None
    description = (request.form.get("description") or "").strip() or None
    if not name:
        abort(400)

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO foods (name, local_name, category, description) VALUES (%s,%s,%s,%s)",
        (name, local_name, category, description),
    )
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for("admin"))


@app.post("/admin/rule/add")
def admin_rule_add():
    user = require_admin()
    if not isinstance(user, dict):
        return user

    symptom_id = int(request.form.get("symptom_id"))
    diagnosis_id = int(request.form.get("diagnosis_id"))
    weight = int(request.form.get("weight") or 1)

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO rules (symptom_id, diagnosis_id, weight)
        VALUES (%s,%s,%s)
        ON DUPLICATE KEY UPDATE weight=VALUES(weight)
        """,
        (symptom_id, diagnosis_id, weight),
    )
    conn.commit()
    cur.close()
    conn.close()
    log_admin_audit(int(user["id"]), "rule_add", f"symptom_id={symptom_id} diagnosis_id={diagnosis_id} weight={weight}")
    return redirect(url_for("admin"))


@app.post("/admin/rule/update")
def admin_rule_update():
    user = require_admin()
    if not isinstance(user, dict):
        return user
    try:
        rule_id = int(request.form.get("rule_id"))
        weight = int(request.form.get("weight") or 1)
    except Exception:
        abort(400)
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE rules SET weight=%s WHERE id=%s", (weight, rule_id))
    conn.commit()
    cur.close()
    conn.close()
    log_admin_audit(int(user["id"]), "rule_update", f"rule_id={rule_id} weight={weight}")
    return redirect(url_for("admin"))


@app.post("/admin/rule/delete")
def admin_rule_delete():
    user = require_admin()
    if not isinstance(user, dict):
        return user
    try:
        rule_id = int(request.form.get("rule_id"))
    except Exception:
        abort(400)
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM rules WHERE id=%s", (rule_id,))
    conn.commit()
    cur.close()
    conn.close()
    log_admin_audit(int(user["id"]), "rule_delete", f"rule_id={rule_id}")
    return redirect(url_for("admin"))


@app.post("/admin/user/role")
def admin_user_role():
    admin = require_admin()
    if not isinstance(admin, dict):
        return admin
    try:
        target_id = int(request.form.get("user_id"))
    except Exception:
        abort(400)
    role = (request.form.get("role") or "user").strip()
    if role not in ("user", "admin"):
        role = "user"
    if target_id == int(admin["id"]) and role != "admin":
        return redirect(url_for("admin"))
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE users SET role=%s WHERE id=%s", (role, target_id))
    conn.commit()
    cur.close()
    conn.close()
    log_admin_audit(int(admin["id"]), "user_role_change", f"user_id={target_id} role={role}")
    return redirect(url_for("admin"))


@app.post("/admin/expert/access")
def admin_expert_access():
    admin = require_admin()
    if not isinstance(admin, dict):
        return admin
    try:
        expert_id = int(request.form.get("expert_id"))
    except Exception:
        abort(400)
    can_manage = 1 if request.form.get("can_manage_kb") == "1" else 0
    linked_raw = request.form.get("linked_user_id") or ""
    linked_user_id: Optional[int] = None
    if linked_raw.strip():
        try:
            linked_user_id = int(linked_raw)
        except Exception:
            linked_user_id = None
    grant_admin = request.form.get("grant_site_admin") == "1"

    conn = get_db()
    cur = conn.cursor()
    try:
        if linked_user_id:
            cur.execute(
                "UPDATE expert_users SET linked_user_id=NULL WHERE linked_user_id=%s AND expert_id<>%s",
                (linked_user_id, expert_id),
            )
        cur.execute(
            """
            UPDATE expert_users
            SET can_manage_kb=%s, linked_user_id=%s
            WHERE expert_id=%s
            """,
            (can_manage, linked_user_id, expert_id),
        )
        if grant_admin and linked_user_id:
            cur.execute("UPDATE users SET role='admin' WHERE id=%s", (linked_user_id,))
    except Exception:
        conn.rollback()
        cur.close()
        conn.close()
        return redirect(url_for("admin"))
    conn.commit()
    cur.close()
    conn.close()
    log_admin_audit(
        int(admin["id"]),
        "expert_access_update",
        f"expert_id={expert_id} can_manage_kb={can_manage} linked_user_id={linked_user_id} grant_admin={int(grant_admin)}",
    )
    return redirect(url_for("admin"))


# ---------------------------
# Expert dashboard & login
# ---------------------------


@app.get("/expert/login")
def expert_login():
    if session.get("expert_id"):
        return redirect(url_for("expert_dashboard"))
    return render_template("expert_login.html", error=None, next=request.args.get("next") or "")


@app.post("/expert/login")
def expert_login_post():
    login_value = request.form.get("login", "").strip()
    password = request.form.get("password", "").encode("utf-8")
    next_url = request.form.get("next") or url_for("expert_dashboard")

    if not login_value or not password:
        return render_template("expert_login.html", error="Login and password are required.", next=next_url)

    conn = get_db()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            """
            SELECT eu.expert_id, eu.password_hash, e.name, e.specialty
            FROM expert_users eu
            JOIN experts e ON e.id = eu.expert_id
            WHERE eu.login_email=%s OR eu.login_username=%s
            """,
            (login_value, login_value),
        )
    except Exception:
        cur.close()
        conn.close()
        return render_template(
            "expert_login.html",
            error="Expert accounts are not configured yet. Please ask the admin to run the expert account setup.",
            next=next_url,
        )

    expert_row = cur.fetchone()
    cur.close()
    conn.close()

    if not expert_row:
        return render_template("expert_login.html", error="Invalid login credentials.", next=next_url)

    if not bcrypt.checkpw(password, expert_row["password_hash"].encode("utf-8")):
        return render_template("expert_login.html", error="Invalid login credentials.", next=next_url)

    session.clear()
    session["expert_id"] = int(expert_row["expert_id"])
    return redirect(next_url)


@app.get("/expert/logout")
def expert_logout():
    session.pop("expert_id", None)
    return redirect(url_for("landing"))


@app.get("/expert/dashboard")
def expert_dashboard():
    expert = require_expert_login()
    if not isinstance(expert, dict):
        return expert

    status = request.args.get("status", "all")
    q = (request.args.get("q") or "").strip()

    conn = get_db()
    cur = conn.cursor(dictionary=True)

    base_where = ["cr.expert_id=%s"]
    params: List[Any] = [expert["id"]]
    if status and status != "all":
        base_where.append("cr.status=%s")
        params.append(status)
    if q:
        base_where.append("(u.username LIKE %s OR cr.user_message LIKE %s)")
        like = f"%{q}%"
        params.extend([like, like])

    where_sql = " AND ".join(base_where)

    # expert_response column may not exist until migration; try-select with fallback
    try:
        cur.execute(
            f"""
            SELECT cr.id, u.username, cr.status, cr.user_message,
                   cr.admin_response, cr.expert_response, cr.created_at
            FROM consultation_requests cr
            JOIN users u ON u.id = cr.user_id
            WHERE {where_sql}
            ORDER BY cr.created_at DESC
            LIMIT 200
            """,
            tuple(params),
        )
    except Exception:
        cur.execute(
            f"""
            SELECT cr.id, u.username, cr.status, cr.user_message,
                   cr.admin_response, NULL AS expert_response, cr.created_at
            FROM consultation_requests cr
            JOIN users u ON u.id = cr.user_id
            WHERE {where_sql}
            ORDER BY cr.created_at DESC
            LIMIT 200
            """,
            tuple(params),
        )

    requests = cur.fetchall()
    cur.close()
    conn.close()

    return render_template("expert_dashboard.html", expert=expert, requests=requests, status=status, q=q, error=None)


@app.post("/expert/consultation/update")
def expert_consultation_update():
    expert = require_expert_login()
    if not isinstance(expert, dict):
        return expert

    request_id_raw = request.form.get("request_id")
    status = request.form.get("status") or "completed"
    expert_response = (request.form.get("expert_response") or "").strip() or None

    try:
        request_id = int(request_id_raw)
    except Exception:
        abort(400)

    conn = get_db()
    cur = conn.cursor()
    # Update expert_response if column exists (migration), otherwise update only status.
    try:
        cur.execute(
            """
            UPDATE consultation_requests
            SET status=%s, expert_response=%s
            WHERE id=%s AND expert_id=%s
            """,
            (status, expert_response, request_id, expert["id"]),
        )
    except Exception:
        cur.execute(
            """
            UPDATE consultation_requests
            SET status=%s
            WHERE id=%s AND expert_id=%s
            """,
            (status, request_id, expert["id"]),
        )
    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("expert_dashboard"))


@app.get("/expert/knowledge")
def expert_knowledge():
    expert = require_expert_kb()
    if not isinstance(expert, dict):
        return expert

    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM symptoms ORDER BY name")
    symptoms = cur.fetchall()
    cur.execute("SELECT * FROM diagnoses ORDER BY name")
    diagnoses = cur.fetchall()
    cur.execute("SELECT * FROM foods ORDER BY category, name")
    foods = cur.fetchall()
    cur.execute(
        """
        SELECT r.id, r.symptom_id, r.diagnosis_id, s.name AS symptom_name, d.name AS diagnosis_name, r.weight
        FROM rules r
        JOIN symptoms s ON s.id = r.symptom_id
        JOIN diagnoses d ON d.id = r.diagnosis_id
        ORDER BY s.name, d.name
        """
    )
    rules = cur.fetchall()
    activity: List[Dict[str, Any]] = []
    try:
        cur.execute(
            """
            SELECT id, action, detail, created_at
            FROM expert_activity_log
            WHERE expert_id=%s
            ORDER BY created_at DESC
            LIMIT 40
            """,
            (expert["id"],),
        )
        activity = cur.fetchall() or []
    except Exception:
        activity = []
    cur.close()
    conn.close()

    return render_template(
        "expert_knowledge.html",
        expert=expert,
        symptoms=symptoms,
        diagnoses=diagnoses,
        foods=foods,
        rules=rules,
        activity=activity,
    )


def _expert_kb_post_redirect():
    return redirect(url_for("expert_knowledge"))


@app.post("/expert/symptom/add")
def expert_symptom_add():
    expert = require_expert_kb()
    if not isinstance(expert, dict):
        return expert

    code = (request.form.get("code") or "").strip() or None
    name = (request.form.get("name") or "").strip()
    description = (request.form.get("description") or "").strip() or None
    if not name:
        abort(400)

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO symptoms (code, name, description) VALUES (%s,%s,%s)",
        (code, name, description),
    )
    conn.commit()
    cur.close()
    conn.close()
    log_expert_activity(int(expert["id"]), "symptom_add", name)
    return _expert_kb_post_redirect()


@app.post("/expert/diagnosis/add")
def expert_diagnosis_add():
    expert = require_expert_kb()
    if not isinstance(expert, dict):
        return expert

    code = (request.form.get("code") or "").strip() or None
    name = (request.form.get("name") or "").strip()
    description = (request.form.get("description") or "").strip() or None
    advice = (request.form.get("general_advice") or "").strip() or None
    if not name:
        abort(400)

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO diagnoses (code, name, description, general_advice) VALUES (%s,%s,%s,%s)",
        (code, name, description, advice),
    )
    conn.commit()
    cur.close()
    conn.close()
    log_expert_activity(int(expert["id"]), "diagnosis_add", name)
    return _expert_kb_post_redirect()


@app.post("/expert/food/add")
def expert_food_add():
    expert = require_expert_kb()
    if not isinstance(expert, dict):
        return expert

    name = (request.form.get("name") or "").strip()
    local_name = (request.form.get("local_name") or "").strip() or None
    category = (request.form.get("category") or "").strip() or None
    description = (request.form.get("description") or "").strip() or None
    if not name:
        abort(400)

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO foods (name, local_name, category, description) VALUES (%s,%s,%s,%s)",
        (name, local_name, category, description),
    )
    conn.commit()
    cur.close()
    conn.close()
    log_expert_activity(int(expert["id"]), "food_add", name)
    return _expert_kb_post_redirect()


@app.post("/expert/rule/add")
def expert_rule_add():
    expert = require_expert_kb()
    if not isinstance(expert, dict):
        return expert

    symptom_id = int(request.form.get("symptom_id"))
    diagnosis_id = int(request.form.get("diagnosis_id"))
    weight = int(request.form.get("weight") or 1)

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO rules (symptom_id, diagnosis_id, weight)
        VALUES (%s,%s,%s)
        ON DUPLICATE KEY UPDATE weight=VALUES(weight)
        """,
        (symptom_id, diagnosis_id, weight),
    )
    conn.commit()
    cur.close()
    conn.close()
    log_expert_activity(
        int(expert["id"]),
        "rule_add",
        f"symptom_id={symptom_id} diagnosis_id={diagnosis_id} weight={weight}",
    )
    return _expert_kb_post_redirect()


@app.post("/expert/rule/update")
def expert_rule_update():
    expert = require_expert_kb()
    if not isinstance(expert, dict):
        return expert
    try:
        rule_id = int(request.form.get("rule_id"))
        weight = int(request.form.get("weight") or 1)
    except Exception:
        abort(400)
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE rules SET weight=%s WHERE id=%s", (weight, rule_id))
    conn.commit()
    cur.close()
    conn.close()
    log_expert_activity(int(expert["id"]), "rule_update", f"rule_id={rule_id} weight={weight}")
    return _expert_kb_post_redirect()


@app.post("/expert/rule/delete")
def expert_rule_delete():
    expert = require_expert_kb()
    if not isinstance(expert, dict):
        return expert
    try:
        rule_id = int(request.form.get("rule_id"))
    except Exception:
        abort(400)
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM rules WHERE id=%s", (rule_id,))
    conn.commit()
    cur.close()
    conn.close()
    log_expert_activity(int(expert["id"]), "rule_delete", f"rule_id={rule_id}")
    return _expert_kb_post_redirect()


@app.errorhandler(403)
def forbidden(_e):
    return render_template("error.html", title="Forbidden", message="You don't have access to this page."), 403


@app.errorhandler(404)
def not_found(_e):
    return render_template("error.html", title="Not found", message="Page not found."), 404


if __name__ == "__main__":
    app.run(debug=True)

