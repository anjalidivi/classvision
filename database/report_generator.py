
from io import BytesIO
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable
)

from database.models import db, Student, EngagementScore, ExpressionHistory


def generate_engagement_pdf():

    buffer = BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        alignment=TA_CENTER,
        textColor=colors.HexColor("#172554"),
        fontSize=20,
        spaceAfter=8
    )

    heading_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        textColor=colors.HexColor("#1D4ED8"),
        spaceBefore=14,
        spaceAfter=8
    )

    story = []

    # REPORT TITLE
    story.append(
        Paragraph(
            "CLASSROOM SNN",
            title_style
        )
    )

    story.append(
        Paragraph(
            "Classroom Engagement Analytics Report",
            styles["Heading2"]
        )
    )

    story.append(
        Paragraph(
            f"Generated on: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}",
            styles["Normal"]
        )
    )

    story.append(Spacer(1, 12))
    story.append(HRFlowable(width="100%", color=colors.grey))
    story.append(Spacer(1, 12))

    # CLASSROOM SUMMARY
    average = db.session.query(
        db.func.avg(EngagementScore.score)
    ).scalar() or 0

    total_records = EngagementScore.query.count()

    students_monitored = db.session.query(
        db.func.count(
            db.func.distinct(EngagementScore.student_id)
        )
    ).scalar() or 0

    story.append(
        Paragraph("1. Classroom Overview", heading_style)
    )

    summary_data = [
        ["Metric", "Value"],
        ["Average Engagement", f"{float(average):.2f}%"],
        ["Total Engagement Records", str(total_records)],
        ["Students Monitored", str(students_monitored)]
    ]

    summary_table = Table(
        summary_data,
        colWidths=[85 * mm, 75 * mm]
    )

    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#172554")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("PADDING", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE")
    ]))

    story.append(summary_table)

    # STUDENT-WISE ENGAGEMENT
    story.append(
        Paragraph("2. Student-wise Engagement", heading_style)
    )

    student_data = [[
        "Student ID",
        "Student Name",
        "Average Score",
        "Records"
    ]]

    results = db.session.query(
        Student.student_id,
        Student.name,
        db.func.avg(EngagementScore.score).label("average"),
        db.func.count(EngagementScore.id).label("records")
    ).join(
        EngagementScore,
        Student.id == EngagementScore.student_id
    ).group_by(
        Student.id,
        Student.student_id,
        Student.name
    ).all()

    for row in results:
        student_data.append([
            str(row.student_id),
            str(row.name),
            f"{float(row.average):.2f}%",
            str(row.records)
        ])

    if len(student_data) == 1:
        student_data.append(["No data", "-", "-", "-"])

    student_table = Table(
        student_data,
        colWidths=[35 * mm, 55 * mm, 40 * mm, 30 * mm],
        repeatRows=1
    )

    student_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1D4ED8")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("PADDING", (0, 0), (-1, -1), 7),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE")
    ]))

    story.append(student_table)

    # ENGAGEMENT DISTRIBUTION
    story.append(
        Paragraph("3. Engagement Distribution", heading_style)
    )

    distribution = db.session.query(
        EngagementScore.engagement_level,
        db.func.count(EngagementScore.id)
    ).group_by(
        EngagementScore.engagement_level
    ).all()

    distribution_data = [
        ["Engagement Level", "Number of Records"]
    ]

    for level, count in distribution:
        distribution_data.append([
            str(level or "Unspecified"),
            str(count)
        ])

    if len(distribution_data) == 1:
        distribution_data.append(["No data", "0"])

    distribution_table = Table(
        distribution_data,
        colWidths=[85 * mm, 75 * mm]
    )

    distribution_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#172554")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("PADDING", (0, 0), (-1, -1), 8)
    ]))

    story.append(distribution_table)

    # EXPRESSION SUMMARY
    story.append(
        Paragraph("4. Expression Statistics", heading_style)
    )

    expressions = db.session.query(
        ExpressionHistory.expression,
        db.func.count(ExpressionHistory.id)
    ).group_by(
        ExpressionHistory.expression
    ).all()

    expression_data = [
        ["Expression", "Number of Records"]
    ]

    for expression, count in expressions:
        expression_data.append([
            str(expression),
            str(count)
        ])

    if len(expression_data) == 1:
        expression_data.append(["No data", "0"])

    expression_table = Table(
        expression_data,
        colWidths=[85 * mm, 75 * mm]
    )

    expression_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1D4ED8")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("PADDING", (0, 0), (-1, -1), 8)
    ]))

    story.append(expression_table)

    # LOW ENGAGEMENT ALERTS
    story.append(
        Paragraph("5. Low Engagement Alerts", heading_style)
    )

    alerts = db.session.query(
        Student.student_id,
        Student.name,
        db.func.avg(EngagementScore.score).label("average")
    ).join(
        EngagementScore,
        Student.id == EngagementScore.student_id
    ).group_by(
        Student.id,
        Student.student_id,
        Student.name
    ).having(
        db.func.avg(EngagementScore.score) < 40
    ).all()

    alert_data = [
        ["Student ID", "Student Name", "Average Engagement"]
    ]

    for row in alerts:
        alert_data.append([
            str(row.student_id),
            str(row.name),
            f"{float(row.average):.2f}%"
        ])

    if len(alert_data) == 1:
        alert_data.append([
            "None",
            "No low-engagement alerts",
            "-"
        ])

    alert_table = Table(
        alert_data,
        colWidths=[45 * mm, 75 * mm, 40 * mm]
    )

    alert_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#991B1B")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("PADDING", (0, 0), (-1, -1), 8)
    ]))

    story.append(alert_table)

    story.append(Spacer(1, 25))

    story.append(
        Paragraph(
            "Generated by CLASSROOM SNN – "
            "AI-Powered Smart Classroom Engagement Monitoring System.",
            styles["Italic"]
        )
    )

    document.build(story)

    buffer.seek(0)

    return buffer

