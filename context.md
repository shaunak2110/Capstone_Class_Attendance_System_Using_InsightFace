# Role-Based Attendance System with Facial Recognition: Context and Workflow

This document provides a comprehensive understanding of the project's architecture, roles, and the data flow (Input -> Process -> Output) across various operations.

## Project Overview
The project is an automated attendance tracking system primarily built for educational institutions. It leverages a custom-trained neural network for facial recognition, wrapped in a FastAPI backend with a React frontend, and uses SQL Server for database operations. The system restricts operations based on privilege levels (Superadmin, Admin, Teacher).

## Tech Stack
- **Frontend**: React (Vite), Tailwind CSS
- **Backend**: FastAPI (Python 3.11)
- **Database**: SQL Server (via pyodbc)
- **Machine Learning**: PyTorch, MTCNN (Face detection), FaceEmbeddingNet (Face recognition), base64 image processing.

---

## Role-Based Workflows (Input -> Output)

### 1. Student Enrollment (Admin)
**Input:**
- Admin authenticates and selects "Manage Students".
- Provides student details: `PRN`, `Name`, `Panel`.
- Uploads exactly **25 face photos** of the student.

**Processing:**
- The images are pre-processed by MTCNN, which detects and crops the student's face from the 25 uploaded images.
- A custom `FaceEmbeddingNet` model extracts 128-dimensional facial embeddings for each cropped face.
- The `training_service.py` performs differential training, mapping the generated embeddings to the student's `PRN`.
- Model state is persisted into `trained_face_brain.pth` and `trained_face_brain_mappings.pkl`.
- Student metadata is saved in the `Student_Master` table in SQL Server.

**Output:**
- The student is registered in the database, and the facial recognition model is updated to dynamically recognize this student in future inferences.

### 2. Lecture Scheduling (Admin)
**Input:**
- Admin selects "Schedule Lecture".
- Provides details: `Date`, `Time`, `Panel / Branch`, and assigned `Teacher ID`.

**Processing:**
- Validates the inputs and checks for scheduling conflicts.
- Inserts a new record into the `Lecture_Master` table.

**Output:**
- A scheduled lecture is now instantiated in the system and becomes available on the assigned Teacher's dashboard.

### 3. Attendance Marking & Processing (Teacher)
**Input:**
- Teacher authenticates and selects the assigned lecture from the dashboard.
- Uploads one or more **classroom photos**.

**Processing:**
- **Decoding**: Backend receives Base64-encoded strings and translates them into numpy arrays/OpenCV arrays (`recognition_service.py`).
- **Face Detection**: MTCNN scans the classroom photos and detects all faces.
- **Embedding & Matching**: The `InferenceEngine` extracts embeddings for each detected face and matches them against the locally stored embeddings via cosine similarity. A similarity threshold of `0.6` is required for a positive match.
- **Resolution**: Successfully matched embeddings correlate to a `PRN`, which looks up the student's name in `Student_Master`. Unidentified faces receive a temporary UUID and are kept in cache for manual verification.

**Output:**
- Present students and unidentified instances are formatted into a JSON response sent to the frontend for Teacher validation.

### 4. Attendance Finalization (Teacher)
**Input:**
- Teacher reviews the automatically recognized names on the "Results" page (with options to adjust anomalies) and clicks **Finalize Attendance**.

**Processing:**
- Inserts confirmed present records into the `Attendance_Record` table mapped to the lecture ID.
- Generates a local CSV export file via `csv_service.py`.

**Output:**
- Finalize endpoint dumps `{panel}_{lecture_name}_{datetime}.csv` in the `backend/Attendance Records/` directory.

### 5. Administrative Controls
* **Superadmin:**
    - **Input:** Superadmin credentials, new Admin details.
    - **Process:** Secure bcrypt hashing for passwords.
    - **Output:** Database insertion of `privilege_level = 1` or Superadmin and `2` for Admin.
* **Admin:**
    - **Input:** Admin credentials, new Teacher details.
    - **Process:** Bcrypt hashing.
    - **Output:** New Teacher accounts (`privilege_level = 3`) provisioned for the system.
