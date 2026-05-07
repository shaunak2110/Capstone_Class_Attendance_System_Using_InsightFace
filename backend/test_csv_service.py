"""
Unit tests for CSV generation service.

Tests the generate_attendance_csv function to ensure it correctly:
- Queries lecture details from Lecture_Master
- Queries teacher name from User_Master
- Queries all students in the panel from Student_Master
- Queries attendance records from Attendance_Record
- Generates CSV with correct columns and data
- Creates directory if it doesn't exist
- Generates correct filename format
"""

import pytest
import os
import csv
from datetime import datetime
from services.csv_service import generate_attendance_csv
from database import execute_query


class TestCSVService:
    """Test suite for CSV generation service."""
    
    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """Setup test data before each test and cleanup after."""
        # Setup: Create test data
        self.test_user_id = None
        self.test_lec_id = None
        self.test_prns = []
        self.csv_filepath = None
        
        try:
            # Create test teacher
            execute_query(
                "INSERT INTO Login_Master (username, password_hash, privilege_level) VALUES (?, ?, ?)",
                ("test_csv_teacher", "hash123", 3),
                fetch=False
            )
            
            # Get the user_id
            result = execute_query(
                "SELECT user_id FROM Login_Master WHERE username = ?",
                ("test_csv_teacher",),
                fetch=True
            )
            self.test_user_id = result[0].user_id
            
            # Create user master record
            execute_query(
                "INSERT INTO User_Master (user_id, name, email_id, school, department, mob) VALUES (?, ?, ?, ?, ?, ?)",
                (self.test_user_id, "Test CSV Teacher", "csv@test.com", "Engineering", "CS", "1234567890"),
                fetch=False
            )
            
            # Create test students in panel "TEST"
            test_students = [
                ("CSV001", "Alice Test", "TEST"),
                ("CSV002", "Bob Test", "TEST"),
                ("CSV003", "Charlie Test", "TEST")
            ]
            
            for prn, name, panel in test_students:
                self.test_prns.append(prn)
                execute_query(
                    "INSERT INTO Student_Master (prn, name, panel) VALUES (?, ?, ?)",
                    (prn, name, panel),
                    fetch=False
                )
            
            # Create test lecture
            execute_query(
                "INSERT INTO Lecture_Master (user_id, school, department, lecorlab, panel, lec_name, course_code, lecture_datetime, attendance_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (self.test_user_id, "Engineering", "CS", "Lecture", "TEST", "CSV Test Lecture", "CS101", datetime(2024, 1, 15, 14, 30), 'Y'),
                fetch=False
            )
            
            # Get the lec_id
            result = execute_query(
                "SELECT lec_id FROM Lecture_Master WHERE user_id = ? AND lec_name = ?",
                (self.test_user_id, "CSV Test Lecture"),
                fetch=True
            )
            self.test_lec_id = result[0].lec_id
            
            # Mark first two students as present
            execute_query(
                "INSERT INTO Attendance_Record (lec_id, prn, status) VALUES (?, ?, ?)",
                (self.test_lec_id, "CSV001", "Present"),
                fetch=False
            )
            execute_query(
                "INSERT INTO Attendance_Record (lec_id, prn, status) VALUES (?, ?, ?)",
                (self.test_lec_id, "CSV002", "Present"),
                fetch=False
            )
            
        except Exception as e:
            print(f"Setup error: {e}")
            raise
        
        yield
        
        # Teardown: Clean up test data
        try:
            # Delete attendance records
            if self.test_lec_id:
                execute_query(
                    "DELETE FROM Attendance_Record WHERE lec_id = ?",
                    (self.test_lec_id,),
                    fetch=False
                )
            
            # Delete lecture
            if self.test_lec_id:
                execute_query(
                    "DELETE FROM Lecture_Master WHERE lec_id = ?",
                    (self.test_lec_id,),
                    fetch=False
                )
            
            # Delete students
            for prn in self.test_prns:
                execute_query(
                    "DELETE FROM Student_Master WHERE prn = ?",
                    (prn,),
                    fetch=False
                )
            
            # Delete user master
            if self.test_user_id:
                execute_query(
                    "DELETE FROM User_Master WHERE user_id = ?",
                    (self.test_user_id,),
                    fetch=False
                )
            
            # Delete login master
            if self.test_user_id:
                execute_query(
                    "DELETE FROM Login_Master WHERE user_id = ?",
                    (self.test_user_id,),
                    fetch=False
                )
            
            # Delete generated CSV file
            if self.csv_filepath and os.path.exists(self.csv_filepath):
                os.remove(self.csv_filepath)
                
        except Exception as e:
            print(f"Teardown error: {e}")
    
    def test_generate_csv_creates_file(self):
        """Test that CSV file is created successfully."""
        self.csv_filepath = generate_attendance_csv(self.test_lec_id)
        
        assert os.path.exists(self.csv_filepath), "CSV file should be created"
        assert self.csv_filepath.startswith("Attendance Records/"), "CSV should be in correct directory"
    
    def test_generate_csv_filename_format(self):
        """Test that CSV filename follows the correct format: {panel}_{lec_name}_{datetime}.csv"""
        self.csv_filepath = generate_attendance_csv(self.test_lec_id)
        
        filename = os.path.basename(self.csv_filepath)
        assert filename.startswith("TEST_"), "Filename should start with panel"
        assert "CSV_Test_Lecture" in filename, "Filename should contain lecture name"
        assert filename.endswith(".csv"), "Filename should end with .csv"
    
    def test_generate_csv_correct_columns(self):
        """Test that CSV has correct column headers."""
        self.csv_filepath = generate_attendance_csv(self.test_lec_id)
        
        with open(self.csv_filepath, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            fieldnames = reader.fieldnames
            
            expected_columns = ['Student PRN', 'Student Name', 'Status', 'Lecture Name', 'Panel', 'DateTime', 'Teacher Name']
            assert fieldnames == expected_columns, f"CSV should have correct columns. Got: {fieldnames}"
    
    def test_generate_csv_all_students_included(self):
        """Test that CSV includes all students in the panel."""
        self.csv_filepath = generate_attendance_csv(self.test_lec_id)
        
        with open(self.csv_filepath, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            rows = list(reader)
            
            assert len(rows) == 3, "CSV should include all 3 students in panel"
            
            prns_in_csv = {row['Student PRN'] for row in rows}
            assert prns_in_csv == {"CSV001", "CSV002", "CSV003"}, "CSV should include all test students"
    
    def test_generate_csv_correct_attendance_status(self):
        """Test that CSV correctly marks students as Present or Absent."""
        self.csv_filepath = generate_attendance_csv(self.test_lec_id)
        
        with open(self.csv_filepath, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            rows = list(reader)
            
            # Create dict for easy lookup
            status_by_prn = {row['Student PRN']: row['Status'] for row in rows}
            
            assert status_by_prn['CSV001'] == 'Present', "CSV001 should be marked Present"
            assert status_by_prn['CSV002'] == 'Present', "CSV002 should be marked Present"
            assert status_by_prn['CSV003'] == 'Absent', "CSV003 should be marked Absent"
    
    def test_generate_csv_includes_lecture_details(self):
        """Test that CSV includes correct lecture details in each row."""
        self.csv_filepath = generate_attendance_csv(self.test_lec_id)
        
        with open(self.csv_filepath, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            rows = list(reader)
            
            # Check first row (all rows should have same lecture details)
            first_row = rows[0]
            assert first_row['Lecture Name'] == 'CSV Test Lecture', "Should include correct lecture name"
            assert first_row['Panel'] == 'TEST', "Should include correct panel"
            assert first_row['Teacher Name'] == 'Test CSV Teacher', "Should include correct teacher name"
            assert '2024-01-15' in first_row['DateTime'], "Should include correct date"
    
    def test_generate_csv_creates_directory(self):
        """Test that CSV generation creates directory if it doesn't exist."""
        # Remove directory if it exists
        directory = "Attendance Records"
        if os.path.exists(directory):
            # Remove any files first
            for file in os.listdir(directory):
                os.remove(os.path.join(directory, file))
            os.rmdir(directory)
        
        assert not os.path.exists(directory), "Directory should not exist before test"
        
        self.csv_filepath = generate_attendance_csv(self.test_lec_id)
        
        assert os.path.exists(directory), "Directory should be created"
        assert os.path.exists(self.csv_filepath), "CSV file should be created in new directory"
    
    def test_generate_csv_invalid_lecture_id(self):
        """Test that invalid lecture ID raises ValueError."""
        with pytest.raises(ValueError, match="Lecture with ID .* not found"):
            generate_attendance_csv(lec_id=999999)
    
    def test_generate_csv_no_students_in_panel(self):
        """Test that lecture with no students in panel raises ValueError."""
        # Create a lecture with a panel that has no students
        execute_query(
            "INSERT INTO Lecture_Master (user_id, school, department, lecorlab, panel, lec_name, course_code, lecture_datetime, attendance_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (self.test_user_id, "Engineering", "CS", "Lecture", "EMPTY", "Empty Panel Lecture", "CS999", datetime.now(), 'Y'),
            fetch=False
        )
        
        result = execute_query(
            "SELECT lec_id FROM Lecture_Master WHERE lec_name = ?",
            ("Empty Panel Lecture",),
            fetch=True
        )
        empty_lec_id = result[0].lec_id
        
        try:
            with pytest.raises(ValueError, match="No students found in panel"):
                generate_attendance_csv(lec_id=empty_lec_id)
        finally:
            # Cleanup
            execute_query(
                "DELETE FROM Lecture_Master WHERE lec_id = ?",
                (empty_lec_id,),
                fetch=False
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


# ===========================================================================
# Feature: cloud-deployment, Property 5: CSV output directory selection
# Validates: Requirements 8.1, 8.3
# ===========================================================================

import platform as _platform
from unittest.mock import patch
from hypothesis import given, settings
from hypothesis import strategies as st
from services.csv_service import _get_output_dir


@given(platform_name=st.sampled_from(['Windows', 'Linux', 'Darwin']))
@settings(max_examples=100)
def test_pbt_csv_output_dir_contains_attendance_records(platform_name):
    """
    Property 5: For any OS platform, _get_output_dir() must return a path
    containing 'Attendance Records'.
    """
    with patch('services.csv_service.platform.system', return_value=platform_name):
        result = _get_output_dir()
        assert 'Attendance Records' in result


@given(platform_name=st.sampled_from(['Linux', 'Darwin']))
@settings(max_examples=50)
def test_pbt_csv_output_dir_starts_with_tmp_on_non_windows(platform_name):
    """
    Property 5 (non-Windows): On Linux/Darwin, _get_output_dir() must start with /tmp.
    """
    with patch('services.csv_service.platform.system', return_value=platform_name):
        result = _get_output_dir()
        assert result.startswith('/tmp'), f"Expected /tmp prefix on {platform_name}, got: {result}"


def test_csv_output_dir_windows_does_not_use_tmp():
    """On Windows, _get_output_dir() must NOT use /tmp."""
    with patch('services.csv_service.platform.system', return_value='Windows'):
        result = _get_output_dir()
        assert '/tmp' not in result
        assert 'Attendance Records' in result


def test_csv_output_dir_linux_uses_tmp():
    """On Linux, _get_output_dir() must return /tmp/Attendance Records."""
    with patch('services.csv_service.platform.system', return_value='Linux'):
        result = _get_output_dir()
        assert result == '/tmp/Attendance Records'


def test_csv_output_dir_darwin_uses_tmp():
    """On Darwin (macOS), _get_output_dir() must return /tmp/Attendance Records."""
    with patch('services.csv_service.platform.system', return_value='Darwin'):
        result = _get_output_dir()
        assert result == '/tmp/Attendance Records'
