
from flask import Blueprint, request, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash
from database.models import db, User
import re

auth_bp = Blueprint(
    "auth",
    __name__,
    url_prefix="/api/auth"
)


# USER REGISTRATION
@auth_bp.route("/register", methods=["POST"])
def register():

    data = request.get_json(silent=True) or {}

    username = str(data.get("username", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))

    if not username or not email or not password:
        return jsonify({
            "success": False,
            "message": "Username, email and password are required."
        }), 400

    if len(username) < 3 or len(username) > 80:
        return jsonify({
            "success": False,
            "message": "Username must contain 3 to 80 characters."
        }), 400

    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return jsonify({
            "success": False,
            "message": "Enter a valid email address."
        }), 400

    if len(password) < 8:
        return jsonify({
            "success": False,
            "message": "Password must contain at least 8 characters."
        }), 400

    if User.query.filter_by(username=username).first():
        return jsonify({
            "success": False,
            "message": "Username already exists."
        }), 409

    if User.query.filter_by(email=email).first():
        return jsonify({
            "success": False,
            "message": "Email already registered."
        }), 409

    user = User(
        username=username,
        email=email,
        password_hash=generate_password_hash(password),
        role="user"
    )

    try:
        db.session.add(user)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": "User registered successfully.",
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role
            }
        }), 201

    except Exception:
        db.session.rollback()

        return jsonify({
            "success": False,
            "message": "Registration failed."
        }), 500


# USER LOGIN
@auth_bp.route("/login", methods=["POST"])
def login():

    data = request.get_json(silent=True) or {}

    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))

    if not username or not password:
        return jsonify({
            "success": False,
            "message": "Username and password are required."
        }), 400

    user = User.query.filter_by(username=username).first()

    if not user or not check_password_hash(
        user.password_hash,
        password
    ):
        return jsonify({
            "success": False,
            "message": "Invalid username or password."
        }), 401

    session.clear()

    session["user_id"] = user.id
    session["username"] = user.username
    session["role"] = user.role
    session.permanent = True

    return jsonify({
        "success": True,
        "message": "Login successful.",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role
        }
    }), 200


# USER LOGOUT
@auth_bp.route("/logout", methods=["POST"])
def logout():

    session.clear()

    return jsonify({
        "success": True,
        "message": "Logout successful."
    })


# CURRENT LOGGED-IN USER
@auth_bp.route("/me", methods=["GET"])
def current_user():

    user_id = session.get("user_id")

    if not user_id:
        return jsonify({
            "success": False,
            "message": "User is not logged in."
        }), 401

    user = db.session.get(User, user_id)

    if not user:
        session.clear()

        return jsonify({
            "success": False,
            "message": "User account not found."
        }), 401

    return jsonify({
        "success": True,
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role
        }
    })


# LIST USERS - ADMIN ONLY
@auth_bp.route("/users", methods=["GET"])
def get_users():

    if session.get("role") != "admin":
        return jsonify({
            "success": False,
            "message": "Administrator access required."
        }), 403

    users = User.query.order_by(User.id).all()

    return jsonify({
        "success": True,
        "count": len(users),
        "users": [
            {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "created_at": (
                    user.created_at.isoformat()
                    if user.created_at else None
                )
            }
            for user in users
        ]
    })
