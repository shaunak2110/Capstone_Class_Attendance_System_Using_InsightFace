-- ============================================================================
-- Role-Based Attendance System with InsightFace
-- Full Database Setup Script
-- ============================================================================
-- Drop order respects all foreign key dependencies:
--   Student_Embeddings → Student_Master
--   Attendance_Record  → Lecture_Master, Student_Master
--   Lecture_Master     → Login_Master
--   Request_Master     → Login_Master
--   User_Master        → Login_Master
--   Login_Master       (root)
-- ============================================================================

USE master;
GO

IF EXISTS (SELECT name FROM sys.databases WHERE name = 'AttendanceDB')
BEGIN
    ALTER DATABASE AttendanceDB SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
    DROP DATABASE AttendanceDB;
END
GO

CREATE DATABASE AttendanceDB;
GO

USE AttendanceDB;
GO

-- ============================================================================
-- DROP TABLES (safe order: children before parents)
-- ============================================================================

IF OBJECT_ID('Student_Embeddings', 'U') IS NOT NULL DROP TABLE Student_Embeddings;
IF OBJECT_ID('Attendance_Record',  'U') IS NOT NULL DROP TABLE Attendance_Record;
IF OBJECT_ID('Lecture_Master',     'U') IS NOT NULL DROP TABLE Lecture_Master;
IF OBJECT_ID('Student_Master',     'U') IS NOT NULL DROP TABLE Student_Master;
IF OBJECT_ID('Request_Master',     'U') IS NOT NULL DROP TABLE Request_Master;
IF OBJECT_ID('User_Master',        'U') IS NOT NULL DROP TABLE User_Master;
IF OBJECT_ID('Login_Master',       'U') IS NOT NULL DROP TABLE Login_Master;
GO

-- ============================================================================
-- TABLE: Login_Master
-- Root authentication table. All users (superadmin, admin, teacher) live here.
-- privilege_level: 1 = Superadmin, 2 = Admin, 3 = Teacher
-- ============================================================================
CREATE TABLE Login_Master (
    user_id         INT           PRIMARY KEY IDENTITY(1,1),
    username        VARCHAR(100)  NOT NULL,
    password_hash   VARCHAR(255)  NOT NULL,
    privilege_level INT           NOT NULL,

    CONSTRAINT UQ_Login_Username    UNIQUE (username),
    CONSTRAINT CK_Login_Privilege   CHECK  (privilege_level IN (1, 2, 3))
);
GO

CREATE INDEX IX_Login_Username       ON Login_Master (username);
CREATE INDEX IX_Login_PrivilegeLevel ON Login_Master (privilege_level);
GO

-- ============================================================================
-- TABLE: User_Master
-- Extended profile for every Login_Master user (1:1 relationship).
-- mob is nullable — superadmin/admin creation form doesn't always collect it.
-- ============================================================================
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
GO

CREATE INDEX IX_User_UserId ON User_Master (user_id);
GO

-- ============================================================================
-- TABLE: Student_Master
-- One row per enrolled student. PRN is the natural primary key.
-- year, course, specialisation, rollno added to match frontend enrollment form
-- and to support panel-based roster queries in user.py enrolled-students endpoint.
-- ============================================================================
CREATE TABLE Student_Master (
    prn             VARCHAR(20)   PRIMARY KEY,
    name            VARCHAR(100)  NOT NULL,
    rollno          VARCHAR(20)   NOT NULL,
    year            VARCHAR(20)   NOT NULL,
    course          VARCHAR(100)  NOT NULL,
    specialisation  VARCHAR(100)  NOT NULL,
    panel           VARCHAR(10)   NOT NULL
);
GO

CREATE INDEX IX_Student_Panel          ON Student_Master (panel);
CREATE INDEX IX_Student_Year_Spec      ON Student_Master (year, specialisation);
CREATE INDEX IX_Student_Panel_Year_Spec ON Student_Master (panel, year, specialisation);
GO

-- ============================================================================
-- TABLE: Student_Embeddings
-- Stores InsightFace 512-dim face embeddings per student.
-- One student can have multiple embedding rows (one per enrolled image).
-- The backend averages them at query time to form the centroid, or stores
-- the pre-averaged centroid as a single row — both patterns are supported.
-- embedding is stored as VARBINARY(MAX):
--   512 float32 values × 4 bytes = 2048 bytes per row (well within limits).
-- The backend serializes/deserializes using numpy: 
--   np.frombuffer(row.embedding, dtype=np.float32)
--   embedding_bytes = embedding.astype(np.float32).tobytes()
-- ============================================================================
CREATE TABLE Student_Embeddings (
    embedding_id  INT              PRIMARY KEY IDENTITY(1,1),
    prn           VARCHAR(20)      NOT NULL,
    embedding     VARBINARY(MAX)   NOT NULL,
    created_at    DATETIME         NOT NULL DEFAULT GETDATE(),

    CONSTRAINT FK_Embedding_Student
        FOREIGN KEY (prn) REFERENCES Student_Master (prn)
        ON DELETE CASCADE
);
GO

CREATE INDEX IX_Embedding_PRN        ON Student_Embeddings (prn);
CREATE INDEX IX_Embedding_PRN_Created ON Student_Embeddings (prn, created_at DESC);
GO

-- ============================================================================
-- TABLE: Lecture_Master
-- One row per scheduled lecture session.
-- user_id FK → Login_Master (not User_Master) to match backend admin.py and
-- user.py which join directly against Login_Master.user_id.
-- year + specialisation stored here so enrolled-students lookup can filter
-- Student_Master by (year, specialisation, panel) without extra joins.
-- ============================================================================
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

    CONSTRAINT FK_Lecture_User
        FOREIGN KEY (user_id) REFERENCES Login_Master (user_id)
        ON DELETE CASCADE,
    CONSTRAINT CK_Lecture_Status
        CHECK (attendance_status IN ('Y', 'N')),
    CONSTRAINT CK_Lecture_Type
        CHECK (lecorlab IN ('lec', 'lab'))
);
GO

CREATE INDEX IX_Lecture_UserId        ON Lecture_Master (user_id);
CREATE INDEX IX_Lecture_Panel         ON Lecture_Master (panel);
CREATE INDEX IX_Lecture_DateTime      ON Lecture_Master (lecture_datetime DESC);
CREATE INDEX IX_Lecture_Status        ON Lecture_Master (attendance_status);
CREATE INDEX IX_Lecture_Year_Spec     ON Lecture_Master (year, specialisation);
GO

-- ============================================================================
-- TABLE: Request_Master
-- Privilege escalation requests submitted by teachers (privilege 3)
-- asking to be promoted to admin (privilege 2).
-- Superadmin approves via POST /superadmin/approve-request.
-- ============================================================================
CREATE TABLE Request_Master (
    request_id   INT       PRIMARY KEY IDENTITY(1,1),
    user_id      INT       NOT NULL,
    requested_at DATETIME  NOT NULL DEFAULT GETDATE(),

    CONSTRAINT FK_Request_User
        FOREIGN KEY (user_id) REFERENCES Login_Master (user_id)
        ON DELETE CASCADE
);
GO

CREATE INDEX IX_Request_UserId ON Request_Master (user_id);
GO

-- ============================================================================
-- TABLE: Attendance_Record
-- One row per (lecture, student) pair. Status is either Present or Absent.
-- Unique constraint on (lec_id, prn) prevents double-marking the same student
-- in the same lecture — enforced at DB level, not just application level.
-- ============================================================================
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
GO

CREATE INDEX IX_Attendance_LecId     ON Attendance_Record (lec_id);
CREATE INDEX IX_Attendance_PRN       ON Attendance_Record (prn);
CREATE INDEX IX_Attendance_Status    ON Attendance_Record (status);
CREATE INDEX IX_Attendance_MarkedAt  ON Attendance_Record (marked_at DESC);
GO

-- ============================================================================
-- VERIFICATION
-- ============================================================================
PRINT 'AttendanceDB schema created successfully.';
PRINT '';
PRINT 'Tables created:';
SELECT TABLE_NAME
FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_TYPE = 'BASE TABLE'
ORDER BY TABLE_NAME;
GO

PRINT '';
PRINT 'Foreign keys:';
SELECT
    fk.name                          AS constraint_name,
    tp.name                          AS parent_table,
    cp.name                          AS parent_column,
    tr.name                          AS referenced_table,
    cr.name                          AS referenced_column
FROM sys.foreign_keys fk
JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
JOIN sys.tables  tp ON fkc.parent_object_id      = tp.object_id
JOIN sys.columns cp ON fkc.parent_object_id      = cp.object_id
                    AND fkc.parent_column_id      = cp.column_id
JOIN sys.tables  tr ON fkc.referenced_object_id  = tr.object_id
JOIN sys.columns cr ON fkc.referenced_object_id  = cr.object_id
                    AND fkc.referenced_column_id  = cr.column_id
ORDER BY tp.name, fk.name;
GO

PRINT '';
PRINT 'Unique constraints:';
SELECT
    tc.TABLE_NAME,
    tc.CONSTRAINT_NAME,
    STRING_AGG(kcu.COLUMN_NAME, ', ') AS columns
FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
    ON tc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
WHERE tc.CONSTRAINT_TYPE = 'UNIQUE'
GROUP BY tc.TABLE_NAME, tc.CONSTRAINT_NAME
ORDER BY tc.TABLE_NAME;
GO
