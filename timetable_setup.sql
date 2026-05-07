-- ============================================================================
-- TIMETABLE FEATURE - DATABASE MIGRATION
-- Run this in SQL Server Management Studio (SSMS) against AttendanceDB
-- ============================================================================

USE AttendanceDB;
GO

-- ============================================================================
-- Step 1: Create Lecture_Schedule table (recurring timetable templates)
-- ============================================================================
IF OBJECT_ID('Lecture_Schedule', 'U') IS NULL
BEGIN
    CREATE TABLE Lecture_Schedule (
        schedule_id     INT PRIMARY KEY IDENTITY(1,1),
        user_id         INT NOT NULL,
        lec_name        VARCHAR(100) NOT NULL,
        course_code     VARCHAR(20) NOT NULL,
        lecorlab        VARCHAR(20) NOT NULL,      -- 'lec' or 'lab'
        year            VARCHAR(20) NOT NULL,
        specialisation  VARCHAR(50) NOT NULL,
        panel           VARCHAR(10) NOT NULL,
        day_of_week     VARCHAR(10) NOT NULL,       -- 'Monday','Tuesday',...,'Sunday'
        start_time      TIME NOT NULL,              -- e.g. 10:45:00
        sem_start_date  DATE NOT NULL,
        sem_end_date    DATE NOT NULL,
        is_active       BIT NOT NULL DEFAULT 1,
        created_at      DATETIME DEFAULT GETDATE(),
        CONSTRAINT FK_Schedule_User FOREIGN KEY (user_id)
            REFERENCES Login_Master(user_id) ON DELETE CASCADE,
        CONSTRAINT CK_Schedule_Day CHECK (day_of_week IN (
            'Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'
        ))
    );
    PRINT 'Created table: Lecture_Schedule';
END
ELSE
    PRINT 'Table Lecture_Schedule already exists - skipped.';
GO

-- Index for fast day+user lookups
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Schedule_UserId_Day')
    CREATE INDEX IX_Schedule_UserId_Day ON Lecture_Schedule(user_id, day_of_week);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Schedule_Day')
    CREATE INDEX IX_Schedule_Day ON Lecture_Schedule(day_of_week);
GO


-- ============================================================================
-- Step 2: Add schedule_id FK column to Lecture_Master
--         (links each lecture instance back to its recurring template)
-- ============================================================================
IF NOT EXISTS (
    SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = 'Lecture_Master' AND COLUMN_NAME = 'schedule_id'
)
BEGIN
    ALTER TABLE Lecture_Master
        ADD schedule_id INT NULL;

    PRINT 'Added column: schedule_id to Lecture_Master';
END
ELSE
    PRINT 'Column schedule_id already exists in Lecture_Master - skipped.';
GO

-- Add FK constraint for schedule_id
IF OBJECT_ID('FK_Lecture_Schedule', 'F') IS NULL
    AND OBJECT_ID('Lecture_Schedule', 'U') IS NOT NULL
BEGIN
    ALTER TABLE Lecture_Master
        ADD CONSTRAINT FK_Lecture_Schedule
            FOREIGN KEY (schedule_id) REFERENCES Lecture_Schedule(schedule_id);
    PRINT 'Added FK: Lecture_Master.schedule_id -> Lecture_Schedule.schedule_id';
END
GO


-- ============================================================================
-- Verification
-- ============================================================================
PRINT '';
PRINT '=== Migration Complete ===';
PRINT '';

SELECT 'Lecture_Schedule columns:' AS info;
SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = 'Lecture_Schedule'
ORDER BY ORDINAL_POSITION;

SELECT 'Lecture_Master schedule_id column:' AS info;
SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = 'Lecture_Master'
  AND COLUMN_NAME = 'schedule_id';
GO


