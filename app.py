"""
My AI – Secure LLM Chat Application
Backend REST API built with Flask, SQLite, Flask-JWT-Extended, Flasgger, and Google GenAI SDK.
"""

import datetime
import os
import sqlite3
import uuid
from flask import Flask, current_app, g, jsonify, render_template, request, send_from_directory
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    get_jwt,
    get_jwt_identity,
    jwt_required,
)
from werkzeug.security import check_password_hash, generate_password_hash
from dotenv import load_dotenv
from flasgger import Swagger
from google import genai
from google.genai import types

# Load environment variables from .env file located in the application directory
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(env_path, override=True)

def create_app(test_config=None):
    """Application factory for My AI."""
    app = Flask(__name__)

    # Configuration
    app.config["JWT_SECRET_KEY"] = os.getenv(
        "JWT_SECRET_KEY", "default-fallback-secret-key-32-chars-minimum-secure"
    )
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = datetime.timedelta(hours=24)
    app.config["JWT_TOKEN_LOCATION"] = ["headers", "query_string"]
    app.config["JWT_QUERY_STRING_NAME"] = "token"
    app.config["DATABASE"] = os.getenv("DATABASE_PATH", "users.db")
    app.config["UPLOAD_FOLDER"] = os.path.join(app.root_path, "uploads")
    app.config["MAX_CONTENT_LENGTH"] = 15 * 1024 * 1024  # 15 MB request ceiling
    app.config["SWAGGER"] = {
        "title": "My AI – Secure LLM Chat Application API",
        "uiversion": 3,
        "openapi": "2.0",
    }

    # Override config for tests if supplied
    if test_config:
        app.config.update(test_config)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # Initialize JWT Manager
    jwt = JWTManager(app)

    # Custom JWT Error Handlers
    @jwt.unauthorized_loader
    def unauthorized_response(callback):
        return jsonify({"success": False, "error": "Missing Authorization Header"}), 401

    @jwt.invalid_token_loader
    def invalid_token_response(callback):
        return jsonify({"success": False, "error": "Invalid token"}), 401

    @jwt.expired_token_loader
    def expired_token_response(jwt_header, jwt_payload):
        return jsonify({"success": False, "error": "Token has expired"}), 401

    # Swagger / OpenAPI Configuration
    swagger_template = {
        "swagger": "2.0",
        "info": {
            "title": "My AI – Secure LLM Chat Application API",
            "description": (
                "Complete REST API with JWT Authentication, Role-based Authorization, "
                "SQLite Database, and Google Gemini LLM Integration."
            ),
            "version": "1.0.0",
        },
        "securityDefinitions": {
            "Bearer": {
                "type": "apiKey",
                "name": "Authorization",
                "in": "header",
                "description": (
                    'Enter your JWT token in the format: Bearer <your_token>\n\n'
                    'Example: Bearer eyJhbGciOiJIUzI1Ni...'
                ),
            }
        },
    }

    swagger_config = {
        "headers": [],
        "specs": [
            {
                "endpoint": "apispec",
                "route": "/apispec.json",
                "rule_filter": lambda rule: True,
                "model_filter": lambda tag: True,
            }
        ],
        "static_url_path": "/flasgger_static",
        "swagger_ui": True,
        "specs_route": "/apidocs/",
    }

    Swagger(app, template=swagger_template, config=swagger_config)

    # Database helpers
    def get_db():
        """Retrieve or create SQLite connection for current request context."""
        if "db" not in g:
            db_path = current_app.config["DATABASE"]
            g.db = sqlite3.connect(db_path)
            g.db.row_factory = sqlite3.Row
        return g.db

    @app.teardown_appcontext
    def close_db(exception=None):
        """Close SQLite connection when request context ends."""
        db = g.pop("db", None)
        if db is not None:
            db.close()

    def init_db():
        """Initialize SQLite tables and seed admin credentials if configured."""
        with app.app_context():
            db = get_db()
            db.execute("PRAGMA foreign_keys = ON;")

            # Create users table
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    role TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL
                )
                """
            )

            # Create conversations table
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
                """
            )

            # Create messages table
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    image_url TEXT,
                    created_at TIMESTAMP NOT NULL,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
                )
                """
            )

            # Migration: Ensure image_url column exists in messages for existing tables
            cursor = db.execute("PRAGMA table_info(messages)")
            cols = [row[1] for row in cursor.fetchall()]
            if "image_url" not in cols:
                db.execute("ALTER TABLE messages ADD COLUMN image_url TEXT")
                db.commit()

            # Create query indexes
            db.execute(
                "CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id, updated_at DESC)"
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id, created_at ASC)"
            )
            db.commit()

            # Seed or sync default admin user from environment variables
            admin_user = os.getenv("ADMIN_USERNAME", "admin").strip()
            admin_pass = os.getenv("ADMIN_PASSWORD", "").strip()

            if admin_user and admin_pass and admin_pass != "your_strong_admin_password_here":
                cursor = db.execute("SELECT id FROM users WHERE username = ?", (admin_user,))
                existing = cursor.fetchone()
                hashed_pw = generate_password_hash(admin_pass)
                now = datetime.datetime.now(datetime.timezone.utc).isoformat()

                if existing is None:
                    db.execute(
                        "INSERT INTO users (username, password, role, created_at) VALUES (?, ?, ?, ?)",
                        (admin_user, hashed_pw, "admin", now),
                    )
                    db.commit()
                else:
                    # Update admin password & role to keep in sync with .env
                    db.execute(
                        "UPDATE users SET password = ?, role = ? WHERE username = ?",
                        (hashed_pw, "admin", admin_user),
                    )
                    db.commit()

    def get_user_by_identity(identity):
        """Fetch user record by identity."""
        db = get_db()
        return db.execute("SELECT id, username, role FROM users WHERE username = ?", (identity,)).fetchone()

    def generate_conversation_title(prompt):
        """Generate a clean, bounded sidebar title from the initial user prompt."""
        if not prompt:
            return "New Chat"
        first_line = prompt.strip().split("\n")[0].strip()
        # Clean common filler suffixes
        for suffix in [" in simple words", " with examples", " with a real-life example", " step by step", " for beginners"]:
            if first_line.lower().endswith(suffix):
                first_line = first_line[:-len(suffix)].strip()
                break
        # Limit length to fit nicely in sidebar
        if len(first_line) > 36:
            words = first_line[:33].rsplit(" ", 1)
            first_line = (words[0] if len(words) > 1 else first_line[:33]) + "..."
        return first_line or "New Chat"

    MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB
    ALLOWED_MIME_TYPES = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }

    def detect_image_type(file_bytes: bytes) -> str | None:
        """Inspect magic bytes to detect real image type safely."""
        if not file_bytes or len(file_bytes) < 12:
            return None
        if file_bytes.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if file_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if file_bytes[:4] == b"RIFF" and file_bytes[8:12] == b"WEBP":
            return "image/webp"
        return None

    # Automatically initialize DB upon app startup
    init_db()

    # ---------------------------------------------------------
    # REST API Routes
    # ---------------------------------------------------------

    @app.route("/", methods=["GET"])
    def index():
        """
        API Health check / Main Application Entry
        ---
        tags:
          - System
        produces:
          - application/json
          - text/html
        responses:
          200:
            description: API running status message or Web UI
            schema:
              type: object
              properties:
                message:
                  type: string
                  example: LLM API is running
        """
        accept_header = request.headers.get("Accept", "")
        # If requested from a browser accepting HTML and not requesting JSON
        if "text/html" in accept_header and "application/json" not in accept_header:
            return render_template("index.html")
        return jsonify({"message": "LLM API is running"}), 200

    @app.route("/chat", methods=["GET"])
    @app.route("/login", methods=["GET"])
    @app.route("/signup", methods=["GET"])
    def frontend_views():
        """Direct route handler to serve the Single Page Chat Application."""
        return render_template("index.html")

    @app.route("/signup", methods=["POST"])
    def signup():
        """
        Register a new user account.
        ---
        tags:
          - Authentication
        parameters:
          - in: body
            name: body
            required: true
            schema:
              type: object
              required:
                - username
                - password
                - confirm_password
              properties:
                username:
                  type: string
                  example: ankita
                password:
                  type: string
                  example: example123
                confirm_password:
                  type: string
                  example: example123
        responses:
          200:
            description: Account created successfully
            schema:
              type: object
              properties:
                success:
                  type: boolean
                  example: true
                message:
                  type: string
                  example: Account created successfully
          400:
            description: Validation error (e.g. missing fields, mismatched passwords, short password)
            schema:
              type: object
              properties:
                success:
                  type: boolean
                  example: false
                error:
                  type: string
          409:
            description: Duplicate username
            schema:
              type: object
              properties:
                success:
                  type: boolean
                  example: false
                error:
                  type: string
                  example: Username already exists
        """
        data = request.get_json(silent=True) or {}
        username = (data.get("username") or "").strip()
        password = data.get("password") or ""
        confirm_password = data.get("confirm_password") or ""

        # Validation rules
        if not username:
            return jsonify({"success": False, "error": "Username is required"}), 400
        if not password:
            return jsonify({"success": False, "error": "Password is required"}), 400
        if not confirm_password:
            return jsonify({"success": False, "error": "Confirm password is required"}), 400
        if password != confirm_password:
            return jsonify({"success": False, "error": "Passwords do not match"}), 400
        if len(password) < 6:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Password must be at least 6 characters long",
                    }
                ),
                400,
            )

        db = get_db()
        # Check if username already exists
        existing = db.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()
        if existing:
            return jsonify({"success": False, "error": "Username already exists"}), 409

        # Always assign 'user' role for self-signup
        hashed_password = generate_password_hash(password)
        created_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

        db.execute(
            "INSERT INTO users (username, password, role, created_at) VALUES (?, ?, ?, ?)",
            (username, hashed_password, "user", created_at),
        )
        db.commit()

        return (
            jsonify({"success": True, "message": "Account created successfully"}),
            200,
        )

    @app.route("/login", methods=["POST"])
    def login():
        """
        Authenticate user and return JWT access token.
        ---
        tags:
          - Authentication
        parameters:
          - in: body
            name: body
            required: true
            schema:
              type: object
              required:
                - username
                - password
              properties:
                username:
                  type: string
                  example: ankita
                password:
                  type: string
                  example: example123
        responses:
          200:
            description: Authentication successful, returns JWT
            schema:
              type: object
              properties:
                success:
                  type: boolean
                  example: true
                access_token:
                  type: string
                  example: eyJhbGciOiJIUzI1Ni...
                username:
                  type: string
                  example: ankita
                role:
                  type: string
                  example: user
          400:
            description: Missing credentials
          401:
            description: Invalid credentials
            schema:
              type: object
              properties:
                success:
                  type: boolean
                  example: false
                error:
                  type: string
                  example: Invalid username or password
        """
        data = request.get_json(silent=True) or {}
        username = (data.get("username") or "").strip()
        password = data.get("password") or ""

        if not username or not password:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Both username and password are required",
                    }
                ),
                400,
            )

        db = get_db()
        user = db.execute(
            "SELECT id, username, password, role FROM users WHERE username = ?",
            (username,),
        ).fetchone()

        if not user or not check_password_hash(user["password"], password):
            return (
                jsonify(
                    {"success": False, "error": "Invalid username or password"}
                ),
                401,
            )

        # Generate JWT with role claim
        access_token = create_access_token(
            identity=user["username"],
            additional_claims={"role": user["role"]},
        )

        return (
            jsonify(
                {
                    "success": True,
                    "access_token": access_token,
                    "username": user["username"],
                    "role": user["role"],
                }
            ),
            200,
        )

    @app.route("/generate", methods=["POST"])
    @jwt_required()
    def generate():
        """
        Generate AI response from Gemini using prompt and optional image.
        ---
        tags:
          - LLM Chat
        security:
          - Bearer: []
        consumes:
          - application/json
          - multipart/form-data
        parameters:
          - in: formData
            name: prompt
            type: string
            description: User prompt or question
          - in: formData
            name: image
            type: file
            description: Optional image file (JPG, PNG, WEBP max 10MB)
          - in: formData
            name: conversation_id
            type: integer
            description: Optional existing conversation ID
        responses:
          200:
            description: Answer generated successfully
          400:
            description: Missing prompt/image, invalid format, or oversized file
          401:
            description: Unauthorized (missing or invalid JWT)
          403:
            description: Forbidden - Not your conversation
          404:
            description: Conversation or user not found
          502:
            description: Gemini API error / Bad Gateway
        """
        username = get_jwt_identity()
        db = get_db()
        user = get_user_by_identity(username)
        if not user:
            return jsonify({"success": False, "error": "User not found"}), 404

        # Support both application/json and multipart/form-data
        image_file = None
        raw_prompt = ""
        conversation_id = None

        if request.is_json:
            data = request.get_json(silent=True) or {}
            raw_prompt = data.get("prompt")
            conversation_id = data.get("conversation_id")
        else:
            raw_prompt = request.form.get("prompt")
            conversation_id = request.form.get("conversation_id")
            if conversation_id:
                try:
                    conversation_id = int(conversation_id)
                except (ValueError, TypeError):
                    conversation_id = None
            if "image" in request.files:
                image_file = request.files.get("image")

        has_prompt = bool(raw_prompt and isinstance(raw_prompt, str) and raw_prompt.strip())
        has_image = bool(image_file and image_file.filename)

        if not has_prompt and not has_image:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Prompt is required and cannot be empty (or attach a valid image)",
                    }
                ),
                400,
            )

        prompt_text = raw_prompt.strip() if has_prompt else ""
        image_bytes = None
        detected_mime = None
        image_url = None

        if has_image:
            image_bytes = image_file.read()
            if len(image_bytes) > MAX_IMAGE_SIZE:
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": "Image file size exceeds the 10 MB limit",
                        }
                    ),
                    400,
                )
            if len(image_bytes) == 0:
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": "Uploaded image file is empty",
                        }
                    ),
                    400,
                )

            detected_mime = detect_image_type(image_bytes)
            if not detected_mime:
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": "Unsupported image format. Allowed formats: JPG, JPEG, PNG, WEBP",
                        }
                    ),
                    400,
                )

            # Store image securely under user's directory using UUID
            ext = ALLOWED_MIME_TYPES[detected_mime]
            filename = f"{uuid.uuid4().hex}{ext}"
            user_upload_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], str(user["id"]))
            os.makedirs(user_upload_dir, exist_ok=True)
            with open(os.path.join(user_upload_dir, filename), "wb") as f:
                f.write(image_bytes)
            image_url = f"/uploads/{filename}"

        # Gemini instruction for image-only request
        gemini_prompt = prompt_text if prompt_text else "Describe and analyze this image in detail."

        # Check API key configuration
        api_key = os.getenv("GEMINI_API_KEY", "").strip().strip("'\"")
        if not api_key or api_key == "your_gemini_api_key_here":
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Gemini API key is not configured. Please set GEMINI_API_KEY in .env",
                    }
                ),
                502,
            )

        model_name = os.getenv("GEMINI_MODEL", "gemini-3.5-flash").strip()

        # Check conversation ownership if conversation_id was provided
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        conv = None
        if conversation_id:
            conv = db.execute(
                "SELECT id, title, user_id FROM conversations WHERE id = ?",
                (conversation_id,),
            ).fetchone()
            if not conv:
                return jsonify({"success": False, "error": "Conversation not found"}), 404
            if conv["user_id"] != user["id"]:
                return jsonify({"success": False, "error": "Unauthorized access to conversation"}), 403

        # Prepare multimodal contents for Gemini
        current_parts = []
        if image_bytes and detected_mime:
            current_parts.append(types.Part.from_bytes(data=image_bytes, mime_type=detected_mime))
        current_parts.append(types.Part.from_text(text=gemini_prompt))
        current_turn = types.Content(role="user", parts=current_parts)

        if conv:
            past_messages = db.execute(
                "SELECT role, content, image_url FROM messages WHERE conversation_id = ? ORDER BY created_at ASC, id ASC",
                (conv["id"],),
            ).fetchall()
            contents = []
            for m in past_messages:
                if m["role"] == "user":
                    m_parts = []
                    if m["image_url"]:
                        img_filename = os.path.basename(m["image_url"])
                        img_path = os.path.join(current_app.config["UPLOAD_FOLDER"], str(user["id"]), img_filename)
                        if os.path.exists(img_path):
                            try:
                                with open(img_path, "rb") as f:
                                    past_bytes = f.read()
                                past_mime = detect_image_type(past_bytes)
                                if past_mime:
                                    m_parts.append(types.Part.from_bytes(data=past_bytes, mime_type=past_mime))
                            except Exception:
                                pass
                    if m["content"]:
                        m_parts.append(types.Part.from_text(text=m["content"]))
                    elif not m_parts:
                        m_parts.append(types.Part.from_text(text="[Image]"))
                    contents.append(types.Content(role="user", parts=m_parts))
                else:
                    contents.append(types.Content(role="model", parts=[types.Part.from_text(text=m["content"])]))
            contents.append(current_turn)
        else:
            contents = [current_turn]

        try:
            client = genai.Client(api_key=api_key)
            result = client.models.generate_content(
                model=model_name,
                contents=contents,
            )

            response_text = ""
            if hasattr(result, "text") and result.text:
                response_text = result.text
            else:
                response_text = "No text returned from model."

            # Save to conversation history
            saved_user_content = prompt_text if prompt_text else ""
            if not conv:
                title_source = prompt_text if prompt_text else "Image Analysis"
                title = generate_conversation_title(title_source)
                cur = db.execute(
                    "INSERT INTO conversations (user_id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                    (user["id"], title, now, now),
                )
                conv_id = cur.lastrowid
                conv_title = title
            else:
                conv_id = conv["id"]
                conv_title = conv["title"]
                db.execute(
                    "UPDATE conversations SET updated_at = ? WHERE id = ?",
                    (now, conv_id),
                )

            # Insert user message and assistant message
            db.execute(
                "INSERT INTO messages (conversation_id, role, content, image_url, created_at) VALUES (?, 'user', ?, ?, ?)",
                (conv_id, saved_user_content, image_url, now),
            )
            db.execute(
                "INSERT INTO messages (conversation_id, role, content, image_url, created_at) VALUES (?, 'assistant', ?, NULL, ?)",
                (conv_id, response_text, now),
            )
            db.commit()

            return (
                jsonify(
                    {
                        "success": True,
                        "conversation_id": conv_id,
                        "title": conv_title,
                        "user": username,
                        "prompt": saved_user_content,
                        "image_url": image_url,
                        "response": response_text,
                    }
                ),
                200,
            )
        except Exception as e:
            err_type = type(e).__name__
            err_msg = str(e)
            if api_key and api_key in err_msg:
                err_msg = err_msg.replace(api_key, "[REDACTED_API_KEY]")
            current_app.logger.error(f"Gemini API error ({err_type}): {err_msg}")

            safe_detail = err_msg[:160] if err_msg else "Unknown remote error"
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Failed to generate response from Gemini API",
                        "details": f"{err_type}: {safe_detail}",
                    }
                ),
                502,
            )

    @app.route("/uploads/<path:filename>", methods=["GET"])
    @jwt_required()
    def get_uploaded_image(filename):
        """
        Serve uploaded image securely to authorized owner only.
        ---
        tags:
          - Uploads
        security:
          - Bearer: []
        parameters:
          - in: path
            name: filename
            type: string
            required: true
        responses:
          200:
            description: Image file binary
          401:
            description: Unauthorized
          403:
            description: Forbidden - Image belongs to another user
          404:
            description: Image not found
        """
        username = get_jwt_identity()
        db = get_db()
        user = get_user_by_identity(username)
        if not user:
            return jsonify({"success": False, "error": "User not found"}), 404

        safe_name = os.path.basename(filename)
        upload_base = current_app.config["UPLOAD_FOLDER"]
        user_upload_dir = os.path.join(upload_base, str(user["id"]))
        file_path = os.path.join(user_upload_dir, safe_name)

        if os.path.exists(file_path):
            with open(file_path, "rb") as f:
                header = f.read(16)
            mime = detect_image_type(header) or "application/octet-stream"
            return send_from_directory(user_upload_dir, safe_name, mimetype=mime)

        # Check if the image belongs to another user to return 403
        if os.path.exists(upload_base):
            for u_dir in os.listdir(upload_base):
                if u_dir != str(user["id"]):
                    other_path = os.path.join(upload_base, u_dir, safe_name)
                    if os.path.exists(other_path):
                        return jsonify({"success": False, "error": "Unauthorized access to image"}), 403

        return jsonify({"success": False, "error": "Image not found"}), 404

    @app.route("/conversations", methods=["GET"])
    @jwt_required()
    def list_conversations():
        """
        List all conversations for the authenticated user.
        ---
        tags:
          - Conversations
        security:
          - Bearer: []
        responses:
          200:
            description: List of conversations ordered by updated_at descending
            schema:
              type: object
              properties:
                success:
                  type: boolean
                  example: true
                conversations:
                  type: array
                  items:
                    type: object
                    properties:
                      id:
                        type: integer
                      title:
                        type: string
                      created_at:
                        type: string
                      updated_at:
                        type: string
          401:
            description: Unauthorized
        """
        username = get_jwt_identity()
        db = get_db()
        user = get_user_by_identity(username)
        if not user:
            return jsonify({"success": False, "error": "User not found"}), 404

        rows = db.execute(
            "SELECT id, title, created_at, updated_at FROM conversations WHERE user_id = ? ORDER BY updated_at DESC",
            (user["id"],),
        ).fetchall()

        conversations = [
            {
                "id": r["id"],
                "title": r["title"],
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
            }
            for r in rows
        ]
        return jsonify({"success": True, "conversations": conversations}), 200

    @app.route("/conversations", methods=["POST"])
    @jwt_required()
    def create_conversation():
        """
        Create a new empty conversation for the authenticated user.
        ---
        tags:
          - Conversations
        security:
          - Bearer: []
        parameters:
          - in: body
            name: body
            schema:
              type: object
              properties:
                title:
                  type: string
                  example: New Chat
        responses:
          201:
            description: Conversation created successfully
          401:
            description: Unauthorized
        """
        username = get_jwt_identity()
        db = get_db()
        user = get_user_by_identity(username)
        if not user:
            return jsonify({"success": False, "error": "User not found"}), 404

        data = request.get_json(silent=True) or {}
        title = (data.get("title") or "New Chat").strip()
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()

        cur = db.execute(
            "INSERT INTO conversations (user_id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (user["id"], title, now, now),
        )
        db.commit()

        return (
            jsonify(
                {
                    "success": True,
                    "conversation": {
                        "id": cur.lastrowid,
                        "title": title,
                        "created_at": now,
                        "updated_at": now,
                    },
                }
            ),
            201,
        )

    @app.route("/conversations/<int:conv_id>", methods=["GET"])
    @jwt_required()
    def get_conversation(conv_id):
        """
        Get a specific conversation and all its messages in chronological order.
        ---
        tags:
          - Conversations
        security:
          - Bearer: []
        parameters:
          - in: path
            name: conv_id
            type: integer
            required: true
        responses:
          200:
            description: Conversation and messages
          401:
            description: Unauthorized
          403:
            description: Forbidden - Not your conversation
          404:
            description: Conversation not found
        """
        username = get_jwt_identity()
        db = get_db()
        user = get_user_by_identity(username)
        if not user:
            return jsonify({"success": False, "error": "User not found"}), 404

        conv = db.execute(
            "SELECT id, title, user_id, created_at, updated_at FROM conversations WHERE id = ?",
            (conv_id,),
        ).fetchone()
        if not conv:
            return jsonify({"success": False, "error": "Conversation not found"}), 404
        if conv["user_id"] != user["id"]:
            return jsonify({"success": False, "error": "Unauthorized access to conversation"}), 403

        msg_rows = db.execute(
            "SELECT id, role, content, image_url, created_at FROM messages WHERE conversation_id = ? ORDER BY created_at ASC, id ASC",
            (conv_id,),
        ).fetchall()

        messages = [
            {
                "id": m["id"],
                "role": m["role"],
                "content": m["content"],
                "image_url": m["image_url"],
                "created_at": m["created_at"],
            }
            for m in msg_rows
        ]

        return (
            jsonify(
                {
                    "success": True,
                    "conversation": {
                        "id": conv["id"],
                        "title": conv["title"],
                        "created_at": conv["created_at"],
                        "updated_at": conv["updated_at"],
                        "messages": messages,
                    },
                }
            ),
            200,
        )

    @app.route("/conversations/<int:conv_id>", methods=["DELETE"])
    @jwt_required()
    def delete_conversation(conv_id):
        """
        Delete a conversation and all its messages.
        ---
        tags:
          - Conversations
        security:
          - Bearer: []
        parameters:
          - in: path
            name: conv_id
            type: integer
            required: true
        responses:
          200:
            description: Conversation deleted successfully
          401:
            description: Unauthorized
          403:
            description: Forbidden - Not your conversation
          404:
            description: Conversation not found
        """
        username = get_jwt_identity()
        db = get_db()
        user = get_user_by_identity(username)
        if not user:
            return jsonify({"success": False, "error": "User not found"}), 404

        conv = db.execute(
            "SELECT id, user_id FROM conversations WHERE id = ?",
            (conv_id,),
        ).fetchone()
        if not conv:
            return jsonify({"success": False, "error": "Conversation not found"}), 404
        if conv["user_id"] != user["id"]:
            return jsonify({"success": False, "error": "Unauthorized access to conversation"}), 403

        # Clean up any image files on disk associated with this conversation
        images_to_delete = db.execute(
            "SELECT image_url FROM messages WHERE conversation_id = ? AND image_url IS NOT NULL",
            (conv_id,),
        ).fetchall()
        for row in images_to_delete:
            if row["image_url"]:
                img_name = os.path.basename(row["image_url"])
                img_path = os.path.join(current_app.config["UPLOAD_FOLDER"], str(user["id"]), img_name)
                if os.path.exists(img_path):
                    try:
                        os.remove(img_path)
                    except OSError:
                        pass

        db.execute("DELETE FROM messages WHERE conversation_id = ?", (conv_id,))
        db.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
        db.commit()

        return jsonify({"success": True, "message": "Conversation deleted successfully"}), 200

    @app.errorhandler(413)
    def request_entity_too_large(error):
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Image file size exceeds the 10 MB limit",
                }
            ),
            400,
        )

    @app.route("/admin", methods=["GET"])
    @jwt_required()
    def admin():
        """
        Admin-only verification endpoint.
        ---
        tags:
          - Admin
        security:
          - Bearer: []
        responses:
          200:
            description: Welcome Admin authorized response
            schema:
              type: object
              properties:
                message:
                  type: string
                  example: Welcome Admin
                access:
                  type: string
                  example: authorized
          401:
            description: Missing or invalid JWT
          403:
            description: Forbidden (role is not admin)
            schema:
              type: object
              properties:
                success:
                  type: boolean
                  example: false
                error:
                  type: string
                  example: Admin access required
        """
        claims = get_jwt()
        role = claims.get("role", "user")

        if role != "admin":
            return (
                jsonify(
                    {"success": False, "error": "Admin access required"}
                ),
                403,
            )

        return (
            jsonify(
                {
                    "message": "Welcome Admin",
                    "access": "authorized",
                }
            ),
            200,
        )

    return app

# Main entry point
app = create_app()

if __name__ == "__main__":
    # Run development server on 127.0.0.1:5000
    app.run(host="127.0.0.1", port=5000, debug=True)
