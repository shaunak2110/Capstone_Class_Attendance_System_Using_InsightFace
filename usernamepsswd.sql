USE AttendanceDB;
GO

-- Insert or update the default Superadmin account
-- Password: Super@admin

IF EXISTS (SELECT 1 FROM Login_Master WHERE username = 'superadmin@mitwpu.edu.in')
BEGIN
    UPDATE Login_Master
    SET password_hash = '$2b$12$rb35pVJMsmeypCGI3PzJUO6CJAYmLXYsSUB1VQsQ6AtjEMlix4Bl2',
        privilege_level = 1
    WHERE username = 'superadmin@mitwpu.edu.in';
    PRINT 'Updated existing superadmin password hash.';
END
ELSE
BEGIN
    INSERT INTO Login_Master (username, password_hash, privilege_level)
    VALUES ('superadmin@mitwpu.edu.in', '$2b$12$rb35pVJMsmeypCGI3PzJUO6CJAYmLXYsSUB1VQsQ6AtjEMlix4Bl2', 1);

    INSERT INTO User_Master (user_id, name, email_id, school, department)
    SELECT user_id, 'Super Admin', 'superadmin@mitwpu.edu.in', 'Administration', 'IT'
    FROM Login_Master WHERE username = 'superadmin@mitwpu.edu.in';

    PRINT 'Inserted new superadmin account.';
END
GO

SELECT user_id, username, privilege_level FROM Login_Master WHERE username = 'superadmin@mitwpu.edu.in';
GO


