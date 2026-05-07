USE AttendanceDB;

SELECT 
    l.user_id,
    l.username,
    l.privilege_level,
    CASE l.privilege_level 
        WHEN 1 THEN 'Superadmin'
        WHEN 2 THEN 'Admin'
        WHEN 3 THEN 'Teacher'
    END AS role,
    u.name,
    l.password_hash
FROM Login_Master l
JOIN User_Master u ON l.user_id = u.user_id
ORDER BY l.privilege_level, u.name;
