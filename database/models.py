
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import UniqueConstraint

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="user")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Student(db.Model):
    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    class_name = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    attendance_records = db.relationship(
        "Attendance", backref="student", lazy=True
    )
    engagement_records = db.relationship(
        "EngagementScore", backref="student", lazy=True
    )
    expression_records = db.relationship(
        "ExpressionHistory", backref="student", lazy=True
    )


class Attendance(db.Model):
    __tablename__ = "attendance"

    __table_args__ = (
        UniqueConstraint(
            "student_id",
            "date",
            name="unique_student_attendance"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(
        db.Integer, db.ForeignKey("students.id"), nullable=False
    )
    date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default="Present")
    recorded_at = db.Column(db.DateTime, default=datetime.utcnow)


class ExpressionHistory(db.Model):
    __tablename__ = "expression_history"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(
        db.Integer, db.ForeignKey("students.id"), nullable=False
    )
    expression = db.Column(db.String(30), nullable=False)
    confidence = db.Column(db.Float)
    recorded_at = db.Column(db.DateTime, default=datetime.utcnow)


class EngagementScore(db.Model):
    __tablename__ = "engagement_scores"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(
        db.Integer, db.ForeignKey("students.id"), nullable=False
    )
    score = db.Column(db.Float, nullable=False)
    engagement_level = db.Column(db.String(30))
    recorded_at = db.Column(db.DateTime, default=datetime.utcnow)
