# RepoSage API Reference Documentation

All endpoints are versioned under `/api/v1` and return standardized JSON envelopes.

## Base Response Envelope
```json
{
  "success": true,
  "message": "Operation completed successfully",
  "data": { ... },
  "error": null
}
```

---

## 1. Authentication Endpoints

### Register User
- **POST** `/api/v1/auth/register`
- **Request Body**:
  ```json
  {
    "email": "developer@example.com",
    "password": "SecurePassword123!"
  }
  ```
- **Response**: `201 Created` with `UserResponse`.

### Login User
- **POST** `/api/v1/auth/login`
- **Request Body**:
  ```json
  {
    "email": "developer@example.com",
    "password": "SecurePassword123!"
  }
  ```
- **Response**: `200 OK` with access token (JWT), refresh token, and expiration in seconds.

### Get Current User Profile
- **GET** `/api/v1/auth/me`
- **Headers**: `Authorization: Bearer <token>`
- **Response**: `200 OK` with `UserResponse`.

---

## 2. Repository Management Endpoints

### Add GitHub Repository
- **POST** `/api/v1/repositories`
- **Headers**: `Authorization: Bearer <token>`
- **Request Body**:
  ```json
  {
    "name": "ecommerce-api",
    "url": "https://github.com/octocat/Hello-World",
    "branch": "main",
    "access_token": "optional-ghp-token"
  }
  ```

### Upload Repository ZIP Archive
- **POST** `/api/v1/repositories/upload-zip`
- **Headers**: `Authorization: Bearer <token>`, `Content-Type: multipart/form-data`
- **Form Data**: `name` (string), `file` (.zip binary).

### List Repositories
- **GET** `/api/v1/repositories`
- **Response**: List of repositories owned by the authenticated user.

### Get Repository Details & Files
- **GET** `/api/v1/repositories/{repository_id}`
- **GET** `/api/v1/repositories/{repository_id}/files`
- **GET** `/api/v1/repositories/{repository_id}/file-content?path=app/main.py`

### Re-index Repository
- **POST** `/api/v1/repositories/{repository_id}/reindex`

---

## 3. Codebase RAG & Chat Endpoints

### Ask Question
- **POST** `/api/v1/chat`
- **Headers**: `Authorization: Bearer <token>`
- **Request Body**:
  ```json
  {
    "repository_id": "b6a1e5e-...",
    "session_id": "optional-session-id",
    "question": "How does user authentication work in this codebase?"
  }
  ```
- **Response**:
  ```json
  {
    "success": true,
    "data": {
      "id": "msg-123",
      "session_id": "sess-456",
      "role": "assistant",
      "content": "### Direct Answer\n...",
      "citations": [
        {
          "file_path": "app/services/auth/auth_service.py",
          "start_line": 25,
          "end_line": 48,
          "symbol_name": "authenticate_user"
        }
      ]
    }
  }
  ```

---

## 4. AI Debugging & Code Intelligence

### Analyze Stack Trace
- **POST** `/api/v1/debug/analyze`
- **Request Body**:
  ```json
  {
    "repository_id": "b6a1e5e-...",
    "error_message": "AttributeError: 'NoneType' object has no attribute 'verify_password'",
    "stack_trace": "Traceback ...",
    "relevant_file": "app/services/auth/auth_service.py"
  }
  ```
- **Response**: Root cause hypothesis, affected files, unified git diff fix, and validation tests.

### Code Review
- **POST** `/api/v1/review`
- **Request Body**:
  ```json
  {
    "repository_id": "b6a1e5e-...",
    "file_path": "app/services/repository/zip_validator.py"
  }
  ```
- **Response**: Categorized findings (Critical, High, Medium, Low) with exact file/line references and remediation advice.
