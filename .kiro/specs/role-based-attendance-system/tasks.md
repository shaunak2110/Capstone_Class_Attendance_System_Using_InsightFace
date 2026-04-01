# Implementation Plan: Role-Based Attendance System with Facial Recognition

## Overview

This implementation plan breaks down the role-based attendance system into discrete coding tasks. The system is built with FastAPI, uses SQL Server for data persistence, and integrates a PyTorch-based facial recognition model. Tasks are organized to build incrementally, with early validation through testing and checkpoints at key milestones.

## Tasks

- [x] 1. Set up project structure and core dependencies
  - Create directory structure: model/, services/, root-level modules
  - Create requirements.txt with FastAPI, pyodbc, bcrypt, torch, hypothesis, python-dotenv, Pillow, numpy
  - Create .env.example file with database connection parameters template
  - Set up .gitignore for Python projects
  - _Requirements: 1.4, 13.3, 14.1, 14.2, 14.3, 14.4_

- [x] 2. Implement database connection module
  - [x] 2.1 Create database.py with connection management
    - Implement get_db_connection() function using pyodbc
    - Load connection parameters from environment variables (SERVER, DATABASE, UID, PWD)
    - Implement connection error handling with descriptive messages
    - Add execute_query() utility function for SQL execution
    - _Requirements: 1.3, 1.4, 13.3, 15.1_

  - [ ]* 2.2 Write property test for database connection
    - **Property 38: Error Response Structure**
    - **Validates: Requirements 13.5, 15.1**

- [x] 3. Implement authentication module
  - [x] 3.1 Create auth.py with login endpoint
    - Define LoginRequest and LoginResponse Pydantic models
    - Implement POST /auth/login endpoint
    - Query Login_Master table for username
    - Verify password using bcrypt.checkpw()
    - Return user_id, username, privilege_level on success
    - Return 401 error for invalid credentials
    - _Requirements: 1.1, 1.2, 13.2_


  - [ ]* 3.2 Write property tests for authentication
    - **Property 1: Valid Authentication Returns Complete User Data**
    - **Validates: Requirements 1.1**
    - **Property 2: Invalid Authentication Fails Appropriately**
    - **Validates: Requirements 1.2**

  - [ ]* 3.3 Write unit tests for authentication
    - Test successful login with valid credentials
    - Test failed login with invalid password
    - Test failed login with non-existent username
    - Test password hashing verification
    - _Requirements: 1.1, 1.2, 13.2_

- [x] 4. Implement Super Admin module
  - [x] 4.1 Create superadmin.py with privilege escalation endpoints
    - Define request/response Pydantic models
    - Implement GET /superadmin/requests endpoint
    - Query Request_Master for pending requests
    - Implement POST /superadmin/approve-request endpoint
    - Update privilege_level to 2 in both Login_Master and User_Master
    - Delete approved request from Request_Master
    - Add privilege validation (403 for non-super-admins)
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 2.5, 15.5_

  - [ ]* 4.2 Write property tests for privilege escalation
    - **Property 5: Pending Requests Retrieval Completeness**
    - **Validates: Requirements 3.1**
    - **Property 6: Privilege Escalation Consistency**
    - **Validates: Requirements 3.2, 3.3, 3.4**
    - **Property 7: Request Cleanup After Approval**
    - **Validates: Requirements 3.5**

  - [x] 4.3 Implement admin creation endpoint
    - Define CreateUserRequest Pydantic model
    - Implement POST /superadmin/create-admin endpoint
    - Hash password using bcrypt.hashpw()
    - Insert record into Login_Master with privilege_level=2
    - Insert corresponding record into User_Master with same user_id
    - Validate required fields (username, password, name, email_id, school, department)
    - Return 409 for duplicate username
    - Return 400 for missing fields
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 13.1, 15.2_

  - [ ]* 4.4 Write property tests for admin creation
    - **Property 8: Dual-Table User Creation**
    - **Validates: Requirements 4.1, 4.2, 4.3**
    - **Property 9: Username Uniqueness Enforcement**
    - **Validates: Requirements 4.4**
    - **Property 10: Required Field Validation**
    - **Validates: Requirements 4.5, 15.2**
    - **Property 37: Password Hashing**
    - **Validates: Requirements 13.1**

- [x] 5. Checkpoint - Ensure authentication and super admin features work
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement Admin module
  - [x] 6.1 Create admin.py with teacher creation endpoint
    - Define CreateUserRequest Pydantic model (reuse from superadmin)
    - Implement POST /admin/create-teacher endpoint
    - Hash password using bcrypt.hashpw()
    - Insert record into Login_Master with privilege_level=3
    - Insert corresponding record into User_Master with same user_id
    - Validate required fields including mob (mobile number)
    - Return 409 for duplicate username
    - Return 400 for missing fields
    - Add privilege validation (403 for non-admins)
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 13.1, 15.2, 2.5_

  - [ ]* 6.2 Write property tests for teacher creation
    - **Property 8: Dual-Table User Creation**
    - **Validates: Requirements 5.1, 5.2, 5.3**
    - **Property 9: Username Uniqueness Enforcement**
    - **Validates: Requirements 5.4**
    - **Property 10: Required Field Validation**
    - **Validates: Requirements 5.5, 15.2**

  - [x] 6.3 Implement lecture scheduling endpoint
    - Define ScheduleLectureRequest and LectureResponse Pydantic models
    - Implement POST /admin/schedule-lecture endpoint
    - Insert record into Lecture_Master with all required fields
    - Set attendance_status to 'N' by default
    - Generate unique lec_id automatically
    - Validate all required fields (user_id, school, department, lecorlab, panel, lec_name, course_code, lecture_datetime)
    - Return 400 for missing fields
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 15.2_

  - [ ]* 6.4 Write property tests for lecture scheduling
    - **Property 16: Lecture Record Creation**
    - **Validates: Requirements 7.1, 7.5**
    - **Property 17: Default Attendance Status**
    - **Validates: Requirements 7.2**
    - **Property 18: Lecture Field Validation**
    - **Validates: Requirements 7.3**
    - **Property 19: Lecture Ownership**
    - **Validates: Requirements 7.4**

- [x] 7. Implement face recognition model layer
  - [x] 7.1 Create model/face_model.py with FaceModel class
    - Implement __init__ to load trained_face_brain.pth
    - Implement generate_embedding() to create 128-dimensional vectors
    - Implement add_student() to store PRN-embedding mappings
    - Implement identify_face() using cosine similarity (threshold=0.6)
    - Implement save_model() to persist weights to trained_face_brain.pth
    - Load and save PRN-embedding mappings (pickle or within model state)
    - _Requirements: 6.3, 6.4, 9.4, 9.5, 12.1, 12.3_

  - [x] 7.2 Create model/inference.py with InferenceEngine class
    - Implement __init__ to accept FaceModel instance
    - Implement detect_faces() using face detection library (e.g., MTCNN or dlib)
    - Implement process_image() to detect faces and generate embeddings
    - Implement identify_students() to match embeddings against known students
    - Return identified students with PRN and similarity score
    - Return unidentified faces as cropped images
    - Handle cases where no faces are detected (return error)
    - _Requirements: 9.2, 9.3, 9.4, 9.5, 9.6, 15.3_

  - [ ]* 7.3 Write property tests for face recognition
    - **Property 23: Face Detection Completeness**
    - **Validates: Requirements 9.2**
    - **Property 24: Known Student Recognition**
    - **Validates: Requirements 9.5**
    - **Property 25: Unknown Face Handling**
    - **Validates: Requirements 9.6**

  - [ ]* 7.4 Write unit tests for face model
    - Test embedding generation produces 128-dimensional vectors
    - Test cosine similarity calculation
    - Test model loading from file
    - Test model saving to file
    - Test PRN-embedding mapping storage
    - _Requirements: 6.3, 9.4, 12.1, 12.2_

- [x] 8. Implement training service
  - [x] 8.1 Create services/training_service.py
    - Implement incremental_train() function
    - Accept list of face images and PRN
    - Generate embeddings for all images
    - Add embeddings to FaceModel using add_student()
    - Call save_model() to persist updated weights
    - Handle training errors gracefully
    - _Requirements: 6.4, 6.5, 10.3, 10.6, 12.2_

  - [ ]* 8.2 Write property tests for training service
    - **Property 13: Model Persistence After Training**
    - **Validates: Requirements 6.5, 10.7, 12.2**
    - **Property 36: Model Embedding Preservation**
    - **Validates: Requirements 12.4**

- [x] 9. Implement student enrollment endpoint
  - [x] 9.1 Add student enrollment to admin.py
    - Define EnrollStudentRequest Pydantic model
    - Implement POST /admin/enroll-student endpoint
    - Validate exactly 25 images provided (return 400 if not)
    - Decode base64 images to numpy arrays
    - Insert student record into Student_Master (PRN, name, panel)
    - Call training_service.incremental_train() with images and PRN
    - Return 409 for duplicate PRN
    - Return 400 for image count mismatch
    - _Requirements: 6.1, 6.2, 6.4, 6.5, 6.6, 6.7, 15.2, 15.4_

  - [ ]* 9.2 Write property tests for student enrollment
    - **Property 11: Student Enrollment Image Count Validation**
    - **Validates: Requirements 6.1**
    - **Property 12: Student Record Creation**
    - **Validates: Requirements 6.2**
    - **Property 14: PRN Uniqueness Enforcement**
    - **Validates: Requirements 6.6, 15.4**
    - **Property 15: Student-Panel Association**
    - **Validates: Requirements 6.7**

- [x] 10. Checkpoint - Ensure admin features and face model work
  - Ensure all tests pass, ask the user if questions arise.

- [x] 11. Implement recognition service
  - [x] 11.1 Create services/recognition_service.py
    - Implement recognize_students() function
    - Accept list of base64 images and lecture_id
    - Decode images to numpy arrays
    - Call InferenceEngine.process_image() for each image
    - Collect all detected faces and embeddings
    - Call InferenceEngine.identify_students() to match faces
    - Query Student_Master for student names by PRN
    - Generate unique face_id (UUID) for each unidentified face
    - Store unidentified faces temporarily (in-memory dict or cache)
    - Return identified students list and unidentified faces list
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7_

  - [ ]* 11.2 Write property tests for recognition service
    - **Property 26: Attendance Response Structure**
    - **Validates: Requirements 9.7**

  - [ ]* 11.3 Write unit tests for recognition service
    - Test batch processing of multiple images
    - Test identified student response format
    - Test unidentified face response format
    - Test face_id generation uniqueness
    - _Requirements: 9.7_

- [x] 12. Implement User/Teacher module
  - [x] 12.1 Create user.py with lecture retrieval endpoint
    - Define LectureResponse Pydantic model
    - Implement GET /user/lectures/{user_id} endpoint
    - Query Lecture_Master filtered by user_id
    - Order results by lecture_datetime DESC
    - Return list of lectures with lec_id, lec_name, panel, lecture_datetime, attendance_status
    - Return 404 if no lectures found
    - _Requirements: 8.1, 8.2, 8.3_

  - [ ]* 12.2 Write property tests for lecture retrieval
    - **Property 20: Teacher Lecture Isolation**
    - **Validates: Requirements 8.1**
    - **Property 21: Lecture Response Completeness**
    - **Validates: Requirements 8.2**
    - **Property 22: Lecture Chronological Ordering**
    - **Validates: Requirements 8.3**

  - [x] 12.3 Implement attendance marking endpoint
    - Define MarkAttendanceRequest and MarkAttendanceResponse Pydantic models
    - Define IdentifiedStudent and UnidentifiedFace Pydantic models
    - Implement POST /user/mark-attendance endpoint
    - Validate lecture exists and belongs to authenticated user
    - Call recognition_service.recognize_students() with images and lec_id
    - Return identified students and unidentified faces
    - Return 404 if lecture not found
    - Return 400 for validation errors
    - _Requirements: 9.1, 9.7, 15.2_

  - [x] 12.4 Implement face resolution endpoint
    - Define FaceResolution and ResolveFacesRequest Pydantic models
    - Implement POST /user/resolve-faces endpoint
    - For each resolution with action="existing": verify PRN exists, insert into Attendance_Record, call incremental_train()
    - For each resolution with action="new": insert into Student_Master, insert into Attendance_Record, call incremental_train()
    - For each resolution with action="discard": skip processing
    - Retrieve unidentified face images from temporary storage by face_id
    - Return count of resolved faces
    - Return 400 for invalid PRN or missing fields
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7_

  - [ ]* 12.5 Write property tests for face resolution
    - **Property 27: Face Resolution PRN Validation**
    - **Validates: Requirements 10.1**
    - **Property 28: Resolved Face Attendance Marking**
    - **Validates: Requirements 10.2**
    - **Property 29: New Student Dynamic Enrollment**
    - **Validates: Requirements 10.5**

- [x] 13. Implement CSV generation service
  - [x] 13.1 Create services/csv_service.py
    - Implement generate_attendance_csv() function
    - Accept lec_id as parameter
    - Query Lecture_Master for lecture details (lec_name, panel, lecture_datetime, user_id)
    - Query User_Master for teacher name by user_id
    - Query Student_Master for all students in the panel
    - Query Attendance_Record for students marked present in this lecture
    - Build CSV with columns: Student PRN, Student Name, Status, Lecture Name, Panel, DateTime, Teacher Name
    - Mark students in Attendance_Record as "Present", others as "Absent"
    - Create "Attendance Records/" directory if it doesn't exist
    - Generate filename: {panel}_{lec_name}_{datetime}.csv
    - Save CSV file and return file path
    - _Requirements: 11.2, 11.3, 11.4, 11.5, 11.6, 11.7_

  - [ ]* 13.2 Write property tests for CSV generation
    - **Property 31: CSV Generation on Finalization**
    - **Validates: Requirements 11.2, 11.5**
    - **Property 32: CSV Structure Completeness**
    - **Validates: Requirements 11.3**
    - **Property 33: CSV Student Roster Completeness**
    - **Validates: Requirements 11.4**
    - **Property 34: CSV Naming Convention**
    - **Validates: Requirements 11.6**
    - **Property 35: Directory Auto-Creation**
    - **Validates: Requirements 11.7**

  - [ ]* 13.3 Write unit tests for CSV service
    - Test CSV file creation
    - Test CSV column headers
    - Test present/absent status assignment
    - Test filename format
    - Test directory creation
    - _Requirements: 11.2, 11.3, 11.4, 11.5, 11.6, 11.7_

- [x] 14. Implement attendance finalization endpoint
  - [x] 14.1 Add finalization endpoint to user.py
    - Define FinalizeAttendanceRequest Pydantic model
    - Implement POST /user/finalize-attendance endpoint
    - Validate lecture exists and belongs to authenticated user
    - Update attendance_status to 'Y' in Lecture_Master
    - Call csv_service.generate_attendance_csv() with lec_id
    - Return success message with CSV file path
    - Return 404 if lecture not found
    - _Requirements: 11.1, 11.2_

  - [ ]* 14.2 Write property tests for attendance finalization
    - **Property 30: Attendance Finalization Status Update**
    - **Validates: Requirements 11.1**

- [x] 15. Checkpoint - Ensure user features and attendance workflow work
  - Ensure all tests pass, ask the user if questions arise.

- [x] 16. Implement main application and CORS
  - [x] 16.1 Create main.py with FastAPI app
    - Initialize FastAPI app instance
    - Configure CORS middleware for frontend integration
    - Include routers from auth, admin, user, superadmin modules
    - Add startup event to load FaceModel
    - Add health check endpoint GET /health
    - Configure uvicorn server settings
    - _Requirements: 13.4, 14.1, 14.2, 14.5_

  - [ ]* 16.2 Write integration tests for main app
    - Test CORS headers in responses
    - Test health check endpoint
    - Test router registration
    - Test model loading at startup
    - _Requirements: 13.4, 14.1_

- [x] 17. Implement privilege-based access control middleware
  - [x] 17.1 Add privilege validation decorator or dependency
    - Create require_privilege() dependency function
    - Accept minimum required privilege level as parameter
    - Extract user privilege from request (session, token, or header)
    - Return 403 if user privilege is insufficient
    - Apply to all protected endpoints
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 15.5_

  - [ ]* 17.2 Write property tests for access control
    - **Property 3: Privilege Level Domain Constraint**
    - **Validates: Requirements 2.1**
    - **Property 4: Privilege-Based Access Enforcement**
    - **Validates: Requirements 2.5, 15.5**

  - [ ]* 17.3 Write unit tests for access control
    - Test Super Admin can access all endpoints
    - Test Admin cannot access Super Admin endpoints
    - Test Teacher cannot access Admin endpoints
    - Test 403 response for unauthorized access
    - _Requirements: 2.2, 2.3, 2.4, 2.5_

- [x] 18. Implement comprehensive error handling
  - [x] 18.1 Add global exception handlers
    - Create exception handler for database errors (500)
    - Create exception handler for validation errors (400)
    - Create exception handler for not found errors (404)
    - Create exception handler for conflict errors (409)
    - Create exception handler for authorization errors (403)
    - Ensure all error responses follow consistent JSON format
    - Log errors with full details for debugging
    - _Requirements: 13.5, 15.1, 15.2, 15.3, 15.4, 15.5_

  - [ ]* 18.2 Write unit tests for error handling
    - Test database connection failure handling
    - Test validation error response format
    - Test 404 for non-existent resources
    - Test 409 for duplicate constraints
    - Test 500 for unexpected errors
    - _Requirements: 15.1, 15.2, 15.3, 15.4_

- [x] 19. Create database schema setup script
  - [x] 19.1 Create setup_database.sql
    - Write CREATE TABLE statements for Login_Master, User_Master, Student_Master, Lecture_Master, Request_Master, Attendance_Record
    - Add primary key, foreign key, and unique constraints
    - Add CHECK constraints for privilege_level and attendance_status
    - Add indexes for frequently queried columns (user_id, prn, lec_id)
    - Include comments documenting table purposes
    - _Requirements: All database-related requirements_

- [x] 20. Create README and documentation
  - [x] 20.1 Create README.md
    - Document system overview and features
    - List prerequisites (Python version, SQL Server, dependencies)
    - Provide installation instructions
    - Document environment variable configuration
    - Provide API endpoint documentation with examples
    - Document how to run the application (uvicorn command)
    - Document how to run tests (pytest command)
    - Include troubleshooting section
    - _Requirements: 14.5_

- [x] 21. Final checkpoint - End-to-end testing
  - Run complete user creation and authentication flow
  - Run student enrollment to attendance marking workflow
  - Run lecture scheduling to finalization workflow
  - Run privilege escalation request and approval workflow
  - Ensure all tests pass
  - Verify CSV generation works correctly
  - Verify model persistence across restarts
  - Ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at key milestones
- Property tests validate universal correctness properties with 100+ iterations
- Unit tests validate specific examples and edge cases
- The system uses Python with FastAPI, PyTorch, bcrypt, pyodbc, and hypothesis
- The pre-trained model file trained_face_brain.pth must exist before running the application
- Database connection parameters must be configured in .env file before running
