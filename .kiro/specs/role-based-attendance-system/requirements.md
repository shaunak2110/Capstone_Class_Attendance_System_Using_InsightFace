# Requirements Document

## Introduction

This document specifies the requirements for a role-based attendance system with facial recognition capabilities. The system enables educational institutions to manage user privileges, schedule lectures, and automate attendance marking using facial recognition technology. The system supports three privilege levels: Super Admin (level 1), Admin (level 2), and User/Teacher (level 3).

## Glossary

- **Attendance_System**: The complete role-based attendance management application
- **Authentication_Service**: The component responsible for validating user credentials
- **Login_Master**: Database table storing user authentication credentials and privilege levels
- **User_Master**: Database table storing detailed user profile information
- **Student_Master**: Database table storing student information and panel assignments
- **Lecture_Master**: Database table storing scheduled lecture information
- **Request_Master**: Database table storing privilege escalation requests
- **Face_Recognition_Engine**: The component that detects and recognizes faces in images
- **Face_Model**: The neural network model that generates face embeddings
- **Embedding**: A 128-dimensional vector representation of a face
- **PRN**: Permanent Registration Number - unique identifier for students
- **Privilege_Level**: Integer value (1, 2, or 3) indicating user access rights
- **Attendance_Status**: Character flag ('Y' or 'N') indicating if attendance has been finalized
- **Panel**: Class section identifier (e.g., 'H', 'I')
- **Cosine_Similarity**: Mathematical measure of similarity between face embeddings
- **Incremental_Training**: Process of updating the model with new student data without full retraining

## Requirements

### Requirement 1: User Authentication

**User Story:** As a system user, I want to authenticate with my credentials, so that I can access features appropriate to my privilege level

#### Acceptance Criteria

1. WHEN a user submits valid credentials, THE Authentication_Service SHALL return the user_id, username, and Privilege_Level from Login_Master
2. WHEN a user submits invalid credentials, THE Authentication_Service SHALL return an authentication error message
3. THE Authentication_Service SHALL validate credentials against the Login_Master table using the database connection
4. THE Authentication_Service SHALL retrieve database connection parameters from environment variables
5. THE Authentication_Service SHALL use the pyodbc library for database connectivity

### Requirement 2: Privilege-Based Access Control

**User Story:** As a system administrator, I want users to have different access levels, so that sensitive operations are restricted to authorized personnel

#### Acceptance Criteria

1. THE Attendance_System SHALL support exactly three Privilege_Level values: 1 for Super Admin, 2 for Admin, and 3 for User
2. WHEN a user with Privilege_Level 1 authenticates, THE Attendance_System SHALL grant access to Super Admin features
3. WHEN a user with Privilege_Level 2 authenticates, THE Attendance_System SHALL grant access to Admin features
4. WHEN a user with Privilege_Level 3 authenticates, THE Attendance_System SHALL grant access to User features
5. THE Attendance_System SHALL deny access to features that require higher privileges than the authenticated user possesses

### Requirement 3: Privilege Escalation Request Management

**User Story:** As a Super Admin, I want to review and approve privilege escalation requests, so that I can promote users to Admin status

#### Acceptance Criteria

1. THE Attendance_System SHALL retrieve pending privilege escalation requests from the Request_Master table
2. WHEN a Super Admin approves a request, THE Attendance_System SHALL update the user's Privilege_Level from 3 to 2 in Login_Master
3. WHEN a Super Admin approves a request, THE Attendance_System SHALL update the user's Privilege_Level from 3 to 2 in User_Master
4. THE Attendance_System SHALL maintain referential integrity between Login_Master and User_Master during privilege updates
5. WHEN a privilege escalation is approved, THE Attendance_System SHALL remove the corresponding record from Request_Master

### Requirement 4: Admin User Creation by Super Admin

**User Story:** As a Super Admin, I want to create new Admin accounts, so that I can delegate administrative responsibilities

#### Acceptance Criteria

1. WHEN a Super Admin creates a new Admin account, THE Attendance_System SHALL insert a record with Privilege_Level 2 into Login_Master
2. WHEN a Super Admin creates a new Admin account, THE Attendance_System SHALL insert a corresponding record into User_Master
3. THE Attendance_System SHALL ensure the user_id is identical in both Login_Master and User_Master for the new Admin
4. THE Attendance_System SHALL enforce username uniqueness across Login_Master
5. THE Attendance_System SHALL require all mandatory User_Master fields (name, email_id, school, department) for new Admin accounts

### Requirement 5: Teacher Account Management

**User Story:** As an Admin, I want to create teacher accounts, so that teachers can schedule lectures and mark attendance

#### Acceptance Criteria

1. WHEN an Admin creates a teacher account, THE Attendance_System SHALL insert a record with Privilege_Level 3 into Login_Master
2. WHEN an Admin creates a teacher account, THE Attendance_System SHALL insert a corresponding record into User_Master
3. THE Attendance_System SHALL ensure the user_id is identical in both Login_Master and User_Master for the new teacher
4. THE Attendance_System SHALL enforce username uniqueness across Login_Master
5. THE Attendance_System SHALL require all mandatory User_Master fields (name, email_id, school, department, mob) for new teacher accounts

### Requirement 6: Student Enrollment with Facial Recognition

**User Story:** As an Admin, I want to enroll students with their facial data, so that the system can recognize them during attendance

#### Acceptance Criteria

1. WHEN an Admin enrolls a student, THE Attendance_System SHALL accept exactly 25 face images for training
2. WHEN an Admin enrolls a student, THE Attendance_System SHALL insert the student record into Student_Master with PRN, name, and Panel
3. THE Attendance_System SHALL use the Face_Model to generate Embedding vectors from the provided images
4. THE Attendance_System SHALL perform incremental training on the Face_Model using the new student images
5. THE Attendance_System SHALL save the updated Face_Model weights to trained_face_brain.pth after enrollment
6. THE Attendance_System SHALL ensure PRN uniqueness in Student_Master
7. THE Attendance_System SHALL associate each student with exactly one Panel identifier

### Requirement 7: Lecture Scheduling

**User Story:** As a teacher, I want to schedule lectures, so that I can later mark attendance for those sessions

#### Acceptance Criteria

1. WHEN a teacher schedules a lecture, THE Attendance_System SHALL insert a record into Lecture_Master
2. THE Attendance_System SHALL set Attendance_Status to 'N' for newly scheduled lectures
3. THE Attendance_System SHALL require the following fields for lecture scheduling: user_id, school, department, lecorlab, Panel, lec_name, course_code, lecture_datetime
4. THE Attendance_System SHALL associate the lecture with the authenticated teacher's user_id
5. THE Attendance_System SHALL generate a unique lec_id for each scheduled lecture

### Requirement 8: Scheduled Lecture Retrieval

**User Story:** As a teacher, I want to view my scheduled lectures, so that I can select which lecture to mark attendance for

#### Acceptance Criteria

1. WHEN a teacher requests their scheduled lectures, THE Attendance_System SHALL retrieve all Lecture_Master records matching the teacher's user_id
2. THE Attendance_System SHALL return lecture details including lec_id, lec_name, Panel, lecture_datetime, and Attendance_Status
3. THE Attendance_System SHALL order returned lectures by lecture_datetime in descending order

### Requirement 9: Facial Recognition for Attendance

**User Story:** As a teacher, I want to capture classroom images and have the system recognize students, so that attendance marking is automated

#### Acceptance Criteria

1. WHEN a teacher initiates attendance marking, THE Attendance_System SHALL accept multiple images and a lecture_id
2. THE Face_Recognition_Engine SHALL detect all faces present in the provided images
3. THE Face_Recognition_Engine SHALL generate Embedding vectors for each detected face
4. THE Face_Recognition_Engine SHALL compare each face Embedding against stored student Embeddings using Cosine_Similarity
5. WHEN a face matches a known student with similarity above the threshold, THE Face_Recognition_Engine SHALL identify the student by PRN
6. WHEN a face does not match any known student, THE Face_Recognition_Engine SHALL return the cropped face image as unidentified
7. THE Attendance_System SHALL return a list of identified students and unidentified face images to the teacher

### Requirement 10: Unidentified Face Resolution

**User Story:** As a teacher, I want to resolve unidentified faces, so that all students present are accurately recorded

#### Acceptance Criteria

1. WHEN a teacher indicates an unidentified face belongs to an existing student, THE Attendance_System SHALL verify the PRN exists in Student_Master
2. WHEN a teacher indicates an unidentified face belongs to an existing student, THE Attendance_System SHALL mark that student as present for the lecture
3. WHEN a teacher indicates an unidentified face belongs to an existing student, THE Attendance_System SHALL perform incremental training using the cropped face image
4. WHEN a teacher indicates an unidentified face is not part of the class, THE Attendance_System SHALL discard the image
5. WHEN a teacher indicates an unidentified face is a new student, THE Attendance_System SHALL insert the student into Student_Master
6. WHEN a teacher indicates an unidentified face is a new student, THE Attendance_System SHALL perform incremental training using the cropped face image
7. THE Attendance_System SHALL save updated Face_Model weights after processing all unidentified faces

### Requirement 11: Attendance Record Finalization

**User Story:** As a teacher, I want to finalize attendance after resolving all faces, so that a permanent record is created

#### Acceptance Criteria

1. WHEN a teacher finalizes attendance, THE Attendance_System SHALL update the Attendance_Status to 'Y' in Lecture_Master for the specified lecture
2. WHEN a teacher finalizes attendance, THE Attendance_System SHALL generate a CSV file containing attendance records
3. THE Attendance_System SHALL include the following columns in the CSV: Student PRN, Student Name, Status, Lecture Name, Panel, DateTime, Teacher Name
4. THE Attendance_System SHALL list all students enrolled in the Panel as either Present or Absent
5. THE Attendance_System SHALL save the CSV file in the "Attendance Records/" directory
6. THE Attendance_System SHALL name the CSV file using the format: {panel}_{lec_name}_{datetime}.csv
7. IF the "Attendance Records/" directory does not exist, THEN THE Attendance_System SHALL create it before saving the CSV file

### Requirement 12: Face Model Persistence

**User Story:** As a system administrator, I want the facial recognition model to retain learned faces, so that recognition accuracy improves over time

#### Acceptance Criteria

1. THE Face_Model SHALL load existing weights from trained_face_brain.pth at system startup
2. WHEN the Face_Model is updated through incremental training, THE Attendance_System SHALL save the updated weights to trained_face_brain.pth
3. THE Face_Model SHALL maintain a mapping between PRN values and Embedding vectors
4. THE Face_Model SHALL preserve previously learned student Embeddings when adding new students

### Requirement 13: Security and Password Management

**User Story:** As a security-conscious administrator, I want passwords to be protected, so that user accounts remain secure

#### Acceptance Criteria

1. THE Attendance_System SHALL hash passwords using bcrypt before storing them in Login_Master
2. THE Attendance_System SHALL compare hashed passwords during authentication
3. THE Attendance_System SHALL retrieve database credentials from environment variables rather than hardcoded values
4. THE Attendance_System SHALL implement CORS (Cross-Origin Resource Sharing) support for frontend integration
5. THE Attendance_System SHALL return appropriate HTTP status codes for all error conditions

### Requirement 14: API Architecture and Structure

**User Story:** As a developer, I want a well-organized backend structure, so that the codebase is maintainable and scalable

#### Acceptance Criteria

1. THE Attendance_System SHALL implement a RESTful API using the FastAPI framework
2. THE Attendance_System SHALL organize code into the following modules: main.py, database.py, auth.py, admin.py, user.py, superadmin.py
3. THE Attendance_System SHALL organize facial recognition code into: model/face_model.py, model/inference.py
4. THE Attendance_System SHALL organize business logic into: services/recognition_service.py, services/training_service.py, services/csv_service.py
5. THE Attendance_System SHALL be executable using the command: uvicorn main:app --reload

### Requirement 15: Error Handling and Validation

**User Story:** As a system user, I want clear error messages when operations fail, so that I can understand and correct issues

#### Acceptance Criteria

1. WHEN a database operation fails, THE Attendance_System SHALL return a descriptive error message and appropriate HTTP status code
2. WHEN required fields are missing from a request, THE Attendance_System SHALL return a validation error listing the missing fields
3. WHEN a face cannot be detected in an image, THE Face_Recognition_Engine SHALL return an error indicating no face was found
4. WHEN a PRN already exists during student enrollment, THE Attendance_System SHALL return a duplicate error
5. WHEN a user attempts an operation without sufficient privileges, THE Attendance_System SHALL return an authorization error with HTTP status 403
