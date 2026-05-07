"""
CSV generation service for attendance records.

This service generates CSV files containing attendance records after attendance
is finalized. It queries lecture details, teacher information, student roster,
and attendance records to create comprehensive attendance reports.

Requirements: 11.2, 11.3, 11.4, 11.5, 11.6, 11.7
"""

import os
import csv
import platform
from datetime import datetime
from typing import Optional
from database import execute_query


def _get_output_dir() -> str:
    """
    Return the directory where attendance CSV files should be written.

    On Windows (local development): uses the backend/Attendance Records/ directory
    anchored to the backend/ folder (parent of services/).

    On Linux/Mac (Render cloud): uses /tmp/Attendance Records/ which is always
    writable on Render's ephemeral filesystem.
    """
    if platform.system() == 'Windows':
        return os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "Attendance Records"
        )
    else:
        return "/tmp/Attendance Records"


def generate_attendance_csv(lec_id: int) -> str:
    """
    Generate a CSV file containing attendance records for a finalized lecture.
    
    This function performs the following steps:
    1. Query Lecture_Master for lecture details (lec_name, panel, lecture_datetime, user_id)
    2. Query User_Master for teacher name by user_id
    3. Query Student_Master for all students in the panel
    4. Query Attendance_Record for students marked present in this lecture
    5. Build CSV with columns: Student PRN, Student Name, Status, Lecture Name, Panel, DateTime, Teacher Name
    6. Mark students in Attendance_Record as "Present", others as "Absent"
    7. Create "Attendance Records/" directory if it doesn't exist
    8. Generate filename: {panel}_{lec_name}_{datetime}.csv
    9. Save CSV file and return file path
    
    Args:
        lec_id: Lecture ID for which to generate attendance CSV
        
    Returns:
        str: File path of the generated CSV file
        
    Raises:
        ValueError: If lecture ID is not found or lecture has no panel/name
        Exception: If database query fails or file writing fails
        
    Example:
        >>> csv_path = generate_attendance_csv(lec_id=123)
        >>> print(f"CSV saved to: {csv_path}")
        CSV saved to: Attendance Records/H_Python Programming_2024-01-15_14-30.csv
    """
    # Step 1: Query Lecture_Master for lecture details
    lecture_query = """
        SELECT lec_name, panel, lecture_datetime, user_id
        FROM Lecture_Master
        WHERE lec_id = %s
    """
    lecture_results = execute_query(lecture_query, (lec_id,), fetch=True)
    
    if not lecture_results or len(lecture_results) == 0:
        raise ValueError(f"Lecture with ID {lec_id} not found")
    
    lecture = lecture_results[0]
    lec_name = lecture.lec_name
    panel = lecture.panel
    lecture_datetime = lecture.lecture_datetime
    user_id = lecture.user_id
    
    if not lec_name or not panel:
        raise ValueError(f"Lecture {lec_id} is missing required fields (lec_name or panel)")
    
    # Step 2: Query User_Master for teacher name
    teacher_query = """
        SELECT name
        FROM User_Master
        WHERE user_id = %s
    """
    teacher_results = execute_query(teacher_query, (user_id,), fetch=True)
    
    if not teacher_results or len(teacher_results) == 0:
        teacher_name = "Unknown Teacher"
    else:
        teacher_name = teacher_results[0].name
    
    # Step 3: Query Student_Master for all students in the panel
    students_query = """
        SELECT prn, name
        FROM Student_Master
        WHERE panel = %s
        ORDER BY prn
    """
    students_results = execute_query(students_query, (panel,), fetch=True)
    
    if not students_results or len(students_results) == 0:
        raise ValueError(f"No students found in panel {panel}")
    
    # Step 4: Query Attendance_Record for students marked present
    attendance_query = """
        SELECT prn
        FROM Attendance_Record
        WHERE lec_id = %s AND status = 'Present'
    """
    attendance_results = execute_query(attendance_query, (lec_id,), fetch=True)
    
    # Create set of PRNs marked present for quick lookup
    present_prns = set()
    if attendance_results:
        present_prns = {row.prn for row in attendance_results}
    
    # Step 5: Build attendance records list
    attendance_records = []
    for student in students_results:
        prn = student.prn
        name = student.name
        
        # Step 6: Mark students as Present or Absent
        status = "Present" if prn in present_prns else "Absent"
        
        attendance_records.append({
            'Student PRN': prn,
            'Student Name': name,
            'Status': status,
            'Lecture Name': lec_name,
            'Panel': panel,
            'DateTime': lecture_datetime.strftime('%Y-%m-%d %H:%M:%S') if isinstance(lecture_datetime, datetime) else str(lecture_datetime),
            'Teacher Name': teacher_name
        })
    
    # Step 7: Create output directory if it doesn't exist
    # Uses /tmp/Attendance Records on Linux/Render, backend/Attendance Records on Windows
    directory = _get_output_dir()
    if not os.path.exists(directory):
        os.makedirs(directory)
    
    # Step 8: Generate filename: {panel}_{lec_name}_{datetime}.csv
    # Format datetime for filename (replace spaces and colons with safe characters)
    if isinstance(lecture_datetime, datetime):
        datetime_str = lecture_datetime.strftime('%Y-%m-%d_%H-%M')
    else:
        # Handle string datetime
        datetime_str = str(lecture_datetime).replace(' ', '_').replace(':', '-')
    
    # Sanitize lec_name for filename (remove special characters)
    safe_lec_name = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in lec_name)
    safe_lec_name = safe_lec_name.replace(' ', '_')
    
    filename = f"{panel}_{safe_lec_name}_{datetime_str}.csv"
    filepath = os.path.join(directory, filename)
    
    # Step 9: Save CSV file
    try:
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['Student PRN', 'Student Name', 'Status', 'Lecture Name', 'Panel', 'DateTime', 'Teacher Name']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            # Write header
            writer.writeheader()
            
            # Write attendance records
            for record in attendance_records:
                writer.writerow(record)
        
        return filepath
        
    except Exception as e:
        raise Exception(f"Failed to write CSV file: {str(e)}")
