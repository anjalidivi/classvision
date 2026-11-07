
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request
from sqlalchemy import func

from database.models import db, Student, EngagementScore

analytics_bp = Blueprint(
    "analytics",
    __name__,
    url_prefix="/api/analytics"
)


# CLASSROOM OVERVIEW
@analytics_bp.route("/overview", methods=["GET"])
def overview():

    average = db.session.query(
        func.avg(EngagementScore.score)
    ).scalar() or 0

    total = EngagementScore.query.count()

    students = db.session.query(
        func.count(func.distinct(EngagementScore.student_id))
    ).scalar() or 0

    return jsonify({
        "success": True,
        "classroom_average": round(float(average), 2),
        "total_records": total,
        "students_monitored": students
    })


# ENGAGEMENT DISTRIBUTION
@analytics_bp.route("/distribution", methods=["GET"])
def distribution():

    results = db.session.query(
        EngagementScore.engagement_level,
        func.count(EngagementScore.id)
    ).group_by(
        EngagementScore.engagement_level
    ).all()

    return jsonify({
        "success": True,
        "distribution": {
            level: count for level, count in results
        }
    })


# STUDENT-WISE ANALYTICS
@analytics_bp.route("/students", methods=["GET"])
def student_analytics():

    results = db.session.query(
        Student.student_id,
        Student.name,
        func.avg(EngagementScore.score).label("average"),
        func.count(EngagementScore.id).label("records")
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
        "students": [
            {
                "student_id": row.student_id,
                "name": row.name,
                "average_engagement": round(float(row.average), 2),
                "total_records": row.records
            }
            for row in results
        ]
    })


# TIME-BASED ENGAGEMENT TREND
@analytics_bp.route("/trends", methods=["GET"])
def engagement_trends():

    days = request.args.get("days", default=7, type=int)

    if not 1 <= days <= 90:
        return jsonify({
            "success": False,
            "message": "Days must be between 1 and 90."
        }), 400

    start_time = datetime.utcnow() - timedelta(days=days)

    records = db.session.query(
        func.date(EngagementScore.recorded_at).label("day"),
        func.avg(EngagementScore.score).label("average"),
        func.count(EngagementScore.id).label("records")
    ).filter(
        EngagementScore.recorded_at >= start_time
    ).group_by(
        func.date(EngagementScore.recorded_at)
    ).order_by("day").all()

    return jsonify({
        "success": True,
        "days": days,
        "trends": [
            {
                "date": str(row.day),
                "average_engagement": round(float(row.average), 2),
                "records": row.records
            }
            for row in records
        ]
    })


# LOW-ENGAGEMENT ALERTS
@analytics_bp.route("/alerts", methods=["GET"])
def low_engagement_alerts():

    threshold = request.args.get(
        "threshold", default=40, type=float
    )

    if not 0 <= threshold <= 100:
        return jsonify({
            "success": False,
            "message": "Threshold must be between 0 and 100."
        }), 400

    results = db.session.query(
        Student.student_id,
        Student.name,
        func.avg(EngagementScore.score).label("average"),
        func.count(EngagementScore.id).label("records")
    ).join(
        EngagementScore,
        Student.id == EngagementScore.student_id
    ).group_by(
        Student.id,
        Student.student_id,
        Student.name
    ).having(
        func.avg(EngagementScore.score) < threshold
    ).all()

    return jsonify({
        "success": True,
        "threshold": threshold,
        "alert_count": len(results),
        "alerts": [
            {
                "student_id": row.student_id,
                "name": row.name,
                "average_engagement": round(float(row.average), 2),
                "records": row.records,
                "message": "Low engagement detected"
            }
            for row in results
        ]
    })


# ATTENTION HEATMAP DATA
@analytics_bp.route("/heatmap", methods=["GET"])
def engagement_heatmap():

    results = db.session.query(
        Student.student_id,
        Student.name,
        func.date(EngagementScore.recorded_at).label("day"),
        func.avg(EngagementScore.score).label("average")
    ).join(
        EngagementScore,
        Student.id == EngagementScore.student_id
    ).group_by(
        Student.student_id,
        Student.name,
        func.date(EngagementScore.recorded_at)
    ).order_by("day").all()

    return jsonify({
        "success": True,
        "heatmap": [
            {
                "student_id": row.student_id,
                "name": row.name,
                "date": str(row.day),
                "average_engagement": round(float(row.average), 2)
            }
            for row in results
        ]
    })
