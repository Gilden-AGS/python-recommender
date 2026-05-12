## Nutrition & Diet Recommendation System (Python + MySQL/XAMPP)

### What this is
This folder contains a **Flask (Python)** recommendation system that uses **MySQL (XAMPP)** and a **HTML/CSS/JavaScript** UI inspired by your screenshots:
- Landing page (dark marketing page)
- User dashboard (health profile cards, condition chips)
- Recommendations page
- Timeline/History (saved recommendation runs)
- Admin panel (manage symptoms, diagnoses, foods, and rules)

### Prerequisites
- XAMPP installed
- MySQL running in XAMPP
- Python 3.10+ installed

### 1) Create database
Open `http://localhost/phpmyadmin` → SQL tab and run:

1. `schema.sql`
2. (optional) `seed.sql`

If you already created the database earlier, you can run this migration instead:
- `migration_v6_email_expert_weight_gain_foods.sql`

### 2) Install and run backend
From this folder:

```bash
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
python create_admin.py
python create_expert_accounts.py
python app.py
```

Open:
- Landing: `http://127.0.0.1:5000/`
- Dashboard: `http://127.0.0.1:5000/dashboard`
- Register: `http://127.0.0.1:5000/register`
- Admin: `http://127.0.0.1:5000/admin`
- Consult: `http://127.0.0.1:5000/consult`
- Expert login: `http://127.0.0.1:5000/expert/login`

### Default admin
When you run `python create_admin.py`, it will create:
- username: `admin`
- password: `admin12345`

Change it after first login.

