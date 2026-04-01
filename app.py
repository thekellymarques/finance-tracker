import os
from functools import wraps
from werkzeug.security import check_password_hash, generate_password_hash

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
import flask_session


app = Flask(__name__)

app.config["TEMPLATES_AUTO_RELOAD"] = True

# configure session to use filesystem instead of signed cookies
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
flask_session.Session(app)

# configure CS50 library to use SQLite database
db = SQL("sqlite:///finance.db")

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function

@app.after_request
def after_request(response):
    # ensure responses aren't cached
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["PRAGMA"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    user_id = session["user_id"]
    selected_month = request.args.get("month")

    if selected_month:
        transactions = db.execute(
            """
            SELECT 
                transactions.id,
                transactions.type,
                transactions.amount_cents,
                transactions.description,
                transactions.date,
                categories.name AS category_name
            FROM transactions
            LEFT JOIN categories 
                ON transactions.category_id = categories.id
            WHERE transactions.user_id = ?
            AND transactions.date LIKE ?
            ORDER BY transactions.date DESC, transactions.id DESC
            """,
        user_id,
        selected_month + "%"
        )
    else:
        transactions = db.execute(
            """
            SELECT 
                transactions.id,
                transactions.type,
                transactions.amount_cents,
                transactions.description,
                transactions.date,
                categories.name AS category_name
            FROM transactions
            LEFT JOIN categories 
                ON transactions.category_id = categories.id
            WHERE transactions.user_id = ?
            ORDER BY transactions.date DESC, transactions.id DESC
            """,
            user_id
        )

    income_cents = 0
    expense_cents = 0

    for transaction in transactions:
        transaction["amount"] = f"{transaction['amount_cents'] / 100:.2f}"

        if transaction["type"] == "income":
            income_cents += transaction["amount_cents"]
        elif transaction["type"] == "expense":
            expense_cents += transaction["amount_cents"]
    
    balance_cents = income_cents - expense_cents

    income = f"{income_cents / 100:.2f}"
    expenses = f"{expense_cents / 100:.2f}"
    balance = f"{balance_cents / 100:.2f}"

    return render_template(
        "index.html", 
        transactions=transactions,
        income=income,
        expenses=expenses,
        balance=balance
        )

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")

    username = request.form.get("username")
    password = request.form.get("password")
    confirmation = request.form.get("confirmation")

    if not username:
        flash("You must provide a username.")
        return redirect("/register")
    if not password:
        flash("You must provide a password.")
        return redirect("/register")
    if password != confirmation:
        flash("Passwords don't match.")
        return redirect("/register")
    
    hash_password = generate_password_hash(password)

    try:
        db.execute(
            "INSERT INTO users (username, hash) VALUES (?, ?)",
            username, 
            hash_password
        )
    except:
        flash("Username already exists.")
        return redirect("/register")
    flash("Registered successfully. Please login.")
    return redirect("/login")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")
    
    username = request.form.get("username")
    password = request.form.get("password")

    if not username:
        flash("You must provide a username.")
        return redirect("/login")
    if not password:
        flash("You must provide a password.")
        return redirect("/login")
    
    rows = db.execute(
        "SELECT * FROM users WHERE username = ?",
        username
    )

    if len(rows) != 1 or not check_password_hash(rows[0]["hash"], password):
        flash("Invalid username or password.")
        return redirect("/login")
        
    session["user_id"] = rows[0]["id"]

    flash("Logged in successfully.")

    return redirect("/")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.")
    return redirect("/login")

@app.route("/add", methods=["GET", "POST"])
@login_required
def add():
    user_id = session["user_id"]

    if request.method == "GET":
        categories = db.execute(
            "SELECT * FROM categories WHERE user_id = ? ORDER BY name",
            user_id
        )
        return render_template("add.html", categories=categories)


    type_ = request.form.get("type")
    amount = request.form.get("amount")
    description = request.form.get("description")
    date = request.form.get("date")
    category_id = request.form.get("category_id")

    if not type_:
        flash("You must select a type.")
        return redirect("/add")

    if type_ not in ["income", "expenses"]:
        flash("Invalid transaction type.")
        return redirect("/add")

    if not amount:
        flash("You must provide an amount.")
        return redirect("/add")

    if not date:
        flash("You must provide a date.")
        return redirect("/add")
    
    if not category_id:
        flash("You must select a category.")
        return redirect("/add")

    try:
        amount_value = float(amount)
    except ValueError:
        flash("Amount must be a valid number.")
        return redirect("/add")

    if amount_value <= 0:
        flash("Amount must be greater than 0.")
        return redirect("/add")

    amount_cents = int(amount_value * 100)

    selected_category = db.execute(
        "SELECT * FROM categories WHERE id = ? AND user_id = ?",
        category_id,
        user_id
    )
    if not selected_category:
        flash("Invalid category selected.")
        return redirect("/add")

    db.execute(
        """
        INSERT INTO transactions (user_id, category_id, type, amount_cents, description, date)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        user_id, category_id, type_, amount_cents, description, date
    )

    flash("Transaction added successfully.")
    return redirect("/")

@app.route("/delete/<int:transaction_id>", methods=["POST"])
@login_required
def delete(transaction_id):
    user_id = session["user_id"]

    db.execute(
        "DELETE FROM transactions WHERE id = ? AND user_id = ?",
        transaction_id, 
        user_id
    )
    flash("Transaction deleted successfully.")
    return redirect("/")

@app.route("/edit/<int:transaction_id>", methods=["GET", "POST"])
@login_required
def edit(transaction_id):
    user_id = session["user_id"]

    rows = db.execute(
        """
            SELECT id, type, description, category_id, amount_cents, date
            FROM transactions
            WHERE id = ? AND user_id = ?
        """,
        transaction_id,
        user_id
    )

    if len(rows) != 1:
        flash("Transaction not found")
        return redirect("/")
    
    transaction = rows[0]
    transaction["amount"] = f"{transaction['amount_cents'] / 100:.2f}"

    if request.method == "GET":
        categories = db.execute(
        "SELECT * FROM categories WHERE user_id = ? ORDER BY name",
        user_id
    )
        return render_template(
            "edit.html", 
            transaction=transaction,
            categories=categories
        )
    
    type_ = request.form.get("type")
    amount = request.form.get("amount")
    description = request.form.get("description")
    date = request.form.get("date")
    category_id = request.form.get("category_id")

    if not type_:
        flash("You must select a type.")
        return redirect(f"/edit/{transaction_id}")
    
    if type_ not in ["income", "expenses"]:
        flash("Invalid transaction type.")
        return redirect(f"/edit/{transaction_id}")
    
    if not amount:
        flash("You must provide an amount.")
        return redirect(f"/edit/{transaction_id}")
    
    if not date:
        flash("You must provide a date.")
        return redirect(f"/edit/{transaction_id}")
    
    if not category_id:
        flash("You must select a category.")
        return redirect(f"/edit/{transaction_id}")
    
    try:
        category_id = int(category_id)
    except ValueError:
        flash("Invalid category selected.")
        return redirect(f"/edit/{transaction_id}")
    
    selected_category = db.execute(
        "SELECT * FROM categories WHERE id = ? AND user_id = ?",
        category_id,
        user_id
    )

    if not selected_category:
        flash("Invalid category selected.")
        return redirect(f"/edit/{transaction_id}")
    
    try:
        amount_value = float(amount)
    except ValueError:
        flash("Amount must be a valid number.")
        return redirect(f"/edit/{transaction_id}")
    
    if amount_value <= 0:
        flash("Amount must be greater than 0.")
        return redirect(f"/edit/{transaction_id}")
    
    amount_cents = int(amount_value * 100)

    db.execute(
            """
            UPDATE transactions
            SET  category_id = ?, type = ?, amount_cents = ?, description = ?, date = ?
            WHERE id = ? AND user_id = ?
            """,
            category_id,
            type_,
            amount_cents,
            description,
            date,
            transaction_id,
            user_id
        )
    flash("Transaction updated successfully.")
    return redirect("/")

@app.route("/categories", methods=["GET", "POST"])
@login_required
def categories():
    user_id = session["user_id"]

    if request.method == "POST":
        name = request.form.get("name")

        if not name or not name.strip(): 
            flash("Category name is required.")
            return redirect("/categories")
        
        name = name.strip()

        existing_category = db.execute(
            "SELECT * FROM categories WHERE user_id = ? AND name = ?",
            user_id,
            name
        )

        if existing_category:
            flash("You already have a category with that name.")
            return redirect("/categories")


        db.execute(
            "INSERT INTO categories (user_id, name) VALUES (?, ?)",
            user_id,
            name
        )

        flash("Category added successfully.")
        return redirect("/categories")
    
    categories = db.execute(
        "SELECT * FROM categories WHERE user_id = ? ORDER BY name",
        user_id
    )

    return render_template("categories.html", categories=categories)




