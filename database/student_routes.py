
from flask import Blueprint, request, jsonify
from sqlalchemy.exc import IntegrityError

from database.models import db, Student

student_bp = Blueprint("students", __name__, url_prefix="/api/students")


# ADD STUDENT
@student_bp.route("/", methods=["POST"])
def add_student():
    data = request.get_json(silent=True) or {}

    student_id = str(data.get("student_id", "")).strip()
    name = str(data.get("name", "")).strip()
    class_name = str(data.get("class_name", "")).strip()

    if not student_id or not name:
        return jsonify({
            "success": False,
            "message": "Student ID and name are required."
        }), 400

    student = Student(
        student_id=student_id,
        name=name,
        class_name=class_name or None
    )

    try:
        db.session.add(student)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Student added successfully.",
            "student": {
                "id": student.id,
                "student_id": student.student_id,
                "name": student.name,
                "class_name": student.class_name
            }
        }), 201

    except IntegrityError:
        db.session.rollback()
        return jsonify({
            "success": False,
            "message": "This student ID already exists."
        }), 409


# VIEW ALL STUDENTS
@student_bp.route("/", methods=["GET"])
def get_students():
    students = Student.query.order_by(Student.id.desc()).all()

    return jsonify({
        "success": True,
        "count": len(students),
        "students": [
            {
                "id": s.id,
                "student_id": s.student_id,
                "name": s.name,
                "class_name": s.class_name
            }
            for s in students
        ]
    })


# VIEW ONE STUDENT
@student_bp.route("/<int:student_id>", methods=["GET"])
def get_student(student_id):
    student = db.session.get(Student, student_id)

    if student is None:
        return jsonify({
            "success": False,
            "message": "Student not found."
        }), 404

    return jsonify({
        "success": True,
        "student": {
            "id": student.id,
            "student_id": student.student_id,
            "name": student.name,
            "class_name": student.class_name
        }
    })


# UPDATE STUDENT
@student_bp.route("/<int:student_id>", methods=["PUT"])
def update_student(student_id):
    student = db.session.get(Student, student_id)

    if student is None:
        return jsonify({
            "success": False,
            "message": "Student not found."
        }), 404

    data = request.get_json(silent=True) or {}

    if "student_id" in data:
        new_id = str(data["student_id"]).strip()
        if not new_id:
            return jsonify({
                "success": False,
                "message": "Student ID cannot be empty."
            }), 400
        student.student_id = new_id

    if "name" in data:
        new_name = str(data["name"]).strip()
        if not new_name:
            return jsonify({
                "success": False,
                "message": "Name cannot be empty."
            }), 400
        student.name = new_name

    if "class_name" in data:
        student.class_name = str(data["class_name"]).strip() or None

    try:
        db.session.commit()
        return jsonify({
            "success": True,
            "message": "Student updated successfully."
        })

    except IntegrityError:
        db.session.rollback()
        return jsonify({
            "success": False,
            "message": "This student ID already exists."
        }), 409


# DELETE STUDENT
@student_bp.route("/<int:student_id>", methods=["DELETE"])
def delete_student(student_id):
    student = db.session.get(Student, student_id)

    if student is None:
        return jsonify({
            "success": False,
            "message": "Student not found."
        }), 404

    db.session.delete(student)
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Student deleted successfully."
    })
