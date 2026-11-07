
from datetime import datetime
from flask import Blueprint, request, jsonify
from sqlalchemy import func

from database.models import (
    db,
    Student,
    ExpressionHistory,
    EngagementScore
)

engagement_bp = Blueprint(
    "engagement",
    __name__,
    url_prefix="/api/engagement"
)

EXPRESSIONS = {
    "happy",
    "sad",
    "neutral",
    "angry",
    "surprise",
    "disgust",
    "fear"
}

ENGAGEMENT_LEVELS = {
    "attentive",
    "slightly distracted",
    "distracted",
    "highly distracted"
}


def parse_timestamp(value):
    if not value:
        return datetime.utcnow()

    try:
        return datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        ).replace(tzinfo=None)
    except ValueError:
        return None


# --------------------------------------------------
# SAVE ONE AI ENGAGEMENT RESULT
# --------------------------------------------------

@engagement_bp.route("/record", methods=["POST"])
def save_engagement_result():
    data = request.get_json(silent=True) or {}

    student_code = str(data.get("student_id", "")).strip()
    expression = str(data.get("expression", "")).strip().lower()
    level = str(data.get("engagement_status", "")).strip().lower()

    if not student_code or not expression or not level:
        return jsonify({
            "success": False,
            "message": "student_id, expression and engagement_status are required."
        }), 400

    if expression not in EXPRESSIONS:
        return jsonify({
            "success": False,
            "message": "Invalid facial expression."
        }), 400

    if level not in ENGAGEMENT_LEVELS:
        return jsonify({
            "success": False,
            "message": "Invalid engagement classification."
        }), 400

    try:
        score = float(data.get("engagement_score"))
    except (TypeError, ValueError):
        return jsonify({
            "success": False,
            "message": "A valid engagement_score is required."
        }), 400

    if not 0 <= score <= 100:
        return jsonify({
            "success": False,
            "message": "Engagement score must be between 0 and 100."
        }), 400

    confidence = data.get("confidence")

    if confidence is not None:
        try:
            confidence = float(confidence)
        except (TypeError, ValueError):
            return jsonify({
                "success": False,
                "message": "Confidence must be a number between 0 and 1."
            }), 400

        if not 0 <= confidence <= 1:
            return jsonify({
                "success": False,
                "message": "Confidence must be between 0 and 1."
            }), 400

    recorded_at = parse_timestamp(data.get("timestamp"))

    if recorded_at is None:
        return jsonify({
            "success": False,
            "message": "Invalid timestamp. Use ISO format."
        }), 400

    student = Student.query.filter_by(
        student_id=student_code
    ).first()

    if student is None:
        return jsonify({
            "success": False,
            "message": "Student not found. Add the student first."
        }), 404

    expression_record = ExpressionHistory(
        student_id=student.id,
        expression=expression.title(),
        confidence=confidence,
        recorded_at=recorded_at
    )

    engagement_record = EngagementScore(
        student_id=student.id,
        score=score,
        engagement_level=level.title(),
        recorded_at=recorded_at
    )

    try:
        db.session.add(expression_record)
        db.session.add(engagement_record)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Expression and engagement result saved.",
            "result": {
                "student_id": student.student_id,
                "student_name": student.name,
                "expression": expression_record.expression,
                "confidence": confidence,
                "engagement_status": engagement_record.engagement_level,
                "engagement_score": engagement_record.score,
                "timestamp": recorded_at.isoformat()
            }
        }), 201

    except Exception:
        db.session.rollback()
        return jsonify({
            "success": False,
            "message": "Could not save the engagement result."
        }), 500


# --------------------------------------------------
# VIEW EXPRESSION HISTORY
# --------------------------------------------------

@engagement_bp.route("/expressions", methods=["GET"])
def get_expression_history():
    query = ExpressionHistory.query.join(Student)

    student_code = request.args.get("student_id")

    if student_code:
        query = query.filter(Student.student_id == student_code)

    records = query.order_by(
        ExpressionHistory.recorded_at.desc()
    ).limit(500).all()

    return jsonify({
        "success": True,
        "count": len(records),
        "expressions": [
            {
                "student_id": record.student.student_id,
                "student_name": record.student.name,
                "expression": record.expression,
                "confidence": record.confidence,
                "timestamp": record.recorded_at.isoformat()
            }
            for record in records
        ]
    })


# --------------------------------------------------
# VIEW ENGAGEMENT HISTORY
# --------------------------------------------------

@engagement_bp.route("/records", methods=["GET"])
def get_engagement_records():
    query = EngagementScore.query.join(Student)

    student_code = request.args.get("student_id")

    if student_code:
        query = query.filter(Student.student_id == student_code)

    records = query.order_by(
        EngagementScore.recorded_at.desc()
    ).limit(500).all()

    return jsonify({
        "success": True,
        "count": len(records),
        "records": [
            {
                "student_id": record.student.student_id,
                "student_name": record.student.name,
                "engagement_score": record.score,
                "engagement_status": record.engagement_level,
                "timestamp": record.recorded_at.isoformat()
            }
            for record in records
        ]
    })


# --------------------------------------------------
# CLASSROOM ENGAGEMENT SUMMARY
# --------------------------------------------------

@engagement_bp.route("/summary", methods=["GET"])
def classroom_engagement_summary():
    average_score = db.session.query(
        func.avg(EngagementScore.score)
    ).scalar()

    total_records = EngagementScore.query.count()

    distribution = db.session.query(
        EngagementScore.engagement_level,
        func.count(EngagementScore.id)
    ).group_by(
        EngagementScore.engagement_level
    ).all()

    student_averages = db.session.query(
        Student.student_id,
        Student.name,
        func.avg(EngagementScore.score).label("average_score"),
        func.count(EngagementScore.id).label("record_count")
    ).join(
        EngagementScore,
        Student.id == EngagementScore.student_id
    ).group_by(
        Student.id,
        Student.student_id,
        Student.name
    ).all()

    return jsonify({
        "success": True,
        "classroom_average": round(float(average_score or 0), 2),
        "total_engagement_records": total_records,
        "engagement_distribution": {
            level: count for level, count in distribution
        },
        "student_averages": [
            {
                "student_id": row.student_id,
                "name": row.name,
                "average_score": round(float(row.average_score), 2),
                "record_count": row.record_count
            }
            for row in student_averages
        ]
    })
