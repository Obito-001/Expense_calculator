"""
SpendWise — Expense Management System
Flask + MySQL | Professional Build
"""

import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
import mysql.connector
from mysql.connector import pooling
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

# Load .env in development
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ─────────────────────────────────────────────
# App
# ─────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-before-deploying")

# ─────────────────────────────────────────────
# Database — connection pool
# ─────────────────────────────────────────────
DB_CONFIG = {
    "host":     os.environ.get("DB_HOST",     "yamabiko.proxy.rlwy.net"),
    "user":     os.environ.get("DB_USER",     "root"),
    "password": os.environ.get("DB_PASSWORD", ""),
    "database": os.environ.get("DB_NAME",     "railway"),
    "port":     int(os.environ.get("DB_PORT", 46914)),
}

connection_pool = pooling.MySQLConnectionPool(
    pool_name="spendwise_pool",
    pool_size=5,
    **DB_CONFIG
)

def get_db():
    return connection_pool.get_connection()


# ─────────────────────────────────────────────
# Schema bootstrap
# ─────────────────────────────────────────────
def init_db():
    conn   = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id  INT PRIMARY KEY AUTO_INCREMENT,
            username VARCHAR(50)  NOT NULL,
            email    VARCHAR(100) NOT NULL UNIQUE,
            password VARCHAR(255) NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            expense_id   INT PRIMARY KEY AUTO_INCREMENT,
            user_id      INT           NOT NULL,
            title        VARCHAR(100)  NOT NULL,
            amount       DECIMAL(10,2) NOT NULL,
            category     VARCHAR(50)   NOT NULL,
            expense_date DATE          NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        )
    """)
    conn.commit()
    cursor.close()
    conn.close()


# ─────────────────────────────────────────────
# Auth decorator
# ─────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


# ─────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────

@app.route("/")
def home():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


# ── Register ──────────────────────────────────
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        email    = request.form["email"].strip().lower()
        password = request.form["password"]

        if not all([username, email, password]):
            flash("All fields are required.", "danger")
            return render_template("register.html")

        hashed = generate_password_hash(password)
        try:
            conn   = get_db()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (username, email, password) VALUES (%s, %s, %s)",
                (username, email, hashed)
            )
            conn.commit()
            flash("Account created! Please sign in.", "success")
            return redirect(url_for("login"))
        except mysql.connector.IntegrityError:
            flash("That email is already registered.", "danger")
        finally:
            cursor.close()
            conn.close()

    return render_template("register.html")


# ── Login ─────────────────────────────────────
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email    = request.form["email"].strip().lower()
        password = request.form["password"]

        conn   = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"]  = user["user_id"]
            session["username"] = user["username"]
            return redirect(url_for("dashboard"))

        flash("Invalid email or password.", "danger")

    return render_template("login.html")


# ── Logout ────────────────────────────────────
@app.route("/logout")
def logout():
    session.clear()
    flash("You've been logged out.", "info")
    return redirect(url_for("login"))


# ── Add Expense ───────────────────────────────
@app.route("/expense", methods=["GET", "POST"])
@login_required
def expense():
    if request.method == "POST":
        title        = request.form["title"].strip()
        amount       = request.form["amount"]
        category     = request.form["category"]
        expense_date = request.form["expense_date"]

        if not all([title, amount, category, expense_date]):
            flash("All fields are required.", "danger")
            return render_template("expense.html")

        conn   = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO expenses (user_id, title, amount, category, expense_date) "
            "VALUES (%s, %s, %s, %s, %s)",
            (session["user_id"], title, amount, category, expense_date)
        )
        conn.commit()
        cursor.close()
        conn.close()
        flash("Expense added!", "success")
        return redirect(url_for("view_expenses"))

    return render_template("expense.html")


# ── View Expenses ─────────────────────────────
@app.route("/view_expenses")
@login_required
def view_expenses():
    conn   = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT * FROM expenses WHERE user_id = %s ORDER BY expense_date DESC",
        (session["user_id"],)
    )
    expenses = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template("view_expenses.html", expenses=expenses)


# ── Edit Expense ──────────────────────────────
@app.route("/edit/<int:expense_id>", methods=["GET", "POST"])
@login_required
def edit_expense(expense_id):
    conn   = get_db()
    cursor = conn.cursor(dictionary=True)

    if request.method == "POST":
        title        = request.form["title"].strip()
        amount       = request.form["amount"]
        category     = request.form["category"]
        expense_date = request.form["expense_date"]

        cursor.execute(
            "UPDATE expenses SET title=%s, amount=%s, category=%s, expense_date=%s "
            "WHERE expense_id=%s AND user_id=%s",
            (title, amount, category, expense_date, expense_id, session["user_id"])
        )
        conn.commit()
        cursor.close()
        conn.close()
        flash("Expense updated.", "success")
        return redirect(url_for("view_expenses"))

    cursor.execute(
        "SELECT * FROM expenses WHERE expense_id = %s AND user_id = %s",
        (expense_id, session["user_id"])
    )
    exp = cursor.fetchone()
    cursor.close()
    conn.close()

    if not exp:
        flash("Expense not found.", "danger")
        return redirect(url_for("view_expenses"))

    return render_template("edit_expense.html", expense=exp)


# ── Delete Expense ────────────────────────────
@app.route("/delete/<int:expense_id>")
@login_required
def delete_expense(expense_id):
    conn   = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM expenses WHERE expense_id = %s AND user_id = %s",
        (expense_id, session["user_id"])
    )
    conn.commit()
    cursor.close()
    conn.close()
    flash("Expense deleted.", "info")
    return redirect(url_for("view_expenses"))


# ── Dashboard ─────────────────────────────────
@app.route("/dashboard")
@login_required
def dashboard():
    conn   = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE user_id = %s",
        (session["user_id"],)
    )
    total = float(cursor.fetchone()[0])

    cursor.execute(
        "SELECT COUNT(*) FROM expenses WHERE user_id = %s",
        (session["user_id"],)
    )
    count = cursor.fetchone()[0]

    cursor.execute(
        "SELECT category, SUM(amount) FROM expenses "
        "WHERE user_id = %s GROUP BY category ORDER BY SUM(amount) DESC",
        (session["user_id"],)
    )
    category_data = cursor.fetchall()

    cursor.close()
    conn.close()

    category_labels  = [row[0] for row in category_data]
    category_amounts = [float(row[1]) for row in category_data]

    return render_template(
        "dashboard.html",
        total=total,
        count=count,
        category_data=category_data,
        category_labels=category_labels,
        category_amounts=category_amounts,
    )


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────
if __name__ == "__main__":
    init_db()
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)), debug=debug)
