from database.analytics_routes import analytics_bp
from database.engagement_routes import engagement_bp
from database.student_routes import student_bp
from database.report_generator import generate_engagement_pdf
from database import db
from database.auth_routes import auth_bp
from flask import session
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    send_from_directory,
    send_file,
    abort
)

from werkzeug.utils import secure_filename
from pathlib import Path
import json
import sys
from datetime import datetime


import os

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "classroom-snn-development-key-change-before-deployment"
)

app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = False
app.config["PERMANENT_SESSION_LIFETIME"] = 1800
# --------------------------------------------------
# DATABASE CONFIGURATION
# --------------------------------------------------

app.config["SQLALCHEMY_DATABASE_URI"] = (
    f"sqlite:///{(Path(__file__).resolve().parent / 'instance' / 'classroom.db').as_posix()}"
)

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)
app.register_blueprint(student_bp)
app.register_blueprint(engagement_bp)
app.register_blueprint(analytics_bp)
app.register_blueprint(auth_bp)
# Protect dashboard pages and APIs
@app.before_request
def require_login():

    # Pages and endpoints accessible without login
    allowed_endpoints = [
        "static",
        "auth.register",
        "auth.login",
        "auth.logout",
        "auth.current_user"
    ]

    if request.endpoint in allowed_endpoints:
        return None

    # Allow login and registration pages
    if request.path in ["/login", "/register"]:
        return None

    # Check whether the user is logged in
    if not session.get("user_id"):

        # API requests receive a JSON response
        if request.path.startswith("/api/"):
            return {
                "success": False,
                "message": "Please log in to access this resource."
            }, 401

        # Browser requests go to the login page
        return redirect(url_for("login_page"))

    return None

# --------------------------------------------------
# PROJECT DIRECTORIES
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent

REPORTS_DIR = BASE_DIR / "reports"
UPLOAD_DIR = BASE_DIR / "uploads"

PROCESSED_DIR = REPORTS_DIR / "processed"

ACTIVITIES_DIR = PROCESSED_DIR / "activities"
ANNOTATED_DIR = PROCESSED_DIR / "annotated"

for directory in [
    UPLOAD_DIR,
    REPORTS_DIR,
    ACTIVITIES_DIR,
    ANNOTATED_DIR
]:
    directory.mkdir(parents=True, exist_ok=True)


app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024

ALLOWED_EXTENSIONS = {
    "mp4", "avi", "mov", "mkv", "webm"
}


# --------------------------------------------------
# DASHBOARD PAGES
# --------------------------------------------------

PAGES = {
    "overview": (
        "Dashboard Overview",
        "Smart classroom analytics."
    ),

    "video-upload": (
        "Video Upload",
        "Upload classroom recordings."
    ),

    "face-training": (
        "Face Detection Training",
        "Face detection training workflow."
    ),

    "face-testing": (
        "Face Detection Testing",
        "Test face detection."
    ),

    "expression-training": (
        "Expression Training",
        "Train expression recognition models."
    ),

    "expression-testing": (
        "Expression Testing",
        "Test expression recognition models."
    ),

    "models": (
        "CNN + LIF SNN",
        "Spiking neural network expression recognition model."
    ),

    "engagement": (
        "Engagement Results",
        "View classroom expression analysis."
    ),

    "queries": (
        "Ask Queries",
        "Classroom data query interface."
    ),

    "monitoring": (
        "Overall Monitoring",
        "Classroom monitoring summary."
    )
}


# --------------------------------------------------
# LOAD MODEL METRICS
# --------------------------------------------------

def load_metrics():

    possible_files = [
        REPORTS_DIR / "snn_lif_evaluation_80.json",
        REPORTS_DIR / "snn_evaluation_improved_80.json",
        REPORTS_DIR / "snn_evaluation_80.json"
    ]

    for path in possible_files:

        if path.exists():

            try:

                with path.open("r", encoding="utf-8") as file:
                    return json.load(file)

            except (OSError, json.JSONDecodeError):

                app.logger.exception(
                    "Metrics loading failed"
                )

    return {}


# --------------------------------------------------
# LOAD LATEST CLASSROOM ANALYSIS
# --------------------------------------------------

def load_latest_analysis():

    report_files = list(
        ACTIVITIES_DIR.glob("*_integrated_report.json")
    )

    if not report_files:
        return {}

    latest_report = max(
        report_files,
        key=lambda file: file.stat().st_mtime
    )

    try:

        with latest_report.open(
            "r",
            encoding="utf-8"
        ) as file:

            analysis = json.load(file)

        analysis["_report_filename"] = latest_report.name

        # --------------------------------------------------
        # FIND MATCHING BROWSER VIDEO
        # --------------------------------------------------

        video_name = analysis.get("video_name", "")

        if video_name:

            video_stem = Path(video_name).stem

            browser_video = (
                ANNOTATED_DIR
                / f"{video_stem}_browser.mp4"
            )

            if browser_video.is_file():

                analysis["_browser_video_filename"] = (
                    browser_video.name
                )

                analysis["_browser_video_available"] = True

            else:

                analysis["_browser_video_filename"] = None

                analysis["_browser_video_available"] = False

        else:

            analysis["_browser_video_filename"] = None

            analysis["_browser_video_available"] = False

        return analysis

    except (OSError, json.JSONDecodeError):

        app.logger.exception(
            "Analysis report loading failed"
        )

        return {}


# --------------------------------------------------
# GET UPLOADED VIDEOS
# --------------------------------------------------

def get_videos():

    videos = []

    for file in UPLOAD_DIR.iterdir():

        if (
            file.is_file()
            and file.suffix.lower().lstrip(".") in ALLOWED_EXTENSIONS
        ):

            videos.append({

                "name": file.name,

                "size": round(
                    file.stat().st_size / (1024 * 1024),
                    2
                )

            })

    return sorted(
        videos,
        key=lambda item: item["name"],
        reverse=True
    )


# --------------------------------------------------
# DASHBOARD HOME
# --------------------------------------------------
# Login page
@app.route("/login")
def login_page():
    if session.get("user_id"):
        return redirect(url_for("page", slug="overview"))

    return render_template(
        "login.html",
        page={
            "title": "Login",
            "description": "Sign in to your account"
        },
        pages=PAGES,
        active_page="login",
        current_year=datetime.now().year,
        metrics={},
        videos=[],
        analysis={},
        latest_video_url=None
    )


# Registration page
@app.route("/register")
def register_page():
    if session.get("user_id"):
        return redirect(url_for("page", slug="overview"))

    return render_template(
        "register.html",
        page={
            "title": "Register",
            "description": "Create your account"
        },
        pages=PAGES,
        active_page="register",
        current_year=datetime.now().year,
        metrics={},
        videos=[],
        analysis={},
        latest_video_url=None
    )

@app.route("/")
def home():

    return redirect(
        url_for("page", slug="overview")
    )


# --------------------------------------------------
# DASHBOARD PAGE
# --------------------------------------------------

@app.route("/page/<slug>")
def page(slug):

    if slug not in PAGES:

        return redirect(
            url_for("home")
        )

    analysis = load_latest_analysis()

    # Dynamic URL for the latest H.264 video
    latest_video_url = None

    if analysis.get("_browser_video_available"):

        latest_video_url = url_for(
            "latest_processed_video"
        )

    return render_template(

        "dashboard.html",

        active_page=slug,

        page={

            "title": PAGES[slug][0],

            "description": PAGES[slug][1]

        },

        pages=PAGES,

        metrics=load_metrics(),

        videos=get_videos(),

        analysis=analysis,

        latest_video_url=latest_video_url,

        current_year=datetime.now().year

    )


# --------------------------------------------------
# VIDEO UPLOAD
# --------------------------------------------------

@app.route("/upload", methods=["POST"])
def upload():

    video = request.files.get("video")

    if not video or not video.filename:

        flash(
            "Please select a video.",
            "error"
        )

        return redirect(
            url_for("page", slug="video-upload")
        )

    filename = secure_filename(video.filename)

    if not filename or "." not in filename:

        flash(
            "Invalid video filename.",
            "error"
        )

        return redirect(
            url_for("page", slug="video-upload")
        )

    extension = filename.rsplit(".", 1)[-1].lower()

    if extension not in ALLOWED_EXTENSIONS:

        flash(
            "Unsupported video format.",
            "error"
        )

        return redirect(
            url_for("page", slug="video-upload")
        )

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    saved_name = f"{timestamp}_{filename}"

    try:

        video.save(
            UPLOAD_DIR / saved_name
        )

        flash(
            "Video uploaded successfully!",
            "success"
        )

    except OSError as error:

        app.logger.exception(
            "Video upload failed"
        )

        flash(
            f"Upload failed: {error}",
            "error"
        )

    return redirect(
        url_for("page", slug="video-upload")
    )


# --------------------------------------------------
# FILE SIZE ERROR
# --------------------------------------------------

@app.errorhandler(413)
def too_large(error):

    flash(
        "Video exceeds the 500 MB limit.",
        "error"
    )

    return redirect(
        url_for("page", slug="video-upload")
    )


# --------------------------------------------------
# PROCESS CLASSROOM VIDEO
# --------------------------------------------------

@app.route(
    "/process/<path:filename>",
    methods=["POST"]
)
def process_video(filename):

    print(
        "\n======================================",
        flush=True
    )

    print(
        "VIDEO PROCESSING REQUEST RECEIVED",
        flush=True
    )

    print(
        "Filename:",
        filename,
        flush=True
    )

    safe_name = secure_filename(filename)

    video_path = UPLOAD_DIR / safe_name

    if not video_path.is_file():

        flash(
            "Video file not found.",
            "error"
        )

        return redirect(
            url_for("page", slug="video-upload")
        )

    try:

        src_path = str(BASE_DIR / "src")

        if src_path not in sys.path:

            sys.path.insert(0, src_path)

        from integrated_video_processor import (
            process_classroom_video
        )

        print(
            "Starting AI video analysis...",
            flush=True
        )

        process_classroom_video(
            video_path,
            sample_interval=5
        )

        print(
            "AI video analysis completed!",
            flush=True
        )

        flash(
            "Video analysis and H.264 conversion completed successfully!",
            "success"
        )

    except Exception as error:

        app.logger.exception(
            "Video processing failed"
        )

        flash(
            f"Video processing failed: {error}",
            "error"
        )

    return redirect(
        url_for("page", slug="video-upload")
    )


# --------------------------------------------------
# SERVE ANNOTATED VIDEO
# --------------------------------------------------

@app.route(
    "/processed-video/<path:filename>"
)
def processed_video(filename):

    return send_from_directory(
        ANNOTATED_DIR,
        filename,
        as_attachment=False
    )


# --------------------------------------------------
# PLAY LATEST PROCESSED H.264 VIDEO
# --------------------------------------------------

@app.route("/latest-processed-video")
def latest_processed_video():

    analysis = load_latest_analysis()

    filename = analysis.get(
        "_browser_video_filename"
    )

    if not filename:

        abort(404)

    return send_from_directory(
        ANNOTATED_DIR,
        filename,
        as_attachment=False
    )


# --------------------------------------------------
# DOWNLOAD CLASSROOM ANALYSIS REPORT
# --------------------------------------------------
# --------------------------------------------------
# DOWNLOAD DATABASE ENGAGEMENT PDF REPORT
# --------------------------------------------------

@app.route("/download-engagement-report")
def download_engagement_report():

    try:
        pdf_buffer = generate_engagement_pdf()

        filename = (
            "classroom_engagement_report_"
            + datetime.now().strftime("%Y%m%d_%H%M%S")
            + ".pdf"
        )

        return send_file(
            pdf_buffer,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename
        )

    except Exception as error:

        app.logger.exception("PDF report generation failed")

        flash(
            "Unable to generate engagement report. Please check the server logs.",
            "error"
        )

        return redirect(url_for("page", slug="overview"))

@app.route("/download-report")
def download_report():

    analysis = load_latest_analysis()

    if not analysis:

        flash(
            "No classroom analysis report is available.",
            "error"
        )

        return redirect(
            url_for("page", slug="overview")
        )

    filename = analysis.get(
        "_report_filename"
    )

    if not filename:

        abort(404)

    return send_from_directory(
        ACTIVITIES_DIR,
        filename,
        as_attachment=True
    )


# --------------------------------------------------
# VIEW REPORT FILES
# --------------------------------------------------

@app.route("/reports/<path:filename>")
def view_report(filename):

    return send_from_directory(
        REPORTS_DIR,
        filename,
        as_attachment=False
    )


# --------------------------------------------------
# RUN APPLICATION
# --------------------------------------------------
# --------------------------------------------------
# INITIALIZE DATABASE TABLES
# --------------------------------------------------

with app.app_context():
    db.create_all()
    print("Database tables initialized successfully!")

if __name__ == "__main__":
        app.run(debug=True, use_reloader=False)
    
# ==================================================
# LIVE WEBCAM FACE DETECTION API
# ==================================================

import base64
import cv2
import numpy as np

from flask import jsonify

from src.shared_video_processor import (
    create_face_detector,
    process_frame
)

from src.face_tracker import FaceTracker


# Temporary webcam session objects
webcam_detector = None
webcam_tracker = None


@app.route("/api/webcam/detect", methods=["POST"])
def webcam_detect():

    global webcam_detector, webcam_tracker

    try:
        data = request.get_json(silent=True) or {}

        image_data = data.get("image", "")

        if "," not in image_data:
            return jsonify({
                "success": False,
                "message": "Invalid webcam frame."
            }), 400

        # Decode browser image
        encoded_image = image_data.split(",", 1)[1]

        image_bytes = base64.b64decode(encoded_image)

        image_array = np.frombuffer(
            image_bytes,
            dtype=np.uint8
        )

        frame = cv2.imdecode(
            image_array,
            cv2.IMREAD_COLOR
        )

        if frame is None:
            return jsonify({
                "success": False,
                "message": "Unable to decode webcam frame."
            }), 400

        # Initialize detector and tracker once per active session
        if webcam_detector is None:
            webcam_detector = create_face_detector()

        if webcam_tracker is None:
            webcam_tracker = FaceTracker()

        # MediaPipe face detection
        detections = process_frame(
            frame,
            webcam_detector
        )

        # Assign temporary tracking IDs
        tracked_faces = webcam_tracker.update(
            detections
        )

        faces = []

        for face in tracked_faces:

            x, y, width, height = face["box"]

            faces.append({
                "student_id": face["student_id"],
                "box": [
                    int(x),
                    int(y),
                    int(width),
                    int(height)
                ]
            })

        return jsonify({
            "success": True,
            "face_count": len(faces),
            "faces": faces
        })

    except Exception as error:

        app.logger.exception("Webcam detection failed")

        return jsonify({
            "success": False,
            "message": str(error)
        }), 500


@app.route("/api/webcam/stop", methods=["POST"])
def webcam_stop():

    global webcam_detector, webcam_tracker

    if webcam_detector is not None:
        webcam_detector.close()
        webcam_detector = None

    webcam_tracker = None

    return jsonify({
        "success": True,
        "message": "Webcam AI session stopped."
    })


    print("\n======================================")
    print("       CLASSROOM SNN DASHBOARD")
    print("======================================")

    print(
        "Open: http://127.0.0.1:5000"
    )

    print("======================================\n")

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )
