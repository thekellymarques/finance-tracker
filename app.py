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
    print("DEBUG: index route reached")
    return render_template("index.html")

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