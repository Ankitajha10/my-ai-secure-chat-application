"""
Automated Pytest Suite for My AI – Secure LLM Chat Application
Tests:
1. GET / (health check)
2. POST /signup success
3. POST /signup duplicate username (409)
4. POST /signup validation failures (400)
5. POST /login success
6. POST /login invalid credentials (401)
7. POST /generate without JWT (401)
8. POST /generate with valid JWT and mocked Gemini API (200)
9. POST /generate with empty prompt (400)
10. POST /generate Gemini failure simulation (502)
11. GET /admin with admin token (200)
12. GET /admin with user token (403)
"""

import os
import tempfile
import pytest
from unittest.mock import MagicMock, patch
from app import create_app


@pytest.fixture
def app_instance(tmp_path):
    """Create test application configured with an isolated SQLite database."""
    test_db_path = str(tmp_path / "test_users.db")
    
    # Configure test app
    test_config = {
        "TESTING": True,
        "DATABASE": test_db_path,
        "JWT_SECRET_KEY": "test-super-secret-key-32-chars-long-strictly-for-testing",
    }
    
    # Set environment variables for admin setup during test
    os.environ["ADMIN_USERNAME"] = "testadmin"
    os.environ["ADMIN_PASSWORD"] = "TestAdminPass123!"
    os.environ["GEMINI_API_KEY"] = "mock_api_key_for_testing"
    os.environ["GEMINI_MODEL"] = "gemini-2.5-flash"

    app = create_app(test_config=test_config)
    yield app


@pytest.fixture
def client(app_instance):
    """A test client for the app."""
    return app_instance.test_client()


# ----------------------------------------------------------------------
# 1. Test GET /
# ----------------------------------------------------------------------
def test_get_root(client):
    """Test the root endpoint returns the running status message."""
    response = client.get("/", headers={"Accept": "application/json"})
    assert response.status_code == 200
    data = response.get_json()
    assert data == {"message": "LLM API is running"}


# ----------------------------------------------------------------------
# 2. Test POST /signup Success
# ----------------------------------------------------------------------
def test_signup_success(client):
    """Test user registration with valid data."""
    payload = {
        "username": "ankita",
        "password": "example123",
        "confirm_password": "example123",
    }
    response = client.post("/signup", json=payload)
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["message"] == "Account created successfully"


# ----------------------------------------------------------------------
# 3. Test POST /signup Duplicate Username
# ----------------------------------------------------------------------
def test_signup_duplicate_username(client):
    """Test registering an existing username returns HTTP 409 Conflict."""
    payload = {
        "username": "ankita",
        "password": "example123",
        "confirm_password": "example123",
    }
    # First registration
    client.post("/signup", json=payload)
    # Duplicate registration attempt
    dup_response = client.post("/signup", json=payload)
    assert dup_response.status_code == 409
    data = dup_response.get_json()
    assert data["success"] is False
    assert data["error"] == "Username already exists"


# ----------------------------------------------------------------------
# 4. Test POST /signup Validation Errors
# ----------------------------------------------------------------------
@pytest.mark.parametrize(
    "payload, expected_error",
    [
        (
            {"password": "pass123", "confirm_password": "pass123"},
            "Username is required",
        ),
        (
            {"username": "user1", "confirm_password": "pass123"},
            "Password is required",
        ),
        (
            {"username": "user1", "password": "pass123"},
            "Confirm password is required",
        ),
        (
            {"username": "user1", "password": "pass123", "confirm_password": "mismatch"},
            "Passwords do not match",
        ),
        (
            {"username": "user1", "password": "123", "confirm_password": "123"},
            "Password must be at least 6 characters long",
        ),
    ],
)
def test_signup_validation_errors(client, payload, expected_error):
    """Test validation errors for invalid signup input."""
    response = client.post("/signup", json=payload)
    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert expected_error in data["error"]


# ----------------------------------------------------------------------
# 5. Test POST /login Success
# ----------------------------------------------------------------------
def test_login_success(client):
    """Test authenticating with valid credentials."""
    # Register user first
    client.post(
        "/signup",
        json={
            "username": "ankita",
            "password": "example123",
            "confirm_password": "example123",
        },
    )

    # Login
    response = client.post(
        "/login", json={"username": "ankita", "password": "example123"}
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert "access_token" in data
    assert data["username"] == "ankita"
    assert data["role"] == "user"


# ----------------------------------------------------------------------
# 6. Test POST /login Invalid Credentials
# ----------------------------------------------------------------------
def test_login_invalid_credentials(client):
    """Test login with wrong password and nonexistent user."""
    # Register user
    client.post(
        "/signup",
        json={
            "username": "ankita",
            "password": "example123",
            "confirm_password": "example123",
        },
    )

    # Wrong password
    wrong_pw = client.post(
        "/login", json={"username": "ankita", "password": "wrongpassword"}
    )
    assert wrong_pw.status_code == 401
    assert wrong_pw.get_json()["error"] == "Invalid username or password"

    # Nonexistent user
    no_user = client.post(
        "/login", json={"username": "nobody", "password": "example123"}
    )
    assert no_user.status_code == 401
    assert no_user.get_json()["error"] == "Invalid username or password"


# ----------------------------------------------------------------------
# 7. Test POST /generate without JWT
# ----------------------------------------------------------------------
def test_generate_without_jwt(client):
    """Test calling /generate without an Authorization header returns HTTP 401."""
    response = client.post(
        "/generate", json={"prompt": "Explain REST API in simple words"}
    )
    assert response.status_code == 401
    data = response.get_json()
    assert data["success"] is False
    assert "Authorization" in data["error"] or "token" in data["error"].lower()


# ----------------------------------------------------------------------
# 8. Test POST /generate with Valid JWT & Mocked Gemini API
# ----------------------------------------------------------------------
def test_generate_with_valid_jwt(client):
    """Test /generate with valid JWT and mocked Gemini LLM call."""
    # Register & Login
    client.post(
        "/signup",
        json={
            "username": "ankita",
            "password": "example123",
            "confirm_password": "example123",
        },
    )
    login_res = client.post(
        "/login", json={"username": "ankita", "password": "example123"}
    )
    token = login_res.get_json()["access_token"]

    # Mock the Gemini client in app.py
    with patch("app.genai.Client") as mock_genai_client_cls:
        mock_instance = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "A REST API is an architectural style that allows systems to communicate over HTTP using standard methods like GET and POST."
        mock_instance.models.generate_content.return_value = mock_response
        mock_genai_client_cls.return_value = mock_instance

        # Call generate
        response = client.post(
            "/generate",
            headers={"Authorization": f"Bearer {token}"},
            json={"prompt": "Explain REST API in simple words"},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["user"] == "ankita"
        assert data["prompt"] == "Explain REST API in simple words"
        assert "A REST API is an architectural style" in data["response"]


# ----------------------------------------------------------------------
# 9. Test POST /generate with Empty Prompt
# ----------------------------------------------------------------------
def test_generate_empty_prompt(client):
    """Test /generate with an empty prompt returns HTTP 400 Bad Request."""
    # Register & Login
    client.post(
        "/signup",
        json={
            "username": "ankita",
            "password": "example123",
            "confirm_password": "example123",
        },
    )
    login_res = client.post(
        "/login", json={"username": "ankita", "password": "example123"}
    )
    token = login_res.get_json()["access_token"]

    # Empty prompt
    response = client.post(
        "/generate",
        headers={"Authorization": f"Bearer {token}"},
        json={"prompt": "   "},
    )
    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert "Prompt is required" in data["error"]


# ----------------------------------------------------------------------
# 10. Test POST /generate Gemini Failure Simulation (502)
# ----------------------------------------------------------------------
def test_generate_gemini_failure_returns_502(client):
    """Test /generate returns HTTP 502 Bad Gateway when Gemini API fails."""
    # Register & Login
    client.post(
        "/signup",
        json={
            "username": "ankita",
            "password": "example123",
            "confirm_password": "example123",
        },
    )
    login_res = client.post(
        "/login", json={"username": "ankita", "password": "example123"}
    )
    token = login_res.get_json()["access_token"]

    # Mock the Gemini client to raise an exception
    with patch("app.genai.Client") as mock_genai_client_cls:
        mock_instance = MagicMock()
        mock_instance.models.generate_content.side_effect = Exception("Remote service unavailable")
        mock_genai_client_cls.return_value = mock_instance

        response = client.post(
            "/generate",
            headers={"Authorization": f"Bearer {token}"},
            json={"prompt": "Hello Gemini"},
        )
        assert response.status_code == 502
        data = response.get_json()
        assert data["success"] is False
        assert data["error"] == "Failed to generate response from Gemini API"


# ----------------------------------------------------------------------
# 11. Test Admin Authorization
# ----------------------------------------------------------------------
def test_admin_authorization(client):
    """Test user with admin role can access GET /admin."""
    # Login as seeded testadmin
    login_res = client.post(
        "/login", json={"username": "testadmin", "password": "TestAdminPass123!"}
    )
    assert login_res.status_code == 200
    data = login_res.get_json()
    assert data["role"] == "admin"
    admin_token = data["access_token"]

    # Access /admin
    response = client.get(
        "/admin", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    admin_data = response.get_json()
    assert admin_data["message"] == "Welcome Admin"
    assert admin_data["access"] == "authorized"


# ----------------------------------------------------------------------
# 12. Test Normal User Denied from Admin Endpoint (403)
# ----------------------------------------------------------------------
def test_normal_user_denied_from_admin(client):
    """Test regular user cannot access GET /admin and receives HTTP 403."""
    # Register normal user
    client.post(
        "/signup",
        json={
            "username": "ankita",
            "password": "example123",
            "confirm_password": "example123",
        },
    )
    login_res = client.post(
        "/login", json={"username": "ankita", "password": "example123"}
    )
    user_token = login_res.get_json()["access_token"]

    # Try accessing /admin
    response = client.get(
        "/admin", headers={"Authorization": f"Bearer {user_token}"}
    )
    assert response.status_code == 403
    data = response.get_json()
    assert data["success"] is False
    assert data["error"] == "Admin access required"


# ----------------------------------------------------------------------
# 13. Test POST /conversations (Create Conversation)
# ----------------------------------------------------------------------
def test_create_conversation(client):
    """Test creating a new conversation."""
    client.post(
        "/signup",
        json={"username": "conv_user", "password": "password123", "confirm_password": "password123"},
    )
    login_res = client.post("/login", json={"username": "conv_user", "password": "password123"})
    token = login_res.get_json()["access_token"]

    response = client.post(
        "/conversations",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Custom Chat Title"},
    )
    assert response.status_code == 201
    data = response.get_json()
    assert data["success"] is True
    assert data["conversation"]["title"] == "Custom Chat Title"
    assert "id" in data["conversation"]


# ----------------------------------------------------------------------
# 14. Test GET /conversations (List Conversations)
# ----------------------------------------------------------------------
def test_list_conversations(client):
    """Test listing all conversations for authenticated user."""
    client.post(
        "/signup",
        json={"username": "list_user", "password": "password123", "confirm_password": "password123"},
    )
    login_res = client.post("/login", json={"username": "list_user", "password": "password123"})
    token = login_res.get_json()["access_token"]

    # Create 2 conversations
    client.post("/conversations", headers={"Authorization": f"Bearer {token}"}, json={"title": "Chat 1"})
    client.post("/conversations", headers={"Authorization": f"Bearer {token}"}, json={"title": "Chat 2"})

    response = client.get("/conversations", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert len(data["conversations"]) >= 2
    titles = [c["title"] for c in data["conversations"]]
    assert "Chat 1" in titles
    assert "Chat 2" in titles


# ----------------------------------------------------------------------
# 15. Test GET /conversations/<id> (Get Conversation with Messages)
# ----------------------------------------------------------------------
def test_get_conversation_with_messages(client):
    """Test retrieving conversation details and message list."""
    client.post(
        "/signup",
        json={"username": "get_user", "password": "password123", "confirm_password": "password123"},
    )
    login_res = client.post("/login", json={"username": "get_user", "password": "password123"})
    token = login_res.get_json()["access_token"]

    # Create conversation
    res = client.post("/conversations", headers={"Authorization": f"Bearer {token}"}, json={"title": "Detail Chat"})
    conv_id = res.get_json()["conversation"]["id"]

    # Get conversation
    get_res = client.get(f"/conversations/{conv_id}", headers={"Authorization": f"Bearer {token}"})
    assert get_res.status_code == 200
    data = get_res.get_json()
    assert data["success"] is True
    assert data["conversation"]["id"] == conv_id
    assert data["conversation"]["title"] == "Detail Chat"
    assert "messages" in data["conversation"]


# ----------------------------------------------------------------------
# 16. Test POST /generate Saves User and Assistant Messages
# ----------------------------------------------------------------------
def test_generate_creates_new_conversation_and_saves_messages(client):
    """Test /generate without conversation_id automatically creates one and saves messages."""
    client.post(
        "/signup",
        json={"username": "persist_user", "password": "password123", "confirm_password": "password123"},
    )
    login_res = client.post("/login", json={"username": "persist_user", "password": "password123"})
    token = login_res.get_json()["access_token"]

    with patch("app.genai.Client") as mock_genai_client_cls:
        mock_instance = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Here is a clear explanation of REST APIs."
        mock_instance.models.generate_content.return_value = mock_response
        mock_genai_client_cls.return_value = mock_instance

        # Call generate without conversation_id
        res = client.post(
            "/generate",
            headers={"Authorization": f"Bearer {token}"},
            json={"prompt": "Explain REST API in simple words"},
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert "conversation_id" in data
        conv_id = data["conversation_id"]

        # Verify messages were saved in database
        conv_res = client.get(f"/conversations/{conv_id}", headers={"Authorization": f"Bearer {token}"})
        assert conv_res.status_code == 200
        conv_data = conv_res.get_json()["conversation"]
        assert len(conv_data["messages"]) == 2
        assert conv_data["messages"][0]["role"] == "user"
        assert conv_data["messages"][0]["content"] == "Explain REST API in simple words"
        assert conv_data["messages"][1]["role"] == "assistant"
        assert "Here is a clear explanation" in conv_data["messages"][1]["content"]


# ----------------------------------------------------------------------
# 17. Test POST /generate Continues Existing Conversation Multi-Turn
# ----------------------------------------------------------------------
def test_generate_continues_existing_conversation_multiturn(client):
    """Test /generate with conversation_id passes multi-turn context and appends messages."""
    client.post(
        "/signup",
        json={"username": "multiturn_user", "password": "password123", "confirm_password": "password123"},
    )
    login_res = client.post("/login", json={"username": "multiturn_user", "password": "password123"})
    token = login_res.get_json()["access_token"]

    with patch("app.genai.Client") as mock_genai_client_cls:
        mock_instance = MagicMock()
        mock_res1 = MagicMock()
        mock_res1.text = "Python was created by Guido van Rossum."
        mock_instance.models.generate_content.return_value = mock_res1
        mock_genai_client_cls.return_value = mock_instance

        # Turn 1
        res1 = client.post(
            "/generate",
            headers={"Authorization": f"Bearer {token}"},
            json={"prompt": "Who created Python?"},
        )
        assert res1.status_code == 200
        conv_id = res1.get_json()["conversation_id"]

        # Turn 2: Mock follow-up response
        mock_res2 = MagicMock()
        mock_res2.text = "It was first released in 1991."
        mock_instance.models.generate_content.return_value = mock_res2

        # Turn 2 call with conversation_id
        res2 = client.post(
            "/generate",
            headers={"Authorization": f"Bearer {token}"},
            json={"prompt": "When was it released?", "conversation_id": conv_id},
        )
        assert res2.status_code == 200

        # Verify conversation now contains 4 messages
        conv_res = client.get(f"/conversations/{conv_id}", headers={"Authorization": f"Bearer {token}"})
        messages = conv_res.get_json()["conversation"]["messages"]
        assert len(messages) == 4
        assert messages[0]["content"] == "Who created Python?"
        assert messages[2]["content"] == "When was it released?"


# ----------------------------------------------------------------------
# 18. Test DELETE /conversations/<id>
# ----------------------------------------------------------------------
def test_delete_conversation_cascades_messages(client):
    """Test deleting a conversation removes it and its messages."""
    client.post(
        "/signup",
        json={"username": "del_user", "password": "password123", "confirm_password": "password123"},
    )
    login_res = client.post("/login", json={"username": "del_user", "password": "password123"})
    token = login_res.get_json()["access_token"]

    # Create conversation
    res = client.post("/conversations", headers={"Authorization": f"Bearer {token}"}, json={"title": "To Be Deleted"})
    conv_id = res.get_json()["conversation"]["id"]

    # Delete conversation
    del_res = client.delete(f"/conversations/{conv_id}", headers={"Authorization": f"Bearer {token}"})
    assert del_res.status_code == 200
    assert del_res.get_json()["success"] is True

    # Verify conversation is now 404
    get_res = client.get(f"/conversations/{conv_id}", headers={"Authorization": f"Bearer {token}"})
    assert get_res.status_code == 404


# ----------------------------------------------------------------------
# 19. Test Unauthorized Conversation Endpoints (401)
# ----------------------------------------------------------------------
def test_unauthorized_conversation_endpoints(client):
    """Test conversation endpoints require authentication."""
    assert client.get("/conversations").status_code == 401
    assert client.post("/conversations", json={"title": "Test"}).status_code == 401
    assert client.get("/conversations/1").status_code == 401
    assert client.delete("/conversations/1").status_code == 401


# ----------------------------------------------------------------------
# 20. Test Cross-User Conversation Access (403 / 404)
# ----------------------------------------------------------------------
def test_cross_user_conversation_access(client):
    """Test User B cannot access or delete User A's conversation."""
    # User A
    client.post("/signup", json={"username": "user_a", "password": "password123", "confirm_password": "password123"})
    login_a = client.post("/login", json={"username": "user_a", "password": "password123"})
    token_a = login_a.get_json()["access_token"]

    # User B
    client.post("/signup", json={"username": "user_b", "password": "password123", "confirm_password": "password123"})
    login_b = client.post("/login", json={"username": "user_b", "password": "password123"})
    token_b = login_b.get_json()["access_token"]

    # User A creates a conversation
    conv_a = client.post("/conversations", headers={"Authorization": f"Bearer {token_a}"}, json={"title": "Secret A"})
    conv_a_id = conv_a.get_json()["conversation"]["id"]

    # User B attempts to access User A's conversation
    access_attempt = client.get(f"/conversations/{conv_a_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert access_attempt.status_code in [403, 404]

    # User B attempts to delete User A's conversation
    delete_attempt = client.delete(f"/conversations/{conv_a_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert delete_attempt.status_code in [403, 404]

    # Verify conversation still exists for User A
    check_a = client.get(f"/conversations/{conv_a_id}", headers={"Authorization": f"Bearer {token_a}"})
    assert check_a.status_code == 200

