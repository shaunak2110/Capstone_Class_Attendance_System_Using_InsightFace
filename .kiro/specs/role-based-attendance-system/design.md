# Design Document: Role-Based Attendance System with Facial Recognition

## Overview

The Role-Based Attendance System is a FastAPI-based backend application that automates attendance tracking in educational institutions using facial recognition technology. The system implements a three-tier privilege hierarchy (Super Admin, Admin, Teacher) and integrates a pre-trained facial recognition model for student identification.

### Core Capabilities

- **Authentication & Authorization**: Secure login with bcrypt password hashing and privilege-based access control
- **User Management**: Multi-level user creation and privilege escalation workflows
- **Student Enrollment**: Facial data collection with incremental model training
- **Lecture Management**: Scheduling and tracking of academic sessions
- **Automated Attendance**: Face detection, recognition, and attendance marking from classroom images
- **Record Generation**: CSV export of finalized attendance records

### Technology Stack

- **Framework**: FastAPI (Python)
- **Database**: SQL Server via pyodbc
- **Face Recognition**: PyTorch-based neural network (trained_face_brain.pth)
- **Security**: bcrypt for password hashing
- **Configuration**: Environment variables for database credentials

## Architecture

### System Architecture

The system follows a layered architecture pattern with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI Application                      │
│                         (main.py)                            │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
┌───────▼────────┐   ┌────────▼────────┐   ┌──────▼──────┐
│  Auth Module   │   │  Admin Module   │   │ User Module │
│   (auth.py)    │   │   (admin.py)    │   │  (user.py)  │
└───────┬────────┘   └────────┬────────┘   └──────┬──────┘
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              │
                    ┌─────────▼──────────┐
                    │ SuperAdmin Module  │
                    │  (superadmin.py)   │
                    └─────────┬──────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
┌───────▼────────┐   ┌────────▼────────┐   ┌──────▼──────────┐
│   Database     │   │    Services     │   │  Face Model     │
│  (database.py) │   │  - recognition  │   │ - face_model.py │
└────────────────┘   │  - training     │   │ - inference.py  │
                     │  - csv          │   └─────────────────┘
                     └─────────────────┘
```

### Module Responsibilities

**main.py**
- Application entry point and FastAPI app initialization
- CORS middleware configuration
- Route registration from all modules
- Server startup configuration

**database.py**
- Database connection management using pyodbc
- Environment variable loading for connection parameters
- Connection pooling and error handling
- SQL query execution utilities

**auth.py**
- User authentication endpoint
- Credential validation against Login_Master
- Password verification using bcrypt
- Session token generation (if implemented)

**admin.py**
- Teacher account creation endpoints
- Student enrollment with facial data
- Lecture scheduling for teachers
- Student and teacher management operations

**user.py**
- Teacher's scheduled lecture retrieval
- Attendance marking workflow
- Unidentified face resolution
- Attendance finalization

**superadmin.py**
- Privilege escalation request retrieval
- Request approval/rejection
- Admin account creation
- System-wide user management

**model/face_model.py**
- Neural network architecture definition
- Model loading from trained_face_brain.pth
- Embedding generation (128-dimensional vectors)
- PRN-to-embedding mapping storage

**model/inference.py**
- Face detection in images
- Embedding extraction from detected faces
- Cosine similarity computation
- Student identification by matching embeddings

**services/recognition_service.py**
- Orchestrates face detection and recognition workflow
- Manages batch processing of multiple images
- Handles unidentified face extraction
- Coordinates with inference module

**services/training_service.py**
- Incremental model training implementation
- New student data integration
- Model weight updates
- Persistence to trained_face_brain.pth

**services/csv_service.py**
- Attendance record CSV generation
- Student roster retrieval by panel
- Present/absent status compilation
- File naming and directory management

## Components and Interfaces

### API Endpoints

#### Authentication Endpoints

**POST /auth/login**
- Request: `{ "username": string, "password": string }`
- Response: `{ "user_id": int, "username": string, "privilege_level": int }`
- Status Codes: 200 (success), 401 (invalid credentials), 500 (server error)

#### Super Admin Endpoints

**GET /superadmin/requests**
- Headers: `Authorization: Bearer <token>` (or privilege validation)
- Response: `[{ "request_id": int, "user_id": int, "username": string, "requested_at": datetime }]`
- Status Codes: 200 (success), 403 (forbidden), 500 (server error)

**POST /superadmin/approve-request**
- Request: `{ "request_id": int, "user_id": int }`
- Response: `{ "message": "Privilege escalation approved" }`
- Status Codes: 200 (success), 403 (forbidden), 404 (not found), 500 (server error)

**POST /superadmin/create-admin**
- Request: `{ "username": string, "password": string, "name": string, "email_id": string, "school": string, "department": string }`
- Response: `{ "user_id": int, "message": "Admin created successfully" }`
- Status Codes: 201 (created), 400 (validation error), 403 (forbidden), 409 (duplicate username), 500 (server error)

#### Admin Endpoints

**POST /admin/create-teacher**
- Request: `{ "username": string, "password": string, "name": string, "email_id": string, "school": string, "department": string, "mob": string }`
- Response: `{ "user_id": int, "message": "Teacher created successfully" }`
- Status Codes: 201 (created), 400 (validation error), 403 (forbidden), 409 (duplicate username), 500 (server error)

**POST /admin/enroll-student**
- Request: `{ "prn": string, "name": string, "panel": string, "images": [base64_encoded_images] }` (25 images required)
- Response: `{ "message": "Student enrolled successfully", "prn": string }`
- Status Codes: 201 (created), 400 (validation error), 403 (forbidden), 409 (duplicate PRN), 500 (server error)

**POST /admin/schedule-lecture**
- Request: `{ "user_id": int, "school": string, "department": string, "lecorlab": string, "panel": string, "lec_name": string, "course_code": string, "lecture_datetime": datetime }`
- Response: `{ "lec_id": int, "message": "Lecture scheduled successfully" }`
- Status Codes: 201 (created), 400 (validation error), 403 (forbidden), 500 (server error)

#### Teacher/User Endpoints

**GET /user/lectures/{user_id}**
- Response: `[{ "lec_id": int, "lec_name": string, "panel": string, "lecture_datetime": datetime, "attendance_status": string }]`
- Status Codes: 200 (success), 403 (forbidden), 404 (not found), 500 (server error)

**POST /user/mark-attendance**
- Request: `{ "lec_id": int, "images": [base64_encoded_images] }`
- Response: `{ "identified_students": [{ "prn": string, "name": string, "similarity": float }], "unidentified_faces": [{ "face_id": string, "image": base64 }] }`
- Status Codes: 200 (success), 400 (validation error), 403 (forbidden), 404 (lecture not found), 500 (server error)

**POST /user/resolve-faces**
- Request: `{ "lec_id": int, "resolutions": [{ "face_id": string, "action": "existing|new|discard", "prn": string?, "name": string?, "panel": string? }] }`
- Response: `{ "message": "Faces resolved successfully", "updated_count": int }`
- Status Codes: 200 (success), 400 (validation error), 403 (forbidden), 500 (server error)

**POST /user/finalize-attendance**
- Request: `{ "lec_id": int }`
- Response: `{ "message": "Attendance finalized", "csv_path": string }`
- Status Codes: 200 (success), 403 (forbidden), 404 (not found), 500 (server error)

### Database Schema

#### Login_Master
```sql
CREATE TABLE Login_Master (
    user_id INT PRIMARY KEY IDENTITY(1,1),
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    privilege_level INT NOT NULL CHECK (privilege_level IN (1, 2, 3))
)
```

#### User_Master
```sql
CREATE TABLE User_Master (
    user_id INT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email_id VARCHAR(100) NOT NULL,
    school VARCHAR(100) NOT NULL,
    department VARCHAR(100) NOT NULL,
    mob VARCHAR(15),
    FOREIGN KEY (user_id) REFERENCES Login_Master(user_id)
)
```

#### Student_Master
```sql
CREATE TABLE Student_Master (
    prn VARCHAR(20) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    panel VARCHAR(10) NOT NULL
)
```

#### Lecture_Master
```sql
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
    attendance_status CHAR(1) DEFAULT 'N' CHECK (attendance_status IN ('Y', 'N')),
    FOREIGN KEY (user_id) REFERENCES Login_Master(user_id)
)
```

#### Request_Master
```sql
CREATE TABLE Request_Master (
    request_id INT PRIMARY KEY IDENTITY(1,1),
    user_id INT NOT NULL,
    requested_at DATETIME DEFAULT GETDATE(),
    FOREIGN KEY (user_id) REFERENCES Login_Master(user_id)
)
```

#### Attendance_Record (for tracking marked attendance)
```sql
CREATE TABLE Attendance_Record (
    attendance_id INT PRIMARY KEY IDENTITY(1,1),
    lec_id INT NOT NULL,
    prn VARCHAR(20) NOT NULL,
    status VARCHAR(10) NOT NULL CHECK (status IN ('Present', 'Absent')),
    marked_at DATETIME DEFAULT GETDATE(),
    FOREIGN KEY (lec_id) REFERENCES Lecture_Master(lec_id),
    FOREIGN KEY (prn) REFERENCES Student_Master(prn)
)
```

### Face Recognition Model Interface

#### FaceModel Class
```python
class FaceModel:
    def __init__(self, model_path: str = "trained_face_brain.pth"):
        """Load pre-trained model and PRN-embedding mappings"""
        
    def generate_embedding(self, face_image: np.ndarray) -> np.ndarray:
        """Generate 128-dimensional embedding from face image"""
        
    def add_student(self, prn: str, embeddings: List[np.ndarray]):
        """Add new student embeddings to the model"""
        
    def identify_face(self, embedding: np.ndarray, threshold: float = 0.6) -> Optional[Tuple[str, float]]:
        """Identify student by comparing embedding using cosine similarity
        Returns: (prn, similarity_score) or None if no match above threshold"""
        
    def save_model(self):
        """Save updated model weights to trained_face_brain.pth"""
```

#### InferenceEngine Class
```python
class InferenceEngine:
    def __init__(self, face_model: FaceModel):
        """Initialize with face model instance"""
        
    def detect_faces(self, image: np.ndarray) -> List[np.ndarray]:
        """Detect all faces in image, return cropped face images"""
        
    def process_image(self, image: np.ndarray) -> List[Dict]:
        """Detect faces and generate embeddings
        Returns: [{"face_image": np.ndarray, "embedding": np.ndarray}]"""
        
    def identify_students(self, embeddings: List[np.ndarray]) -> Tuple[List[Dict], List[np.ndarray]]:
        """Identify students from embeddings
        Returns: (identified_students, unidentified_faces)"""
```

## Data Models

### Request/Response Models (Pydantic)

```python
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    user_id: int
    username: str
    privilege_level: int

class CreateUserRequest(BaseModel):
    username: str
    password: str
    name: str
    email_id: EmailStr
    school: str
    department: str
    mob: Optional[str] = None

class EnrollStudentRequest(BaseModel):
    prn: str
    name: str
    panel: str
    images: List[str]  # Base64 encoded images

class ScheduleLectureRequest(BaseModel):
    user_id: int
    school: str
    department: str
    lecorlab: str
    panel: str
    lec_name: str
    course_code: str
    lecture_datetime: datetime

class LectureResponse(BaseModel):
    lec_id: int
    lec_name: str
    panel: str
    lecture_datetime: datetime
    attendance_status: str

class MarkAttendanceRequest(BaseModel):
    lec_id: int
    images: List[str]  # Base64 encoded images

class IdentifiedStudent(BaseModel):
    prn: str
    name: str
    similarity: float

class UnidentifiedFace(BaseModel):
    face_id: str
    image: str  # Base64 encoded

class MarkAttendanceResponse(BaseModel):
    identified_students: List[IdentifiedStudent]
    unidentified_faces: List[UnidentifiedFace]

class FaceResolution(BaseModel):
    face_id: str
    action: str  # "existing", "new", or "discard"
    prn: Optional[str] = None
    name: Optional[str] = None
    panel: Optional[str] = None

class ResolveFacesRequest(BaseModel):
    lec_id: int
    resolutions: List[FaceResolution]

class FinalizeAttendanceRequest(BaseModel):
    lec_id: int
```

### Internal Data Structures

**PRN-Embedding Mapping**
```python
# Stored within the model or as a separate pickle file
prn_embeddings: Dict[str, List[np.ndarray]] = {
    "PRN001": [embedding1, embedding2, ...],  # Multiple embeddings per student
    "PRN002": [embedding1, embedding2, ...],
}
```

**Temporary Face Storage**
```python
# In-memory storage during attendance marking session
unidentified_faces: Dict[str, np.ndarray] = {
    "face_uuid_1": cropped_face_image,
    "face_uuid_2": cropped_face_image,
}
```


## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property Reflection

After analyzing all acceptance criteria, I identified several areas of redundancy:

- **User Creation Properties (4.x and 5.x)**: Admin and teacher creation share identical patterns for dual-table insertion, user_id consistency, username uniqueness, and field validation. These can be generalized into properties about user creation regardless of privilege level.
- **Privilege Update Properties (3.2 and 3.3)**: Updating privilege in both Login_Master and User_Master can be combined into a single property about maintaining consistency across both tables.
- **Model Persistence Properties (6.5, 10.7, 12.2)**: Multiple criteria mention saving model weights after various operations. These can be unified into a property about model persistence after any training operation.
- **CSV Structure Properties (11.3, 11.4, 11.5, 11.6)**: Multiple properties about CSV generation can be combined into comprehensive properties about CSV completeness and format.

### Property 1: Valid Authentication Returns Complete User Data

*For any* valid username and password combination in Login_Master, authentication should return the user_id, username, and privilege_level matching the database record.

**Validates: Requirements 1.1**

### Property 2: Invalid Authentication Fails Appropriately

*For any* credentials that do not match a record in Login_Master (either non-existent username or incorrect password), authentication should fail and return an error.

**Validates: Requirements 1.2**

### Property 3: Privilege Level Domain Constraint

*For any* user record in Login_Master or User_Master, the privilege_level value must be exactly 1, 2, or 3.

**Validates: Requirements 2.1**

### Property 4: Privilege-Based Access Enforcement

*For any* user and any endpoint requiring higher privileges than the user possesses, the system should deny access with HTTP status 403.

**Validates: Requirements 2.5, 15.5**

### Property 5: Pending Requests Retrieval Completeness

*For any* set of records in Request_Master, the super admin endpoint should return all pending requests without omission.

**Validates: Requirements 3.1**

### Property 6: Privilege Escalation Consistency

*For any* approved privilege escalation request, the user's privilege_level should be updated from 3 to 2 in both Login_Master and User_Master with matching values.

**Validates: Requirements 3.2, 3.3, 3.4**

### Property 7: Request Cleanup After Approval

*For any* privilege escalation request that is approved, the corresponding record should be removed from Request_Master.

**Validates: Requirements 3.5**

### Property 8: Dual-Table User Creation

*For any* new user creation (admin or teacher), records should be inserted into both Login_Master and User_Master with identical user_id values.

**Validates: Requirements 4.1, 4.2, 4.3, 5.1, 5.2, 5.3**

### Property 9: Username Uniqueness Enforcement

*For any* attempt to create a user with a username that already exists in Login_Master, the operation should fail with a duplicate error.

**Validates: Requirements 4.4, 5.4**

### Property 10: Required Field Validation

*For any* user creation request missing mandatory fields (name, email_id, school, department, and mob for teachers), the operation should fail with a validation error listing the missing fields.

**Validates: Requirements 4.5, 5.5, 15.2**

### Property 11: Student Enrollment Image Count Validation

*For any* student enrollment request, the system should accept exactly 25 face images—rejecting requests with fewer or more images.

**Validates: Requirements 6.1**

### Property 12: Student Record Creation

*For any* valid student enrollment with 25 images, a record should be inserted into Student_Master containing the PRN, name, and panel.

**Validates: Requirements 6.2**

### Property 13: Model Persistence After Training

*For any* operation that performs incremental training (student enrollment, face resolution), the trained_face_brain.pth file should be updated with new weights.

**Validates: Requirements 6.5, 10.7, 12.2**

### Property 14: PRN Uniqueness Enforcement

*For any* attempt to enroll a student with a PRN that already exists in Student_Master, the operation should fail with a duplicate error.

**Validates: Requirements 6.6, 15.4**

### Property 15: Student-Panel Association

*For any* enrolled student in Student_Master, the record should contain exactly one non-null panel identifier.

**Validates: Requirements 6.7**

### Property 16: Lecture Record Creation

*For any* valid lecture scheduling request with all required fields, a record should be inserted into Lecture_Master with a unique lec_id.

**Validates: Requirements 7.1, 7.5**

### Property 17: Default Attendance Status

*For any* newly scheduled lecture, the attendance_status field should be initialized to 'N'.

**Validates: Requirements 7.2**

### Property 18: Lecture Field Validation

*For any* lecture scheduling request missing any required field (user_id, school, department, lecorlab, panel, lec_name, course_code, lecture_datetime), the operation should fail with a validation error.

**Validates: Requirements 7.3**

### Property 19: Lecture Ownership

*For any* scheduled lecture, the user_id in Lecture_Master should match the authenticated teacher who created it.

**Validates: Requirements 7.4**

### Property 20: Teacher Lecture Isolation

*For any* teacher requesting their scheduled lectures, only lectures with matching user_id should be returned.

**Validates: Requirements 8.1**

### Property 21: Lecture Response Completeness

*For any* lecture returned by the retrieval endpoint, the response should include lec_id, lec_name, panel, lecture_datetime, and attendance_status.

**Validates: Requirements 8.2**

### Property 22: Lecture Chronological Ordering

*For any* set of lectures returned to a teacher, they should be ordered by lecture_datetime in descending order (most recent first).

**Validates: Requirements 8.3**

### Property 23: Face Detection Completeness

*For any* image containing N faces, the face detection engine should detect all N faces without omission.

**Validates: Requirements 9.2**

### Property 24: Known Student Recognition

*For any* enrolled student's face image with sufficient quality, the face recognition engine should identify the student by their PRN when similarity exceeds the threshold.

**Validates: Requirements 9.5**

### Property 25: Unknown Face Handling

*For any* face that does not match any enrolled student above the similarity threshold, the system should return it as an unidentified face with the cropped image.

**Validates: Requirements 9.6**

### Property 26: Attendance Response Structure

*For any* attendance marking operation, the response should contain both a list of identified students (with PRN, name, similarity) and a list of unidentified faces (with face_id and image).

**Validates: Requirements 9.7**

### Property 27: Face Resolution PRN Validation

*For any* face resolution indicating an existing student, the system should verify the PRN exists in Student_Master before marking attendance.

**Validates: Requirements 10.1**

### Property 28: Resolved Face Attendance Marking

*For any* unidentified face resolved to an existing student, that student should be marked present for the lecture.

**Validates: Requirements 10.2**

### Property 29: New Student Dynamic Enrollment

*For any* unidentified face resolved as a new student with valid PRN, name, and panel, a record should be inserted into Student_Master.

**Validates: Requirements 10.5**

### Property 30: Attendance Finalization Status Update

*For any* lecture with attendance_status 'N', finalizing attendance should update the status to 'Y' in Lecture_Master.

**Validates: Requirements 11.1**

### Property 31: CSV Generation on Finalization

*For any* finalized lecture, a CSV file should be generated in the "Attendance Records/" directory.

**Validates: Requirements 11.2, 11.5**

### Property 32: CSV Structure Completeness

*For any* generated attendance CSV, it should contain columns for Student PRN, Student Name, Status, Lecture Name, Panel, DateTime, and Teacher Name.

**Validates: Requirements 11.3**

### Property 33: CSV Student Roster Completeness

*For any* finalized lecture, the CSV should list all students enrolled in the lecture's panel with status either "Present" or "Absent".

**Validates: Requirements 11.4**

### Property 34: CSV Naming Convention

*For any* generated CSV file, the filename should follow the format {panel}_{lec_name}_{datetime}.csv.

**Validates: Requirements 11.6**

### Property 35: Directory Auto-Creation

*For any* CSV generation when the "Attendance Records/" directory does not exist, the system should create the directory before saving the file.

**Validates: Requirements 11.7**

### Property 36: Model Embedding Preservation

*For any* existing student in the system, adding new students through enrollment should preserve the existing student's embeddings in the model.

**Validates: Requirements 12.4**

### Property 37: Password Hashing

*For any* user account in Login_Master, the password field should contain a bcrypt hash, not plaintext.

**Validates: Requirements 13.1**

### Property 38: Error Response Structure

*For any* error condition (database failure, validation error, face detection failure), the response should include a descriptive error message and an appropriate HTTP status code.

**Validates: Requirements 13.5, 15.1, 15.3**

## Error Handling

### Error Categories and Responses

**Authentication Errors (401)**
- Invalid credentials
- Missing authentication token
- Expired session

**Authorization Errors (403)**
- Insufficient privileges for requested operation
- Attempting to access another user's resources

**Validation Errors (400)**
- Missing required fields
- Invalid field formats (e.g., invalid email)
- Image count mismatch (not 25 images for enrollment)
- Invalid privilege level values

**Conflict Errors (409)**
- Duplicate username during user creation
- Duplicate PRN during student enrollment

**Not Found Errors (404)**
- Lecture ID does not exist
- User ID does not exist
- PRN does not exist during face resolution

**Processing Errors (422)**
- No faces detected in provided images
- Face detection failure due to image quality
- Model inference errors

**Server Errors (500)**
- Database connection failures
- Model loading failures
- File system errors during CSV generation
- Unexpected exceptions

### Error Response Format

All errors should follow a consistent JSON structure:

```json
{
    "error": "Error category",
    "message": "Detailed description of what went wrong",
    "details": {
        "field": "Additional context (optional)"
    }
}
```

### Error Handling Strategies

**Database Errors**
- Wrap all database operations in try-except blocks
- Log full error details for debugging
- Return sanitized error messages to clients
- Implement connection retry logic for transient failures

**Face Recognition Errors**
- Validate image format and size before processing
- Handle cases where no faces are detected gracefully
- Provide fallback for low-quality images
- Return unidentified faces for manual resolution

**File System Errors**
- Check directory existence before file operations
- Create directories automatically when needed
- Handle disk space issues gracefully
- Implement file locking for concurrent access

**Validation Errors**
- Use Pydantic models for automatic request validation
- Provide clear field-level error messages
- List all validation errors, not just the first one
- Include examples of valid formats in error messages

## Testing Strategy

### Dual Testing Approach

The system requires both unit testing and property-based testing for comprehensive coverage:

**Unit Tests** focus on:
- Specific examples demonstrating correct behavior
- Edge cases (empty inputs, boundary values)
- Error conditions and exception handling
- Integration points between components
- Database transaction rollback scenarios

**Property-Based Tests** focus on:
- Universal properties that hold for all inputs
- Comprehensive input coverage through randomization
- Invariant preservation across operations
- Round-trip properties (e.g., serialize/deserialize)

### Property-Based Testing Configuration

**Framework Selection**: Use `hypothesis` for Python property-based testing

**Test Configuration**:
- Minimum 100 iterations per property test (due to randomization)
- Each property test must reference its design document property
- Tag format: `# Feature: role-based-attendance-system, Property {number}: {property_text}`

**Example Property Test Structure**:

```python
from hypothesis import given, strategies as st
import hypothesis

@hypothesis.settings(max_examples=100)
@given(
    username=st.text(min_size=1, max_size=50),
    password=st.text(min_size=8, max_size=100)
)
def test_property_1_valid_authentication_returns_complete_data(username, password):
    """
    Feature: role-based-attendance-system
    Property 1: Valid Authentication Returns Complete User Data
    
    For any valid username and password combination in Login_Master,
    authentication should return the user_id, username, and privilege_level
    matching the database record.
    """
    # Setup: Create user in database
    user_id = create_test_user(username, password, privilege_level=2)
    
    # Execute: Authenticate
    response = client.post("/auth/login", json={
        "username": username,
        "password": password
    })
    
    # Verify: Response contains complete data
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == user_id
    assert data["username"] == username
    assert data["privilege_level"] == 2
    
    # Cleanup
    delete_test_user(user_id)
```

### Unit Testing Strategy

**Authentication Module Tests**:
- Test successful login with valid credentials
- Test failed login with invalid password
- Test failed login with non-existent username
- Test password hashing on user creation

**Authorization Tests**:
- Test Super Admin can access all endpoints
- Test Admin cannot access Super Admin endpoints
- Test Teacher cannot access Admin endpoints
- Test 403 response for unauthorized access

**User Management Tests**:
- Test admin creation by Super Admin
- Test teacher creation by Admin
- Test duplicate username rejection
- Test missing required fields validation

**Student Enrollment Tests**:
- Test successful enrollment with 25 images
- Test rejection with fewer than 25 images
- Test rejection with more than 25 images
- Test duplicate PRN rejection
- Test model file update after enrollment

**Lecture Management Tests**:
- Test lecture scheduling with all required fields
- Test default attendance_status is 'N'
- Test lecture retrieval filtered by user_id
- Test lecture ordering by datetime descending

**Face Recognition Tests**:
- Test face detection with single face image
- Test face detection with multiple faces
- Test recognition of enrolled student
- Test unidentified face handling
- Test similarity threshold behavior

**Attendance Workflow Tests**:
- Test attendance marking with identified students
- Test face resolution to existing student
- Test face resolution to new student
- Test face discard action
- Test attendance finalization status update

**CSV Generation Tests**:
- Test CSV file creation in correct directory
- Test CSV filename format
- Test CSV contains all panel students
- Test CSV column headers
- Test directory auto-creation

**Error Handling Tests**:
- Test database connection failure handling
- Test validation error response format
- Test 404 for non-existent resources
- Test 409 for duplicate constraints
- Test 500 for unexpected errors

### Integration Testing

**End-to-End Workflows**:
1. Complete user creation and authentication flow
2. Student enrollment to attendance marking workflow
3. Lecture scheduling to finalization workflow
4. Privilege escalation request and approval workflow

**Database Integration**:
- Test transaction rollback on errors
- Test referential integrity constraints
- Test concurrent access scenarios
- Test connection pool behavior

**Model Integration**:
- Test model loading at startup
- Test incremental training with new data
- Test embedding persistence across restarts
- Test recognition accuracy with real face images

### Test Data Management

**Test Database**:
- Use separate test database instance
- Reset database state before each test
- Use database transactions for test isolation
- Seed with minimal required data

**Test Images**:
- Maintain a set of test face images
- Include various lighting conditions
- Include multiple angles and expressions
- Include edge cases (no face, multiple faces)

**Mock Data Generators**:
- Generate random but valid usernames
- Generate random PRNs following institutional format
- Generate random lecture schedules
- Generate random panel identifiers

### Continuous Integration

**CI Pipeline Steps**:
1. Run linting and code formatting checks
2. Run unit tests with coverage reporting
3. Run property-based tests (100 iterations minimum)
4. Run integration tests against test database
5. Generate test coverage report (target: >80%)
6. Run security vulnerability scanning

**Test Execution Time**:
- Unit tests: < 2 minutes
- Property tests: < 5 minutes
- Integration tests: < 3 minutes
- Total CI pipeline: < 15 minutes

