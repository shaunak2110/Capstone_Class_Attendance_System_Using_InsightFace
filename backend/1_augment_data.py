import cv2
import os
import numpy as np
import albumentations as A

# --- CONFIGURATION ---
INPUT_FOLDER = "dataset"
OUTPUT_FOLDER = "dataset_augmented"
IMAGES_PER_PHOTO = 50  # How many clones to make per original photo

# 1. Define the "Magic Funhouse" Pipeline
# This defines all the ways we will mess up the photos
transform = A.Compose([
    A.HorizontalFlip(p=0.5),             # Flip left/right
    A.Rotate(limit=20, p=0.7),           # Tilt the head
    A.RandomBrightnessContrast(p=0.8),   # Change lighting
    A.GaussianBlur(blur_limit=3, p=0.3), # Make it blurry
    A.GaussNoise(p=0.3),                 # Add TV static/grain
    A.CLAHE(p=0.4),                      # Enhance contrast (good for features)
    # This last one cuts out small squares to simulate "occlusion" (hair/glasses blocking view)
    A.CoarseDropout(max_holes=4, max_height=10, max_width=10, p=0.3), 
])

def create_clones():
    # check if output folder exists, if not, create it
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)
    
    # Walk through the input folder
    for person_name in os.listdir(INPUT_FOLDER):
        person_path = os.path.join(INPUT_FOLDER, person_name)
        
        # Skip hidden files
        if not os.path.isdir(person_path):
            continue

        print(f"Starting cloning process for: {person_name}")
        
        # Create a folder for this person in the output directory
        save_path = os.path.join(OUTPUT_FOLDER, person_name)
        if not os.path.exists(save_path):
            os.makedirs(save_path)
            
        # Loop through every image of this person
        image_files = os.listdir(person_path)
        for img_name in image_files:
            img_path = os.path.join(person_path, img_name)
            
            # Read the image using OpenCV
            image = cv2.imread(img_path)
            
            if image is None:
                print(f"Skipping bad file: {img_name}")
                continue
                
            # --- THE CLONING LOOP ---
            for i in range(IMAGES_PER_PHOTO):
                # Apply the magic transformations
                augmented = transform(image=image)["image"]
                
                # Save the new file
                # Name it: originalname_clone_0.jpg, originalname_clone_1.jpg...
                new_filename = f"{os.path.splitext(img_name)[0]}_clone_{i}.jpg"
                cv2.imwrite(os.path.join(save_path, new_filename), augmented)

    print("\n--- CLONING COMPLETE ---")
    print(f"Check the '{OUTPUT_FOLDER}' directory for your new army of data.")

if __name__ == "__main__":
    create_clones()