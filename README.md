# My AI – Secure LLM Chat Application

A full-stack ChatGPT-style AI chatbot web application built from scratch with Python, Flask, SQLite, JWT authentication, role-based authorization, Swagger/OpenAPI documentation, Google Gemini LLM API integration, persistent conversation history, and multimodal image understanding.

---

## 1. Project Overview

**My AI** is designed as a beginner-friendly yet production-structured AI application. It demonstrates modern backend and frontend engineering patterns:
- **Authentication**: Secure registration and login using cryptographic salted password hashing (`werkzeug.security`).
- **Authorization**: Stateless JSON Web Tokens (`Flask-JWT-Extended`) with role-based access control (`user` vs `admin`).
- **Google GenAI SDK**: Multimodal integration using the official `google-genai` Python SDK communicating with Google Gemini (`gemini-3.5-flash`, configurable via `.env`).
- **Persistent Conversation History**: Multi-turn conversation persistence in SQLite with automated title generation, date grouping (*Today*, *Yesterday*, *Previous 7 Days*, *Older*), and chat deletion.
- **Multimodal Image Understanding**: Upload and analyze JPG, PNG, and WEBP images (up to 10 MB) alongside or without text prompts.
- **ChatGPT-Style UI**: Modern dark-mode interface built with HTML5, CSS3, and Vanilla JavaScript with rich Markdown rendering (headings, lists, code blocks with copy buttons).
- **Interactive API Documentation**: Automated Swagger / OpenAPI documentation UI via Flasgger at `/apidocs/`.
- **Automated Testing**: 24 automated unit and integration tests using `pytest` covering authentication, authorization, conversations, multi-turn, and image upload flows.

---

## 2. Key Features

- **User Authentication**: Email/username and password validation with salted password hashing.
- **JWT Authorization**: 24-hour expiration tokens containing username and role claims.
- **Role-Based Access Control (RBAC)**:
  - Standard user registrations default strictly to the `user` role.
  - Administrative endpoints (`GET /admin`) strictly require the `admin` role claim.
- **Multi-Turn Conversation Memory**:
  - Conversations and messages persist safely in SQLite (`conversations` and `messages` tables).
  - Multi-turn context is formatted into `google.genai.types.Content` structures preserving context across turns.
- **Multimodal Image Uploads**:
  - Image attachment button (`📎`) with client-side thumbnail preview and file removal.
  - Supports image-only or image + text queries.
  - Server-side file validation enforcing format verification via magic bytes (not trusting MIME headers alone) and file size constraints (max 10 MB).
  - Secure, user-isolated image storage preventing cross-user access.
- **ChatGPT-Style Markdown Rendering**:
  - Headings, bold, italic, blockquotes, ordered/unordered lists, and tables render smoothly.
  - Code blocks feature language labels and one-click clipboard copy buttons.
- **Zero-Configuration SQLite Database**:
  - Database schema and tables automatically initialize upon application startup.
  - No database files need to be committed to version control.
- **Security & Error Masking**:
  - All database queries use parameterized SQL to prevent SQL injection.
  - Sensitive internal exceptions and API keys are redacted from server responses.
  - XSS protection via sanitized DOM rendering.

---

## 3. Technology Stack

### Backend
- **Python 3.10+ / 3.14+**
- **Flask**: WSGI web application framework.
- **Flask-JWT-Extended**: JWT token generation, header and query parameter extraction, and role authorization.
- **Google GenAI Python SDK (`google-genai`)**: Official SDK for Google Gemini models.
- **SQLite3**: Embedded relational database with foreign keys and cascade deletion.
- **Werkzeug**: Cryptographic password hashing (`scrypt` / `pbkdf2`).
- **python-dotenv**: Environment variable management.
- **Flasgger**: OpenAPI / Swagger 2.0 interactive documentation.

### Frontend
- **HTML5**: Semantic document structure.
- **CSS3**: Custom dark-mode styling, responsive flexbox layout, CSS variables, and keyframe animations.
- **Vanilla JavaScript (ES6+)**: SPA state management, asynchronous `fetch` calls, dynamic DOM manipulation, and Markdown formatting.
- **marked.js**: Lightweight Markdown parser with safe fallback.

### Testing
- **pytest**: Test suite runner with fixtures and mocks (`unittest.mock`).

---

## 4. Architecture

```
+-------------------------------------------------------------------------+
|                              Browser (Client)                           |
|  [ Auth Views | Responsive History Sidebar | Multimodal Chat Workspace ]|
+-------------------------------------------------------------------------+
                                    |
           HTTP JSON / Multipart    |  Authorization: Bearer <JWT>
                                    v
+-------------------------------------------------------------------------+
|                              Flask Backend                              |
|                                                                         |
|   +-----------------------------------------------------------------+   |
|   |                        REST API Endpoints                       |   |
|   |   GET    /                      -> SPA Web UI / Health Check    |   |
|   |   POST   /signup                -> User registration            |   |
|   |   POST   /login                 -> JWT authentication           |   |
|   |   POST   /generate              -> Multimodal Gemini generation |   |
|   |   GET    /conversations         -> List user conversations      |   |
|   |   POST   /conversations         -> Create new conversation      |   |
|   |   GET    /conversations/<id>    -> Get conversation & messages  |   |
|   |   DELETE /conversations/<id>    -> Delete conversation          |   |
|   |   GET    /uploads/<filename>    -> Secure user-isolated image   |   |
|   |   GET    /admin                 -> Admin-only verification      |   |
|   |   GET    /apidocs/              -> Swagger interactive UI       |   |
|   +-----------------------------------------------------------------+   |
|            |                                            |               |
|            v                                            v               |
|   +-------------------+                     +-----------------------+   |
|   |  SQLite Database  |                     |  Google GenAI SDK     |   |
|   |  (users, convs,   |                     |     (google.genai)    |   |
|   |   messages)       |                     +-----------------------+   |
|   +-------------------+                                 |               |
+---------------------------------------------------------|---------------+
                                                          v
                                              +-----------------------+
                                              | Google Gemini LLM API |
                                              +-----------------------+
```

---

## 5. Folder Structure

```
my-ai-chat-app/
│
├── app.py                  # Main Flask application with REST API & Swagger specs
├── requirements.txt        # Python package dependencies
├── .env.example            # Environment configuration template (safe placeholders)
├── .gitignore              # Git ignore rules for secrets, DBs, and local data
├── README.md               # Documentation and setup instructions
│
├── templates/
│   └── index.html          # HTML5 Single Page Application template
│
├── static/
│   ├── css/
│   │   └── style.css       # Responsive dark-mode ChatGPT-style CSS
│   └── js/
│       └── app.js          # Pure JavaScript frontend controller
│
├── uploads/
│   └── .gitkeep            # Upload directory marker (uploaded files ignored)
│
└── tests/
    ├── __init__.py         # Test package marker
    └── test_api.py         # 24 automated pytest tests
```

---

## 6. Installation & Setup

### 1. Clone the Repository
```bash
git clone https://github.com/your-username/my-ai-chat-app.git
cd my-ai-chat-app
```

### 2. Set Up a Virtual Environment (Recommended)

#### On Windows (PowerShell):
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

#### On Linux / macOS (Bash):
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

---

## 7. Environment Configuration

1. Create a local `.env` file by copying `.env.example`:
   ```bash
   cp .env.example .env
   ```
2. Open `.env` and fill in your values:
   ```env
   # Google Gemini API Key (Obtain from https://aistudio.google.com/)
   GEMINI_API_KEY=your_actual_gemini_api_key_here

   # Gemini Model (Configurable)
   GEMINI_MODEL=gemini-3.5-flash

   # JWT Secret Key (Generate a secure random string)
   JWT_SECRET_KEY=change_this_to_a_secure_random_secret_key

   # Initial Admin Credentials (Optional)
   ADMIN_USERNAME=admin
   ADMIN_PASSWORD=your_strong_admin_password_here
   ```

> [!IMPORTANT]
> - Never commit your `.env` file or share your API keys or passwords.
> - `.gitignore` is preconfigured to prevent `.env` and SQLite database files from being committed.

---

## 8. Running the Application

Start the Flask development server:
```bash
python app.py
```

The application will start at:
- **Chat Application UI**: [http://127.0.0.1:5000/](http://127.0.0.1:5000/)
- **Swagger Documentation**: [http://127.0.0.1:5000/apidocs/](http://127.0.0.1:5000/apidocs/)

---

## 9. API Reference

| Method | Endpoint | Auth | Description | Status Codes |
|---|---|---|---|---|
| `GET` | `/` | None | Web Application UI or API status | `200` |
| `POST` | `/signup` | None | Register a new user account | `200`, `400`, `409` |
| `POST` | `/login` | None | Authenticate user and receive JWT token | `200`, `400`, `401` |
| `POST` | `/generate` | Bearer JWT | Generate AI response (text or multimodal) | `200`, `400`, `401`, `403`, `502` |
| `GET` | `/conversations` | Bearer JWT | List authenticated user's conversations | `200`, `401` |
| `POST` | `/conversations` | Bearer JWT | Create a new conversation thread | `201`, `401` |
| `GET` | `/conversations/<id>` | Bearer JWT | Get conversation messages (chronological) | `200`, `401`, `403`, `404` |
| `DELETE` | `/conversations/<id>` | Bearer JWT | Delete conversation and cascade messages | `200`, `401`, `403`, `404` |
| `GET` | `/uploads/<filename>` | Bearer JWT | Retrieve user-owned uploaded image | `200`, `401`, `403`, `404` |
| `GET` | `/admin` | Bearer JWT | Admin role verification endpoint | `200`, `401`, `403` |

---

## 10. Automated Testing

Run the full automated pytest suite:
```bash
python -m pytest -v
```

The 24 automated tests cover:
- Health check route response (`200 OK`).
- User registration validation (length, match, uniqueness, missing fields).
- Authentication validation (valid credentials, invalid credentials).
- JWT protection on `/generate` and conversation routes.
- Multimodal generation and prompt validation.
- Gemini API error handling and 502 status masking.
- Admin role authorization and non-admin denial (`403 Forbidden`).
- Conversation creation, listing, message retrieval, and cascade deletion.
- Multi-turn conversation context retention.
- Cross-user data isolation and authorization checks.

---

## 11. Security Checklist

- [x] **No Secrets Committed**: `.env` is listed in `.gitignore`; `.env.example` contains only placeholder values.
- [x] **No Databases Committed**: SQLite database files (`*.db`, `users.db`) are ignored.
- [x] **No Uploaded Data Committed**: User uploads in `uploads/` are ignored via `.gitignore`.
- [x] **Password Protection**: Passwords are cryptographically hashed using salted Werkzeug methods.
- [x] **Input Validation**: Strict client and server-side validation on prompts, auth forms, and image uploads.
- [x] **Magic Byte Image Validation**: Uploaded images are verified using binary file signatures (JPEG, PNG, WEBP) to prevent malicious payload uploads.
- [x] **Path Traversal Protection**: Uploaded files use UUIDs and `os.path.basename` to prevent directory traversal.
- [x] **Cross-User Isolation**: Conversation and image endpoints enforce ownership checks, returning `403 Forbidden` for unauthorized attempts.
