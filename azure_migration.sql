-- ============================================================================
-- Azure SQL Migration Script
-- AttendanceDB Schema — Azure SQL Compatible
-- ============================================================================
-- NOTES:
--   • No USE master / CREATE DATABASE / USE AttendanceDB — Azure SQL connections
--     already target the database selected in the connection string.
--   • No Trusted_Connection — SQL authentication only.
--   • Idempotent: safe to re-run on a database that already has the schema.
--   • GO batch separators are supported by SSMS and sqlcmd.
--
-- Creation order (respects FK dependencies):
--   1. Login_Master        (root — no FKs)
--   2. User_Master         (FK → Login_Master)
--   3. Student_Master      (no FKs)
--   4. Lecture_Schedule    (FK → Login_Master)
--   5. Lecture_Master      (FK → Login_Master, FK → Lecture_Schedule)
--   6. Student_Embeddings  (FK → Student_Master)
--   7. Request_Master      (FK → Login_Master)
--   8. Attendance_Record   (FK → Lecture_Master, FK → Student_Master)
-- ============================================================================

-- ============================================================================
-- TABLE: Login_Master
-- Root authentication table. All users (superadmin, admin, teacher) live here.
-- privilege_level: 1 = Superadmin, 2 = Admin, 3 = Teacher
-- ============================================================================
IF OBJECT_ID('Login_Master', 'U') IS NULL
BEGIN
    CREATE TABLE Login_Master (
        user_id         INT           PRIMARY KEY IDENTITY(1,1),
        username        VARCHAR(100)  NOT NULL,
        password_hash   VARCHAR(255)  NOT NULL,
        privilege_level INT           NOT NULL,

        CONSTRAINT UQ_Login_Username  UNIQUE (username),
        CONSTRAINT CK_Login_Privilege CHECK  (privilege_level IN (1, 2, 3))
    );
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Login_Username' AND object_id = OBJECT_ID('Login_Master'))
    CREATE INDEX IX_Login_Username ON Login_Master (username);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Login_PrivilegeLevel' AND object_id = OBJECT_ID('Login_Master'))
    CREATE INDEX IX_Login_PrivilegeLevel ON Login_Master (privilege_level);
GO

-- ============================================================================
-- TABLE: User_Master
-- Extended profile for every Login_Master user (1:1 relationship).
-- mob is nullable — superadmin/admin creation form doesn't always collect it.
-- ============================================================================
IF OBJECT_ID('User_Master', 'U') IS NULL
BEGIN
    CREATE TABLE User_Master (
        user_id     INT           PRIMARY KEY,
        name        VARCHAR(100)  NOT NULL,
        email_id    VARCHAR(100)  NOT NULL,
        school      VARCHAR(150)  NOT NULL,
        department  VARCHAR(150)  NOT NULL,
        mob         VARCHAR(15)   NULL,

        CONSTRAINT FK_User_Login
            FOREIGN KEY (user_id) REFERENCES Login_Master (user_id)
            ON DELETE CASCADE
    );
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_User_UserId' AND object_id = OBJECT_ID('User_Master'))
    CREATE INDEX IX_User_UserId ON User_Master (user_id);
GO

-- ============================================================================
-- TABLE: Student_Master
-- One row per enrolled student. PRN is the natural primary key.
-- ============================================================================
IF OBJECT_ID('Student_Master', 'U') IS NULL
BEGIN
    CREATE TABLE Student_Master (
        prn             VARCHAR(20)   PRIMARY KEY,
        name            VARCHAR(100)  NOT NULL,
        rollno          VARCHAR(20)   NOT NULL,
        year            VARCHAR(20)   NOT NULL,
        course          VARCHAR(100)  NOT NULL,
        specialisation  VARCHAR(100)  NOT NULL,
        panel           VARCHAR(10)   NOT NULL
    );
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Student_Panel' AND object_id = OBJECT_ID('Student_Master'))
    CREATE INDEX IX_Student_Panel ON Student_Master (panel);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Student_Year_Spec' AND object_id = OBJECT_ID('Student_Master'))
    CREATE INDEX IX_Student_Year_Spec ON Student_Master (year, specialisation);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Student_Panel_Year_Spec' AND object_id = OBJECT_ID('Student_Master'))
    CREATE INDEX IX_Student_Panel_Year_Spec ON Student_Master (panel, year, specialisation);
GO

-- ============================================================================
-- TABLE: Lecture_Schedule
-- Recurring timetable templates. One row per recurring lecture slot.
-- day_of_week: 'Monday' through 'Sunday'
-- lecorlab: 'lec' or 'lab'
-- ============================================================================
IF OBJECT_ID('Lecture_Schedule', 'U') IS NULL
BEGIN
    CREATE TABLE Lecture_Schedule (
        schedule_id     INT           PRIMARY KEY IDENTITY(1,1),
        user_id         INT           NOT NULL,
        lec_name        VARCHAR(100)  NOT NULL,
        course_code     VARCHAR(20)   NOT NULL,
        lecorlab        VARCHAR(20)   NOT NULL,
        year            VARCHAR(20)   NOT NULL,
        specialisation  VARCHAR(50)   NOT NULL,
        panel           VARCHAR(10)   NOT NULL,
        day_of_week     VARCHAR(10)   NOT NULL,
        start_time      TIME          NOT NULL,
        sem_start_date  DATE          NOT NULL,
        sem_end_date    DATE          NOT NULL,
        is_active       BIT           NOT NULL DEFAULT 1,
        created_at      DATETIME               DEFAULT GETDATE(),

        CONSTRAINT FK_Schedule_User
            FOREIGN KEY (user_id) REFERENCES Login_Master (user_id)
            ON DELETE CASCADE,
        CONSTRAINT CK_Schedule_Day CHECK (day_of_week IN (
            'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'
        )),
        CONSTRAINT CK_Schedule_LecOrLab CHECK (lecorlab IN ('lec', 'lab'))
    );
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Schedule_UserId_Day' AND object_id = OBJECT_ID('Lecture_Schedule'))
    CREATE INDEX IX_Schedule_UserId_Day ON Lecture_Schedule (user_id, day_of_week);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Schedule_Day' AND object_id = OBJECT_ID('Lecture_Schedule'))
    CREATE INDEX IX_Schedule_Day ON Lecture_Schedule (day_of_week);
GO

-- ============================================================================
-- TABLE: Lecture_Master
-- One row per scheduled lecture session.
-- schedule_id FK → Lecture_Schedule (nullable — links instance to template).
-- ============================================================================
IF OBJECT_ID('Lecture_Master', 'U') IS NULL
BEGIN
    CREATE TABLE Lecture_Master (
        lec_id            INT           PRIMARY KEY IDENTITY(1,1),
        user_id           INT           NOT NULL,
        school            VARCHAR(150)  NOT NULL,
        department        VARCHAR(150)  NOT NULL,
        year              VARCHAR(20)   NOT NULL,
        specialisation    VARCHAR(100)  NOT NULL,
        lecorlab          VARCHAR(20)   NOT NULL,
        panel             VARCHAR(10)   NOT NULL,
        lec_name          VARCHAR(150)  NOT NULL,
        course_code       VARCHAR(50)   NOT NULL,
        lecture_datetime  DATETIME      NOT NULL,
        attendance_status CHAR(1)       NOT NULL DEFAULT 'N',
        schedule_id       INT           NULL,

        CONSTRAINT FK_Lecture_User
            FOREIGN KEY (user_id) REFERENCES Login_Master (user_id)
            ON DELETE CASCADE,
        CONSTRAINT FK_Lecture_Schedule
            FOREIGN KEY (schedule_id) REFERENCES Lecture_Schedule (schedule_id),
        CONSTRAINT CK_Lecture_Status
            CHECK (attendance_status IN ('Y', 'N')),
        CONSTRAINT CK_Lecture_Type
            CHECK (lecorlab IN ('lec', 'lab'))
    );
END
GO

-- If Lecture_Master already existed without schedule_id, add the column and FK
IF NOT EXISTS (
    SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = 'Lecture_Master' AND COLUMN_NAME = 'schedule_id'
)
BEGIN
    ALTER TABLE Lecture_Master ADD schedule_id INT NULL;
END
GO

IF OBJECT_ID('FK_Lecture_Schedule', 'F') IS NULL
    AND OBJECT_ID('Lecture_Schedule', 'U') IS NOT NULL
BEGIN
    ALTER TABLE Lecture_Master
        ADD CONSTRAINT FK_Lecture_Schedule
            FOREIGN KEY (schedule_id) REFERENCES Lecture_Schedule (schedule_id);
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Lecture_UserId' AND object_id = OBJECT_ID('Lecture_Master'))
    CREATE INDEX IX_Lecture_UserId ON Lecture_Master (user_id);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Lecture_Panel' AND object_id = OBJECT_ID('Lecture_Master'))
    CREATE INDEX IX_Lecture_Panel ON Lecture_Master (panel);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Lecture_DateTime' AND object_id = OBJECT_ID('Lecture_Master'))
    CREATE INDEX IX_Lecture_DateTime ON Lecture_Master (lecture_datetime DESC);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Lecture_Status' AND object_id = OBJECT_ID('Lecture_Master'))
    CREATE INDEX IX_Lecture_Status ON Lecture_Master (attendance_status);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Lecture_Year_Spec' AND object_id = OBJECT_ID('Lecture_Master'))
    CREATE INDEX IX_Lecture_Year_Spec ON Lecture_Master (year, specialisation);
GO

-- ============================================================================
-- TABLE: Student_Embeddings
-- Stores InsightFace 512-dim face embeddings per student.
-- embedding stored as VARBINARY(MAX): 512 float32 × 4 bytes = 2048 bytes/row.
-- ============================================================================
IF OBJECT_ID('Student_Embeddings', 'U') IS NULL
BEGIN
    CREATE TABLE Student_Embeddings (
        embedding_id  INT              PRIMARY KEY IDENTITY(1,1),
        prn           VARCHAR(20)      NOT NULL,
        embedding     VARBINARY(MAX)   NOT NULL,
        created_at    DATETIME         NOT NULL DEFAULT GETDATE(),

        CONSTRAINT FK_Embedding_Student
            FOREIGN KEY (prn) REFERENCES Student_Master (prn)
            ON DELETE CASCADE
    );
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Embedding_PRN' AND object_id = OBJECT_ID('Student_Embeddings'))
    CREATE INDEX IX_Embedding_PRN ON Student_Embeddings (prn);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Embedding_PRN_Created' AND object_id = OBJECT_ID('Student_Embeddings'))
    CREATE INDEX IX_Embedding_PRN_Created ON Student_Embeddings (prn, created_at DESC);
GO

-- ============================================================================
-- TABLE: Request_Master
-- Privilege escalation requests submitted by teachers (privilege 3)
-- asking to be promoted to admin (privilege 2).
-- ============================================================================
IF OBJECT_ID('Request_Master', 'U') IS NULL
BEGIN
    CREATE TABLE Request_Master (
        request_id   INT       PRIMARY KEY IDENTITY(1,1),
        user_id      INT       NOT NULL,
        requested_at DATETIME  NOT NULL DEFAULT GETDATE(),

        CONSTRAINT FK_Request_User
            FOREIGN KEY (user_id) REFERENCES Login_Master (user_id)
            ON DELETE CASCADE
    );
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Request_UserId' AND object_id = OBJECT_ID('Request_Master'))
    CREATE INDEX IX_Request_UserId ON Request_Master (user_id);
GO

-- ============================================================================
-- TABLE: Attendance_Record
-- One row per (lecture, student) pair. Status is either Present or Absent.
-- Unique constraint on (lec_id, prn) prevents double-marking.
-- ============================================================================
IF OBJECT_ID('Attendance_Record', 'U') IS NULL
BEGIN
    CREATE TABLE Attendance_Record (
        attendance_id  INT          PRIMARY KEY IDENTITY(1,1),
        lec_id         INT          NOT NULL,
        prn            VARCHAR(20)  NOT NULL,
        status         VARCHAR(10)  NOT NULL,
        marked_at      DATETIME     NOT NULL DEFAULT GETDATE(),

        CONSTRAINT FK_Attendance_Lecture
            FOREIGN KEY (lec_id) REFERENCES Lecture_Master (lec_id)
            ON DELETE CASCADE,
        CONSTRAINT FK_Attendance_Student
            FOREIGN KEY (prn) REFERENCES Student_Master (prn),
        CONSTRAINT CK_Attendance_Status
            CHECK (status IN ('Present', 'Absent')),
        CONSTRAINT UQ_Attendance_LecId_PRN
            UNIQUE (lec_id, prn)
    );
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Attendance_LecId' AND object_id = OBJECT_ID('Attendance_Record'))
    CREATE INDEX IX_Attendance_LecId ON Attendance_Record (lec_id);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Attendance_PRN' AND object_id = OBJECT_ID('Attendance_Record'))
    CREATE INDEX IX_Attendance_PRN ON Attendance_Record (prn);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Attendance_Status' AND object_id = OBJECT_ID('Attendance_Record'))
    CREATE INDEX IX_Attendance_Status ON Attendance_Record (status);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Attendance_MarkedAt' AND object_id = OBJECT_ID('Attendance_Record'))
    CREATE INDEX IX_Attendance_MarkedAt ON Attendance_Record (marked_at DESC);
GO

-- ============================================================================
-- VERIFICATION
-- ============================================================================
PRINT 'Azure SQL migration completed successfully.';
PRINT 'Tables created or verified:';
SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE' ORDER BY TABLE_NAME;
GO
