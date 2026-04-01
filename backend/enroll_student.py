"""
Student Enrollment Script
=========================
Usage:
1. Create a folder under student_photos/<PRN>/ and put exactly 25 face images in it
2. Edit the CONFIG section below with the student's details
3. Run: python enroll_student.py
"""

import base64
import json
import requests
import os

# ============================================================
# CONFIG - Edit these values before running
# ============================================================
PRN        = "PRN001"           # Student PRN number
NAME       = "Student Name"     # Student full name
PANEL      = "H"                # Panel/class (e.g. H, A, B)
ADMIN_ID   = "1"                # Your admin user_id
API_URL    = "http://127.0.0.1:8000"
# ============================================================

def image_to_base64(image_path):
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode("utf-8")

def enroll_student():
    image_folder = os.path.join("student_photos", PRN)

    if not os.path.exists(image_folder):
        print(f"ERROR: Folder not found: {image_folder}")
        print(f"Please create the folder and add 25 images:")
        print(f"  backend/student_photos/{PRN}/")
        return

    # Collect all image files
    supported = (".jpg", ".jpeg", ".png", ".bmp")
    image_files = sorted([
        f for f in os.listdir(image_folder)
        if f.lower().endswith(supported)
    ])

    print(f"Found {len(image_files)} images in {image_folder}")

    if len(image_files) != 25:
        print(f"ERROR: Need exactly 25 images, found {len(image_files)}")
        print("Please add or remove images to make it exactly 25.")
        return

    print("Converting images to base64...")
    images = []
    for filename in image_files:
        img_path = os.path.join(image_folder, filename)
        images.append(image_to_base64(img_path))
        print(f"  ✓ {filename}")

    payload = {
        "prn": PRN,
        "name": NAME,
        "panel": PANEL,
        "images": images
    }

    print(f"\nEnrolling student: {NAME} (PRN: {PRN}, Panel: {PANEL})")
    print("Sending request to API...")

    try:
        response = requests.post(
            f"{API_URL}/admin/enroll-student",
            json=payload,
            headers={
                "X-User-Id": ADMIN_ID,
                "X-Privilege-Level": "2"
            },
            timeout=120  # training can take a while
        )

        if response.status_code == 200:
            print(f"\n✅ SUCCESS! Student enrolled.")
            print(json.dumps(response.json(), indent=2))
        elif response.status_code == 409:
            print(f"\n⚠️  Student with PRN {PRN} already exists.")
        elif response.status_code == 400:
            print(f"\n❌ Bad request: {response.json()}")
        else:
            print(f"\n❌ Error {response.status_code}: {response.json()}")

    except requests.exceptions.ConnectionError:
        print("\n❌ Cannot connect to API. Make sure the server is running:")
        print("   uvicorn main:app --reload")

if __name__ == "__main__":
    enroll_student()
