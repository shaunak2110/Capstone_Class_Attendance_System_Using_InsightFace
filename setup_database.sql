-- ============================================================================
-- Role-Based Attendance System Database Setup Script
-- ============================================================================
-- This script creates all required database tables with proper constraints,
-- indexes, and relationships for the attendance management system.
--
-- Tables:
--   1. Login_Master - User authentication credentials and privilege levels
--   2. User_Master - Detailed user profile information
--   3. Student_Master - Student enrollment records
--   4. Lecture_Master - Scheduled lecture information
--   5. Request_Master - Privilege escalation requests
--   6. Attendance_Record - Attendance tracking records
-- ============================================================================

-- Create database if it doesn't exist
IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = 'AttendanceDB')
BEGIN
    CREATE DATABASE AttendanceDB;
END
GO

USE AttendanceDB;
GO

-- ============================================================================
-- Table: Login_Master
-- Purpose: Stores user authentication credentials and privilege levels
-- Privilege Levels: 1 = Super Admin, 2 = Admin, 3 = User/Teacher
-- ============================================================================
IF OBJECT_ID('Login_Master', 'U') IS NOT NULL
    DROP TABLE Login_Master;
GO

CREATE TABLE Login_Master (
    user_id INT PRIMARY KEY IDENTITY(1,1),
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    privilege_level INT NOT NULL,
    CONSTRAINT CK_Login_Privilege CHECK (privilege_level IN (1, 2, 3))
);
GO

-- Index for authentication queries
CREATE INDEX IX_Login_Username ON Login_Master(username);
GO

-- ============================================================================
-- Table: User_Master
-- Purpose: Stores detailed user profile information
-- Relationships: References Login_Master via user_id (1:1 relationship)
-- ============================================================================
IF OBJECT_ID('User_Master', 'U') IS NOT NULL
    DROP TABLE User_Master;
GO

CREATE TABLE User_Master (
    user_id INT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email_id VARCHAR(100) NOT NULL,
    school VARCHAR(100) NOT NULL,
    department VARCHAR(100) NOT NULL,
    mob VARCHAR(15),
    CONSTRAINT FK_User_Login FOREIGN KEY (user_id) REFERENCES Login_Master(user_id) ON DELETE CASCADE
);
GO

-- Index for user lookups
CREATE INDEX IX_User_UserId ON User_Master(user_id);
GO

-- ============================================================================
-- Table: Student_Master
-- Purpose: Stores student enrollment records with panel assignments
-- PRN: Permanent Registration Number (unique student identifier)
-- Panel: Class section identifier (e.g., 'H', 'I')
-- ============================================================================
IF OBJECT_ID('Student_Master', 'U') IS NOT NULL
    DROP TABLE Student_Master;
GO

CREATE TABLE Student_Master (
    prn VARCHAR(20) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    panel VARCHAR(10) NOT NULL
);
GO

-- Index for panel-based queries (used in attendance marking)
CREATE INDEX IX_Student_Panel ON Student_Master(panel);
GO

-- ============================================================================
-- Table: Lecture_Master
-- Purpose: Stores scheduled lecture information and attendance status
-- Attendance_Status: 'N' = Not finalized, 'Y' = Finalized
-- ============================================================================
IF OBJECT_ID('Lecture_Master', 'U') IS NOT NULL
    DROP TABLE Lecture_Master;
GO

CREATE TABLE Lecture_Master (
    lec_id INT PRIMARY KEY IDENTITY(1,1),
    user_id INT NOT NULL,
    school VARCHAR(100) NOT NULL,
    department VARCHAR(100) NOT NULL,
    lecorlab VARCHAR(20) NOT NULL,
    panel VARCHAR(10) NOT NULL,
    lec_name VARCHAR(100) NOT NULL,
    course_code VARCHAR(20) NOT NULL,
    lecture_datetime DATETIME NOT NULL,
    attendance_status CHAR(1) DEFAULT 'N' NOT NULL,
    CONSTRAINT FK_Lecture_User FOREIGN KEY (user_id) REFERENCES Login_Master(user_id) ON DELETE CASCADE,
    CONSTRAINT CK_Lecture_Status CHECK (attendance_status IN ('Y', 'N'))
);
GO

-- Index for teacher's lecture queries
CREATE INDEX IX_Lecture_UserId ON Lecture_Master(user_id);
GO

-- Index for lecture lookup by ID
CREATE INDEX IX_Lecture_LecId ON Lecture_Master(lec_id);
GO

-- Index for panel-based queries
CREATE INDEX IX_Lecture_Panel ON Lecture_Master(panel);
GO

-- ============================================================================
-- Table: Request_Master
-- Purpose: Stores privilege escalation requests from users to admins
-- Relationships: References Login_Master via user_id
-- ============================================================================
IF OBJECT_ID('Request_Master', 'U') IS NOT NULL
    DROP TABLE Request_Master;
GO

CREATE TABLE Request_Master (
    request_id INT PRIMARY KEY IDENTITY(1,1),
    user_id INT NOT NULL,
    requested_at DATETIME DEFAULT GETDATE() NOT NULL,
    CONSTRAINT FK_Request_User FOREIGN KEY (user_id) REFERENCES Login_Master(user_id) ON DELETE CASCADE
);
GO

-- Index for pending request queries
CREATE INDEX IX_Request_UserId ON Request_Master(user_id);
GO

-- ============================================================================
-- Table: Attendance_Record
-- Purpose: Tracks attendance records for students in lectures
-- Status: 'Present' or 'Absent'
-- Relationships: References Lecture_Master and Student_Master
-- ============================================================================
IF OBJECT_ID('Attendance_Record', 'U') IS NOT NULL
    DROP TABLE Attendance_Record;
GO

CREATE TABLE Attendance_Record (
    attendance_id INT PRIMARY KEY IDENTITY(1,1),
    lec_id INT NOT NULL,
    prn VARCHAR(20) NOT NULL,
    status VARCHAR(10) NOT NULL,
    marked_at DATETIME DEFAULT GETDATE() NOT NULL,
    CONSTRAINT FK_Attendance_Lecture FOREIGN KEY (lec_id) REFERENCES Lecture_Master(lec_id) ON DELETE CASCADE,
    CONSTRAINT FK_Attendance_Student FOREIGN KEY (prn) REFERENCES Student_Master(prn) ON DELETE CASCADE,
    CONSTRAINT CK_Attendance_Status CHECK (status IN ('Present', 'Absent'))
);
GO

-- Index for lecture-based attendance queries
CREATE INDEX IX_Attendance_LecId ON Attendance_Record(lec_id);
GO

-- Index for student-based attendance queries
CREATE INDEX IX_Attendance_PRN ON Attendance_Record(prn);
GO

-- Composite index for efficient attendance lookups
CREATE INDEX IX_Attendance_LecId_PRN ON Attendance_Record(lec_id, prn);
GO

-- ============================================================================
-- Verification Queries
-- ============================================================================
PRINT 'Database setup completed successfully!';
PRINT '';
PRINT 'Created tables:';
SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE' ORDER BY TABLE_NAME;
GO
