"""
Unit tests for admin.py module.

Tests cover teacher creation, lecture scheduling, and student enrollment endpoints.
All tests use the current InsightFace-based pipeline (no FaceModel / torch).
"""

import pytest
import base64
from io import BytesIO
from datetime import datetime
from fastapi import status
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from fastapi import FastAPI
from admin import router

app = FastAPI()
app.include_router(router)
client = TestClient(app)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_b64_image() -> str:
    """Return a minimal valid base64-encoded 1×1 red PNG."""
    try:
        from PIL import Image
        img = Image.new("RGB", (1, 1), color="red")
        buf = BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()
    except ImportError:
        # Fallback: raw 1×1 red PNG bytes (hard-coded)
        raw = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
            b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00"
            b"\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18"
            b"\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        return base64.b64encode(raw).decode()


# ---------------------------------------------------------------------------
# POST /admin/schedule-lecture
# ---------------------------------------------------------------------------

class TestScheduleLectureEndpoint:
    """Tests for POST /admin/schedule-lecture."""

    @patch("admin.get_db_connection")
    def test_schedule_by_username_success(self, mock_conn):
        """Schedule a lecture by providing teacher username (frontend flow)."""
        conn = MagicMock()
        cursor = MagicMock()
        conn.cursor.return_value = cursor
        mock_conn.return_value = conn

        # First fetchone: username lookup → (user_id, school, department)
        # Second fetchone: OUTPUT INSERTED.lec_id → lec_id
        cursor.fetchone.side_effect = [(42, "Engineering", "CS"), (101,)]

        response = client.post(
            "/admin/schedule-lecture",
            headers={"X-Privilege-Level": "2"},
            json={
                "username": "teacher1",
                "year": "FY",
                "specialisation": "CSE",
                "lecorlab": "lec",
                "panel": "H",
                "lec_name": "Data Structures",
                "course_code": "CS201",
                "lecture_datetime": "2024-01-15T10:00:00",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["lec_id"] == 101
        assert "scheduled" in data["message"].lower()
        conn.commit.assert_called_once()

    @patch("admin.get_db_connection")
    def test_schedule_by_user_id_success(self, mock_conn):
        """Schedule a lecture by providing user_id directly."""
        conn = MagicMock()
        cursor = MagicMock()
        conn.cursor.return_value = cursor
        mock_conn.return_value = conn
        cursor.fetchone.return_value = (55,)

        response = client.post(
            "/admin/schedule-lecture",
            headers={"X-Privilege-Level": "2"},
            json={
                "user_id": 10,
                "year": "SY",
                "specialisation": "AIDS",
                "lecorlab": "lab",
                "panel": "I",
                "lec_name": "ML Lab",
                "course_code": "AI301",
                "lecture_datetime": "2024-03-01T14:00:00",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["lec_id"] == 55

    @patch("admin.get_db_connection")
    def test_schedule_unknown_username_returns_404(self, mock_conn):
        """Unknown teacher username should return 404."""
        conn = MagicMock()
        cursor = MagicMock()
        conn.cursor.return_value = cursor
        mock_conn.return_value = conn
        cursor.fetchone.return_value = None  # username not found

        response = client.post(
            "/admin/schedule-lecture",
            headers={"X-Privilege-Level": "2"},
            json={
                "username": "ghost_teacher",
                "year": "FY",
                "specialisation": "CSE",
                "lecorlab": "lec",
                "panel": "A",
                "lec_name": "Test",
                "course_code": "T101",
                "lecture_datetime": "2024-01-01T10:00:00",
            },
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "ghost_teacher" in response.json()["detail"]

    def test_schedule_no_user_or_username_returns_400(self):
        """Omitting both user_id and username should return 400."""
        response = client.post(
            "/admin/schedule-lecture",
            headers={"X-Privilege-Level": "2"},
            json={
                "year": "FY",
                "specialisation": "CSE",
                "lecorlab": "lec",
                "panel": "A",
                "lec_name": "Test",
                "course_code": "T101",
                "lecture_datetime": "2024-01-01T10:00:00",
            },
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_schedule_teacher_privilege_returns_403(self):
        """Privilege level 3 (teacher) must not schedule lectures."""
        response = client.post(
            "/admin/schedule-lecture",
            headers={"X-Privilege-Level": "3"},
            json={
                "user_id": 1,
                "year": "FY",
                "specialisation": "CSE",
                "lecorlab": "lec",
                "panel": "A",
                "lec_name": "Test",
                "course_code": "T101",
                "lecture_datetime": "2024-01-01T10:00:00",
            },
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_schedule_no_privilege_header_returns_403(self):
        """Missing X-Privilege-Level header must return 403."""
        response = client.post(
            "/admin/schedule-lecture",
            json={
                "user_id": 1,
                "year": "FY",
                "specialisation": "CSE",
                "lecorlab": "lec",
                "panel": "A",
                "lec_name": "Test",
                "course_code": "T101",
                "lecture_datetime": "2024-01-01T10:00:00",
            },
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_schedule_missing_required_fields_returns_422(self):
        """Missing Pydantic-required fields must return 422."""
        response = client.post(
            "/admin/schedule-lecture",
            headers={"X-Privilege-Level": "2"},
            json={"user_id": 1},  # missing year, panel, lec_name, etc.
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @patch("admin.get_db_connection")
    def test_schedule_superadmin_can_schedule(self, mock_conn):
        """Privilege level 1 (superadmin) must also be able to schedule."""
        conn = MagicMock()
        cursor = MagicMock()
        conn.cursor.return_value = cursor
        mock_conn.return_value = conn
        cursor.fetchone.return_value = (77,)

        response = client.post(
            "/admin/schedule-lecture",
            headers={"X-Privilege-Level": "1"},
            json={
                "user_id": 5,
                "year": "TY",
                "specialisation": "CSE",
                "lecorlab": "lec",
                "panel": "B",
                "lec_name": "OS",
                "course_code": "CS401",
                "lecture_datetime": "2024-06-01T09:00:00",
            },
        )
        assert response.status_code == status.HTTP_200_OK

    @patch("admin.get_db_connection")
    def test_schedule_rollback_on_db_error(self, mock_conn):
        """DB error during INSERT must trigger rollback and return 500."""
        import pyodbc

        conn = MagicMock()
        cursor = MagicMock()
        conn.cursor.return_value = cursor
        mock_conn.return_value = conn

        # username lookup succeeds, INSERT raises
        cursor.fetchone.return_value = (10, "Eng", "CS")
        cursor.execute.side_effect = [None, pyodbc.Error("insert failed")]

        response = client.post(
            "/admin/schedule-lecture",
            headers={"X-Privilege-Level": "2"},
            json={
                "username": "teacher1",
                "year": "FY",
                "specialisation": "CSE",
                "lecorlab": "lec",
                "panel": "A",
                "lec_name": "Test",
                "course_code": "T101",
                "lecture_datetime": "2024-01-01T10:00:00",
            },
        )

        conn.rollback.assert_called_once()
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


# ---------------------------------------------------------------------------
# POST /admin/enroll-student
# ---------------------------------------------------------------------------

class TestEnrollStudentEndpoint:
    """Tests for POST /admin/enroll-student (InsightFace pipeline)."""

    @patch("admin.incremental_enroll")
    @patch("admin.get_db_connection")
    def test_enroll_new_student_success(self, mock_conn, mock_enroll):
        """New student with valid images should enroll successfully."""
        conn = MagicMock()
        cursor = MagicMock()
        conn.cursor.return_value = cursor
        mock_conn.return_value = conn
        cursor.fetchone.return_value = None  # student does not exist yet
        mock_enroll.return_value = True  # embedding stored

        img = _make_b64_image()
        response = client.post(
            "/admin/enroll-student",
            headers={"X-Privilege-Level": "2"},
            json={
                "prn": "PRN001",
                "name": "Alice",
                "year": "FY",
                "course": "B.Tech",
                "specialisation": "CSE",
                "rollno": "1",
                "panel": "H",
                "images": [img] * 5,
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["prn"] == "PRN001"
        assert "enrolled" in data["message"].lower()
        # incremental_enroll called once per image
        assert mock_enroll.call_count == 5

    @patch("admin.incremental_enroll")
    @patch("admin.get_db_connection")
    def test_enroll_updates_existing_student(self, mock_conn, mock_enroll):
        """Existing student should be updated (not rejected)."""
        conn = MagicMock()
        cursor = MagicMock()
        conn.cursor.return_value = cursor
        mock_conn.return_value = conn
        cursor.fetchone.return_value = ("PRN001",)  # student exists
        mock_enroll.return_value = True

        img = _make_b64_image()
        response = client.post(
            "/admin/enroll-student",
            headers={"X-Privilege-Level": "2"},
            json={
                "prn": "PRN001",
                "name": "Alice Updated",
                "year": "SY",
                "course": "B.Tech",
                "specialisation": "CSE",
                "rollno": "1",
                "panel": "H",
                "images": [img],
            },
        )

        assert response.status_code == status.HTTP_200_OK
        # UPDATE should have been called
        executed_sqls = [str(call[0][0]) for call in cursor.execute.call_args_list]
        assert any("UPDATE" in sql for sql in executed_sqls)

    @patch("admin.incremental_enroll")
    @patch("admin.get_db_connection")
    def test_enroll_no_faces_detected_returns_400(self, mock_conn, mock_enroll):
        """If no embeddings are stored (all images fail), return 400."""
        conn = MagicMock()
        cursor = MagicMock()
        conn.cursor.return_value = cursor
        mock_conn.return_value = conn
        cursor.fetchone.return_value = None
        mock_enroll.return_value = False  # no face detected in any image

        img = _make_b64_image()
        response = client.post(
            "/admin/enroll-student",
            headers={"X-Privilege-Level": "2"},
            json={
                "prn": "PRN002",
                "name": "Bob",
                "year": "FY",
                "course": "B.Tech",
                "specialisation": "CSE",
                "rollno": "2",
                "panel": "H",
                "images": [img],
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "face" in response.json()["detail"].lower()

    def test_enroll_teacher_privilege_returns_403(self):
        """Privilege level 3 must not enroll students."""
        response = client.post(
            "/admin/enroll-student",
            headers={"X-Privilege-Level": "3"},
            json={
                "prn": "PRN003",
                "name": "Carol",
                "year": "FY",
                "course": "B.Tech",
                "specialisation": "CSE",
                "rollno": "3",
                "panel": "H",
                "images": [_make_b64_image()],
            },
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_enroll_missing_required_fields_returns_422(self):
        """Missing Pydantic-required fields must return 422."""
        response = client.post(
            "/admin/enroll-student",
            headers={"X-Privilege-Level": "2"},
            json={"prn": "PRN004"},  # missing name, year, course, etc.
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_enroll_no_privilege_header_returns_403(self):
        """Missing X-Privilege-Level header must return 403."""
        response = client.post(
            "/admin/enroll-student",
            json={
                "prn": "PRN005",
                "name": "Dave",
                "year": "FY",
                "course": "B.Tech",
                "specialisation": "CSE",
                "rollno": "5",
                "panel": "H",
                "images": [_make_b64_image()],
            },
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


# ---------------------------------------------------------------------------
# POST /admin/create-teacher
# ---------------------------------------------------------------------------

class TestCreateTeacherEndpoint:
    """Tests for POST /admin/create-teacher."""

    @patch("admin.get_db_connection")
    def test_create_teacher_success(self, mock_conn):
        """Valid payload should create a teacher and return user_id."""
        conn = MagicMock()
        cursor = MagicMock()
        conn.cursor.return_value = cursor
        mock_conn.return_value = conn
        cursor.fetchone.side_effect = [None, (99,)]  # no duplicate, then user_id

        response = client.post(
            "/admin/create-teacher",
            headers={"X-Privilege-Level": "2"},
            json={
                "username": "newteacher",
                "password": "secret123",
                "name": "New Teacher",
                "email_id": "teacher@uni.edu",
                "school": "Engineering",
                "department": "CS",
                "mob": "9999999999",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["user_id"] == 99
        assert "created" in data["message"].lower()

    @patch("admin.get_db_connection")
    def test_create_teacher_duplicate_username_returns_409(self, mock_conn):
        """Duplicate username must return 409."""
        conn = MagicMock()
        cursor = MagicMock()
        conn.cursor.return_value = cursor
        mock_conn.return_value = conn
        cursor.fetchone.return_value = (1,)  # username exists

        response = client.post(
            "/admin/create-teacher",
            headers={"X-Privilege-Level": "2"},
            json={
                "username": "existing",
                "password": "pass",
                "name": "Existing",
                "email_id": "e@uni.edu",
                "school": "Eng",
                "department": "CS",
                "mob": "0000000000",
            },
        )

        assert response.status_code == status.HTTP_409_CONFLICT

    def test_create_teacher_no_privilege_returns_403(self):
        """Privilege level 3 must not create teachers."""
        response = client.post(
            "/admin/create-teacher",
            headers={"X-Privilege-Level": "3"},
            json={
                "username": "t",
                "password": "p",
                "name": "T",
                "email_id": "t@t.com",
                "school": "S",
                "department": "D",
                "mob": "1",
            },
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


# ---------------------------------------------------------------------------
# GET /admin/lectures
# ---------------------------------------------------------------------------

class TestGetAllLecturesEndpoint:
    """Tests for GET /admin/lectures."""

    @patch("admin.execute_query")
    def test_get_lectures_returns_list(self, mock_query):
        """Should return a list of lecture dicts with username field."""
        row = MagicMock()
        row.lec_id = 1
        row.lec_name = "DS"
        row.panel = "H"
        row.year = "FY"
        row.specialisation = "CSE"
        row.course_code = "CS201"
        row.lecture_datetime = "2024-01-15 10:00:00"
        row.attendance_status = "N"
        row.lecorlab = "lec"
        row.username = "teacher1"
        mock_query.return_value = [row]

        response = client.get(
            "/admin/lectures",
            headers={"X-Privilege-Level": "2"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["username"] == "teacher1"
        assert data[0]["lec_name"] == "DS"

    @patch("admin.execute_query")
    def test_get_lectures_empty_returns_empty_list(self, mock_query):
        """Empty table should return []."""
        mock_query.return_value = []

        response = client.get(
            "/admin/lectures",
            headers={"X-Privilege-Level": "2"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    def test_get_lectures_teacher_privilege_returns_403(self):
        """Privilege level 3 must not access admin lectures."""
        response = client.get(
            "/admin/lectures",
            headers={"X-Privilege-Level": "3"},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


# ---------------------------------------------------------------------------
# GET /admin/attendance-analytics
# ---------------------------------------------------------------------------

class TestAttendanceAnalyticsEndpoint:
    """Tests for GET /admin/attendance-analytics."""

    @patch("admin.execute_query")
    def test_analytics_no_matching_lectures(self, mock_query):
        """No matching lectures should return zero-count response."""
        mock_query.return_value = []  # no lectures found

        response = client.get(
            "/admin/attendance-analytics?course_code=NONE&panel=Z",
            headers={"X-Privilege-Level": "2"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["totalLectures"] == 0
        assert data["students"] == []

    @patch("admin.execute_query")
    def test_analytics_returns_student_breakdown(self, mock_query):
        """Should return per-student present/absent counts."""
        # Call 1: lecture rows
        lec_row = MagicMock()
        lec_row.lec_id = 1
        lec_row.lec_name = "DS"
        lec_row.panel = "H"
        lec_row.course_code = "CS201"

        # Call 2: student rows
        stu_row = MagicMock()
        stu_row.prn = "PRN001"
        stu_row.name = "Alice"

        # Call 3: attendance rows
        att_row = MagicMock()
        att_row.prn = "PRN001"
        att_row.present_count = 1

        mock_query.side_effect = [[lec_row], [stu_row], [att_row]]

        response = client.get(
            "/admin/attendance-analytics?course_code=CS201&panel=H",
            headers={"X-Privilege-Level": "2"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["totalLectures"] == 1
        assert len(data["students"]) == 1
        assert data["students"][0]["prn"] == "PRN001"
        assert data["students"][0]["present"] == 1

    def test_analytics_teacher_privilege_returns_403(self):
        """Privilege level 3 must not access analytics."""
        response = client.get(
            "/admin/attendance-analytics",
            headers={"X-Privilege-Level": "3"},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
