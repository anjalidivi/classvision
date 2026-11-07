
from datetime import date
from flask import Blueprint, request, jsonify
from sqlalchemy.exc import IntegrityError

from database.models import db, Student, Attendance

attendance_bp = Blueprint(
    "attendance",
    __name__,
    url_prefix="/api/attendance"
)


# MARK ATTENDANCE
@attendance_bp.route("/", methods=["POST"])
def mark_attendance():
    data = request.get_json(silent=True) or {}

    student_id = data.get("student_id")
    status = str(data.get("status", "Present")).strip().capitalize()
    attendance_date = data.get("date", date.today().isoformat())

    if not student_id:
        return jsonify({
            "success": False,
            "message": "Student ID is required."
        }), 400

    if status not in ["Present", "Absent"]:
        return jsonify({
            "success": False,
            "message": "Status must be Present or Absent."
        }), 400

    student = Student.query.filter_by(
        student_id=str(student_id).strip()
    ).first()

    if student is None:
        return jsonify({
            "success": False,
            "message": "Student not found."
        }), 404

    try:
        parsed_date = date.fromisoformat(attendance_date)
    except (ValueError, TypeError):
        return jsonify({
            "success": False,
            "message": "Date must use YYYY-MM-DD format."
        }), 400

    record = Attendance(
        student_id=student.id,
        date=parsed_date,
        status=status
    )

    try:
        db.session.add(record)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Attendance recorded successfully.",
            "attendance": {
                "student_id": student.student_id,
                "name": student.name,
                "date": parsed_date.isoformat(),
                "status": status
            }
        }), 201

    except IntegrityError:
        db.session.rollback()
        return jsonify({
            "success": False,
            "message": "Attendance already recorded for this student on this date."
        }), 409


# VIEW ATTENDANCE RECORDS
@attendance_bp.route("/", methods=["GET"])
def get_attendance():
    query = Attendance.query.join(Student)

    selected_date = request.args.get("date")
    selected_student = request.args.get("student_id")

    if selected_date:
        try:
            query = query.filter(
                Attendance.date == date.fromisoformat(selected_date)
            )
        except ValueError:
            return jsonify({
                "success": False,
                "message": "Date must use YYYY-MM-DD format."
            }), 400

    if selected_student:
        query = query.filter(
            Student.student_id == selected_student
        )

    records = query.order_by(Attendance.date.desc()).all()

    return jsonify({
        "success": True,
        "count": len(records),
        "attendance": [
            {
                "student_id": record.student.student_id,
                "name": record.student.name,
                "date": record.date.isoformat(),
                "status": record.status
            }
            for record in records
        ]
    })


# STUDENT ATTENDANCE SUMMARY
@attendance_bp.route("/summary/<string:student_code>", methods=["GET"])
def attendance_summary(student_code):
    student = Student.query.filter_by(
        student_id=student_code
    ).first()

    if student is None:
        return jsonify({
            "success": False,
            "message": "Student not found."
        }), 404

    records = Attendance.query.filter_by(
        student_id=student.id
    ).all()

    total = len(records)
    present = sum(1 for record in records if record.status == "Present")
    absent = sum(1 for record in records if record.status == "Absent")

    percentage = round((present / total) * 100, 2) if total else 0

    return jsonify({
        "success": True,
        "student_id": student.student_id,
        "name": student.name,
        "total_days": total,
        "present": present,
        "absent": absent,
        "attendance_percentage": percentage
    })
