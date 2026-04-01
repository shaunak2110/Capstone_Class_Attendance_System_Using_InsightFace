CREATE DATABASE AttendanceDB;
GO


USE AttendanceDB;
GO



CREATE TABLE Login_Master (
    user_id INT PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    password VARCHAR(100) NOT NULL,
    privilege INT NOT NULL
);
GO


INSERT INTO Login_Master (user_id, username, password, privilege) VALUES
(1, 'superadmin@mitwpu.edu.in', 'Super@admin', 1),
(2, 'admin1@mitwpu.edu.in', 'Admin1@mit', 2),
(3, 'user@mitwpu.edu.in', 'User@mit', 3),
(4, 'user2@mitwpu.edu.in', 'User2@mit', 3);
GO



CREATE TABLE User_Master (
    user_id INT PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    password VARCHAR(100) NOT NULL,
    name VARCHAR(100),
    mob VARCHAR(15),
    email_id VARCHAR(100),
    privilege INT,
    school VARCHAR(150),
    department VARCHAR(150),
    FOREIGN KEY (user_id) REFERENCES Login_Master(user_id)
);
GO




INSERT INTO User_Master 
(user_id, username, password, name, mob, email_id, privilege, school, department)
VALUES
(2, 'admin1@mitwpu.edu.in', 'Admin1@mit', 'Admin1 MIT', '7620946932', 'shaunakdalvi12@gmail.com', 2, 'Computer Engineering and Technology', 'Computer Science and Engineering'),

(1, 'superadmin@mitwpu.edu.in', 'Super@admin', 'Super Admin', '7620946932', 'shaunakdalvi12@gmail.com', 1, 'nil', 'nil'),

(3, 'user@mitwpu.edu.in', 'User@mit', 'User MIT', '7620946932', 'shaunakdalvi12@gmail.com', 3, 'Computer Engineering and Technology', 'Computer Science and Engineering');
GO



CREATE TABLE Lecture_Master (
    lec_id INT PRIMARY KEY,
    user_id INT,
    school VARCHAR(150),
    department VARCHAR(150),
    lecorlab VARCHAR(10),
    panel VARCHAR(10),
    lec_name VARCHAR(150),
    course_code VARCHAR(50),
    lecture_datetime DATETIME,
    attendance_status CHAR(1),
    FOREIGN KEY (user_id) REFERENCES User_Master(user_id)
);
GO




INSERT INTO Lecture_Master
(lec_id, user_id, school, department, lecorlab, panel, lec_name, course_code, lecture_datetime, attendance_status)
VALUES
(1, 3, 'Computer Engineering and Technology', 'Computer Science and Engineering', 'lec', 'H', 'High Performance Computing', 'CET4005B', '2026-03-13 10:45:00', 'Y'),

(2, 3, 'Computer Engineering and Technology', 'Computer Science and Engineering', 'lec', 'I', 'High Performance Computing', 'CET4005B', '2026-03-13 11:45:00', 'Y'),

(3, 3, 'Computer Engineering and Technology', 'Computer Science and Engineering', 'lab', 'H', 'High Performance Computing', 'CET4005B', '2026-03-13 13:30:00', 'N');
GO




CREATE TABLE Student_Master (
    RollNo INT PRIMARY KEY,
    PRN BIGINT UNIQUE,
    panel VARCHAR(10),
    name VARCHAR(150)
);
GO




INSERT INTO Student_Master (RollNo, PRN, panel, name) VALUES
(12, 1032221489, 'H', 'Shaunak Dinesh Dalvi'),
(8, 1032220455, 'H', 'Sudhanshu Santosh Athanimath');
GO




CREATE TABLE Request_Master (
    request_id INT PRIMARY KEY,
    user_id INT,
    privilege INT,
    username VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(100),
    FOREIGN KEY (user_id) REFERENCES User_Master(user_id)
);
GO



SELECT * FROM Login_Master;
SELECT * FROM User_Master;
SELECT * FROM Lecture_Master;
SELECT * FROM Student_Master;
SELECT * FROM Request_Master;

SELECT user_id, username, privilege_level FROM Login_Master;


UPDATE Login_Master 
SET password_hash = '$2b$12$ybsUKoYcrr/n.xY7MmALNORpjqMACKXWYN8mMD4Eqw7bN312VDXT.'
WHERE username = 'teacher2@mitwpu.edu.in';
