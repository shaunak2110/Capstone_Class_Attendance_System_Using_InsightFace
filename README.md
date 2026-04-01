# Role-Based Attendance System with Facial Recognition

An automated attendance tracking system for educational institutions that uses facial recognition technology and role-based access control. The system supports three privilege levels (Super Admin, Admin, Teacher) and automates attendance marking through AI-powered face detection and recognition.

## Features

- **Role-Based Access Control**: Three-tier privilege system (Super Admin, Admin, Teacher) with secure authentication
- **Facial Recognition**: PyTorch-based neural network for accurate student identification
- **Student Enrollment**: Automated enrollment with facial data collection and incremental model training
- **Lecture Management**: Schedule lectures and track attendance status
- **Automated Attendance**: Mark attendance from classroom images with face detection and recognition
- **Unidentified Face Resolution**: Manual resolution workflow for unrecognized faces
- **CSV Export**: Generate attendance records in CSV format with complete student rosters
- **RESTful API**: FastAPI-based backend with comprehensive error handling

## System Architecture

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

## Prerequisites

### Software Requirements

- **Python**: 3.8 or higher
- **SQL Server**: Microsoft SQL Server (any recent version)
- **ODBC Driver**: ODBC Driver 17 for SQL Server or higher

### Python Dependencies

All dependencies are listed in `backend/requirements.txt`:

- `torch` - PyTorch deep learning framework
- `torchvision` - Computer vision utilities
- `facenet-pytorch` - Pre-trained face detection and recognition models
- `numpy` - Numerical computing
- `Pillow` - Image processing
- `opencv-python` - Computer vision operations
- `fastapi` - Web framework for building APIs
- `uvicorn[standard]` - ASGI server
- `pyodbc` - SQL Server database connectivity
- `bcrypt` - Password hashing
- `hypothesis` - Property-based testing
- `python-dotenv` - Environment variable management
- `pytest` - Testing framework

## Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd role-based-attendance-system
```

### 2. Set Up Python Environment

Create and activate a virtual environment:

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 4. Set Up Database

Run the database setup script to create all required tables:

```bash
# Connect to SQL Server and run the script
sqlcmd -S your_server_name -d master -i ../setup_database.sql

# Or use SQL Server Management Studio (SSMS) to execute setup_database.sql
```

The script creates the following tables:
- `Login_Master` - User authentication and privilege levels
- `User_Master` - User profile information
- `Student_Master` - Student enrollment records
- `Lecture_Master` - Scheduled lectures
- `Request_Master` - Privilege escalation requests
- `Attendance_Record` - Attendance tracking

### 5. Configure Environment Variables

Create a `.env` file in the `backend` directory:

```bash
cp .env.example .env
```

Edit `.env` with your database credentials:

```env
# SQL Server connection settings
SERVER=your_server_name_or_ip
DATABASE=AttendanceDB
UID=your_username
PWD=your_password

# Optional: Driver specification (default: ODBC Driver 17 for SQL Server)
# DRIVER={ODBC Driver 17 for SQL Server}
```

### 6. Initialize Face Recognition Model

Ensure the pre-trained model file `trained_face_brain.pth` exists in the `backend` directory. If starting fresh, the model will be created during the first student enrollment.

## Running the Application

### Start the Backend Server

From the `backend` directory:

```bash
# Development mode with auto-reload
uvicorn main:app --reload

# Or using Python directly
python main.py

# Production mode (specify host and port)
uvicorn main:app --host 0.0.0.0 --port 8000
```

The API will be available at:
- **API Base URL**: http://localhost:8000
- **Interactive API Docs**: http://localhost:8000/docs
- **Alternative API Docs**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

### Verify Installation

Check the health endpoint:

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "message": "Role-Based Attendance System is running",
  "face_model_status": "loaded",
  "enrolled_students": 0
}
```

## API Documentation

### Authentication

#### Login
```http
POST /auth/login
Content-Type: application/json

{
  "username": "admin",
  "password": "password123"
}
```

**Response:**
```json
{
  "user_id": 1,
  "username": "admin",
  "privilege_level": 1
}
```

### Super Admin Endpoints

#### Get Privilege Escalation Requests
```http
GET /superadmin/requests
```

#### Approve Privilege Escalation
```http
POST /superadmin/approve-request
Content-Type: application/json

{
  "request_id": 1,
  "user_id": 5
}
```

#### Create Admin Account
```http
POST /superadmin/create-admin
Content-Type: application/json

{
  "username": "newadmin",
  "password": "securepass",
  "name": "John Doe",
  "email_id": "john@example.com",
  "school": "Engineering",
  "department": "Computer Science"
}
```

### Admin Endpoints

#### Create Teacher Account
```http
POST /admin/create-teacher
Content-Type: application/json

{
  "username": "teacher1",
  "password": "teacherpass",
  "name": "Jane Smith",
  "email_id": "jane@example.com",
  "school": "Engineering",
  "department": "Computer Science",
  "mob": "1234567890"
}
```

#### Enroll Student
```http
POST /admin/enroll-student
Content-Type: application/json

{
  "prn": "PRN001",
  "name": "Student Name",
  "panel": "H",
  "images": ["base64_encoded_image_1", "base64_encoded_image_2", ...]
}
```
**Note:** Exactly 25 images are required for enrollment.

#### Schedule Lecture
```http
POST /admin/schedule-lecture
Content-Type: application/json

{
  "user_id": 3,
  "school": "Engineering",
  "department": "Computer Science",
  "lecorlab": "Lecture",
  "panel": "H",
  "lec_name": "Data Structures",
  "course_code": "CS201",
  "lecture_datetime": "2024-01-15T10:00:00"
}
```

### Teacher/User Endpoints

#### Get Scheduled Lectures
```http
GET /user/lectures/{user_id}
```

**Response:**
```json
[
  {
    "lec_id": 1,
    "lec_name": "Data Structures",
    "panel": "H",
    "lecture_datetime": "2024-01-15T10:00:00",
    "attendance_status": "N"
  }
]
```

#### Mark Attendance
```http
POST /user/mark-attendance
Content-Type: application/json

{
  "lec_id": 1,
  "images": ["base64_encoded_image_1", "base64_encoded_image_2"]
}
```

**Response:**
```json
{
  "identified_students": [
    {
      "prn": "PRN001",
      "name": "Student Name",
      "similarity": 0.85
    }
  ],
  "unidentified_faces": [
    {
      "face_id": "uuid-1234",
      "image": "base64_encoded_cropped_face"
    }
  ]
}
```

#### Resolve Unidentified Faces
```http
POST /user/resolve-faces
Content-Type: application/json

{
  "lec_id": 1,
  "resolutions": [
    {
      "face_id": "uuid-1234",
      "action": "existing",
      "prn": "PRN002"
    },
    {
      "face_id": "uuid-5678",
      "action": "new",
      "prn": "PRN003",
      "name": "New Student",
      "panel": "H"
    },
    {
      "face_id": "uuid-9012",
      "action": "discard"
    }
  ]
}
```

**Actions:**
- `existing` - Link face to existing student by PRN
- `new` - Enroll new student with this face
- `discard` - Ignore this face (not a student)

#### Finalize Attendance
```http
POST /user/finalize-attendance
Content-Type: application/json

{
  "lec_id": 1
}
```

**Response:**
```json
{
  "message": "Attendance finalized",
  "csv_path": "Attendance Records/H_Data_Structures_2024-01-15_10-00-00.csv"
}
```

## Running Tests

The project includes comprehensive unit tests and property-based tests.

### Run All Tests

```bash
cd backend
pytest
```

### Run Specific Test Files

```bash
# Test authentication
pytest test_auth.py

# Test admin functionality
pytest test_admin.py

# Test user/teacher functionality
pytest test_user.py

# Test face recognition
pytest test_face_model.py test_inference.py

# Test services
pytest test_recognition_service.py test_training_service.py test_csv_service.py
```

### Run Tests with Verbose Output

```bash
pytest -v
```

### Run Tests with Coverage

```bash
pytest --cov=. --cov-report=html
```

## Project Structure

```
role-based-attendance-system/
├── backend/
│   ├── model/
│   │   ├── face_model.py          # Neural network model
│   │   └── inference.py           # Face detection and recognition
│   ├── services/
│   │   ├── recognition_service.py # Attendance marking workflow
│   │   ├── training_service.py    # Incremental model training
│   │   └── csv_service.py         # CSV generation
│   ├── main.py                    # FastAPI application entry point
│   ├── database.py                # Database connection management
│   ├── auth.py                    # Authentication endpoints
│   ├── admin.py                   # Admin endpoints
│   ├── user.py                    # Teacher/user endpoints
│   ├── superadmin.py              # Super admin endpoints
│   ├── dependencies.py            # Shared dependencies and utilities
│   ├── requirements.txt           # Python dependencies
│   ├── .env.example               # Environment variables template
│   ├── trained_face_brain.pth     # Pre-trained face recognition model
│   └── test_*.py                  # Test files
├── frontend/                      # Frontend application (if applicable)
├── Attendance Records/            # Generated CSV files
├── setup_database.sql             # Database schema setup script
└── README.md                      # This file
```

## Troubleshooting

### Database Connection Issues

**Problem:** `pyodbc.Error: ('08001', '[08001] [Microsoft][ODBC Driver 17 for SQL Server]...')`

**Solutions:**
1. Verify SQL Server is running
2. Check firewall settings allow connections on port 1433
3. Verify credentials in `.env` file
4. Ensure ODBC Driver 17 is installed:
   ```bash
   # Windows: Download from Microsoft website
   # Linux: sudo apt-get install msodbcsql17
   ```
5. Test connection with `sqlcmd`:
   ```bash
   sqlcmd -S your_server -U your_username -P your_password
   ```

### Face Model Loading Issues

**Problem:** `Warning: Failed to load face model`

**Solutions:**
1. Ensure `trained_face_brain.pth` exists in the `backend` directory
2. Check file permissions
3. Verify PyTorch installation:
   ```bash
   python -c "import torch; print(torch.__version__)"
   ```
4. If starting fresh, the model will be created during first student enrollment

### Import Errors

**Problem:** `ModuleNotFoundError: No module named 'fastapi'`

**Solutions:**
1. Activate virtual environment:
   ```bash
   # Windows: venv\Scripts\activate
   # Linux/Mac: source venv/bin/activate
   ```
2. Reinstall dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Port Already in Use

**Problem:** `ERROR: [Errno 48] Address already in use`

**Solutions:**
1. Change port in command:
   ```bash
   uvicorn main:app --port 8001
   ```
2. Kill process using port 8000:
   ```bash
   # Windows: netstat -ano | findstr :8000
   # Linux/Mac: lsof -ti:8000 | xargs kill
   ```

### Image Encoding Issues

**Problem:** `Invalid base64 image data`

**Solutions:**
1. Ensure images are properly base64 encoded
2. Remove data URI prefix if present:
   ```python
   # Remove "data:image/jpeg;base64," prefix
   base64_string = base64_string.split(',')[1]
   ```
3. Verify image format (JPEG, PNG supported)

### Attendance CSV Not Generated

**Problem:** CSV file not created after finalization

**Solutions:**
1. Check write permissions on `Attendance Records/` directory
2. Verify lecture exists and belongs to the user
3. Check logs for specific error messages
4. Ensure at least one student is enrolled in the panel

### Test Failures

**Problem:** Tests fail with database errors

**Solutions:**
1. Ensure test database is set up
2. Check `.env` configuration
3. Run tests with verbose output:
   ```bash
   pytest -v -s
   ```
4. Clear test data between runs if needed

## Security Considerations

- **Password Hashing**: All passwords are hashed using bcrypt before storage
- **Environment Variables**: Database credentials stored in `.env` (never commit this file)
- **CORS Configuration**: Update `allow_origins` in `main.py` for production
- **SQL Injection**: All queries use parameterized statements via pyodbc
- **Privilege Validation**: All protected endpoints verify user privilege level

## Performance Optimization

- **Database Indexes**: All frequently queried columns have indexes
- **Model Caching**: Face model loaded once at startup
- **Batch Processing**: Multiple images processed in single request
- **Connection Pooling**: Database connections managed efficiently

## Contributing

1. Follow PEP 8 style guidelines for Python code
2. Write tests for new features
3. Update API documentation for endpoint changes
4. Ensure all tests pass before submitting changes

## License

[Specify your license here]

## Support

For issues and questions:
- Check the troubleshooting section above
- Review API documentation at http://localhost:8000/docs
- Check application logs for detailed error messages

## Acknowledgments

- FastAPI framework for the excellent web framework
- PyTorch and facenet-pytorch for face recognition capabilities
- The open-source community for various dependencies
