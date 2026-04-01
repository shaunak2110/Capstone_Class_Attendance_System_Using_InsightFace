USE AttendanceDB;
GO

INSERT INTO Login_Master (username, password_hash, privilege_level)
VALUES ('superadmin@mitwpu.edu.in', '$2b$12$w5nvctbOZU4SBymjYS36.e7GJIPhk/gWfjIr8ddgJ5QC6AafJP/rm', 1);
GO


SELECT * FROM Login_Master;


INSERT INTO User_Master (user_id, name, email_id, school, department)
VALUES (1, 'Super Admin', 'superadmin@mitwpu.edu.in', 'Administration', 'IT');



SELECT * FROM Login_Master;