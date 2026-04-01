import torch
import os
import numpy as np
from PIL import Image
from torchvision import transforms

# Import our brain architecture
from face_model import FaceEmbeddingNet

# --- 1. CONFIGURATION ---
KNOWN_FACES_DIR = "dataset"          # The folder with original, clean photos
TEST_IMAGE_PATH = "test_photo_1.jpeg"   # We will create this file in a moment!
MODEL_WEIGHTS = "trained_face_brain.pth"
THRESHOLD = 0.8                      # Distance threshold (lower = stricter)

# The exact same preprocessing we used during training
preprocess = transforms.Compose([
    transforms.Resize((112, 112)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.5, 0.5, 0.5], std=[0.5, 0.5, 0.5])
])

# --- 2. ENROLLMENT (BUILDING THE DATABASE) ---
def build_database(model, device):
    print("Building database of known faces...")
    database = {}
    
    # Go through the original dataset folder
    for person_name in os.listdir(KNOWN_FACES_DIR):
        person_dir = os.path.join(KNOWN_FACES_DIR, person_name)
        if not os.path.isdir(person_dir): continue
        
        embeddings = []
        # Grab the first 3 images to create a strong average ID badge
        images = os.listdir(person_dir)[:3] 
        
        for img_name in images:
            img_path = os.path.join(person_dir, img_name)
            image = Image.open(img_path).convert('RGB')
            input_tensor = preprocess(image).unsqueeze(0).to(device) # Add batch dimension
            
            with torch.no_grad(): # No training allowed here!
                emb = model(input_tensor)
            embeddings.append(emb.cpu().squeeze().numpy())
        
        # Average the embeddings for stability and re-normalize
        mean_embedding = np.mean(embeddings, axis=0)
        mean_embedding /= np.linalg.norm(mean_embedding) 
        database[person_name] = mean_embedding
        print(f" -> Enrolled: {person_name}")
        
    return database

# --- 3. RECOGNITION (THE EXAM) ---
def recognize_face(model, image_path, database, device):
    print(f"\nAnalyzing unknown face: {image_path}")
    image = Image.open(image_path).convert('RGB')
    input_tensor = preprocess(image).unsqueeze(0).to(device)
    
    with torch.no_grad():
        query_emb = model(input_tensor).cpu().squeeze().numpy()
    
    best_match = None
    best_distance = float('inf')
    
    # Compare against everyone in the database
    print("\n--- Matching Distances ---")
    for name, stored_emb in database.items():
        # Calculate Euclidean distance
        dist = np.linalg.norm(query_emb - stored_emb)
        print(f"Distance to {name}: {dist:.4f}")
        
        if dist < best_distance:
            best_distance = dist
            best_match = name
            
    print("--------------------------")
    # Final Verdict
    if best_distance < THRESHOLD:
        print(f"\nVERDICT: MATCH FOUND! This is {best_match.upper()} (Distance: {best_distance:.4f})")
    else:
        print(f"\nVERDICT: UNKNOWN PERSON. Closest was {best_match} but distance ({best_distance:.4f}) was above threshold.")

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    # Load the brain and the memories (weights)
    model = FaceEmbeddingNet(embedding_dim=128).to(device)
    model.load_state_dict(torch.load(MODEL_WEIGHTS, map_location=device, weights_only=True))
    model.eval() # Put model in test mode (turns off Dropout)
    
    # 1. Build database
    db = build_database(model, device)
    
    # 2. Test a new image
    if os.path.exists(TEST_IMAGE_PATH):
        recognize_face(model, TEST_IMAGE_PATH, db, device)
    else:
        print(f"\n[!] Please put a new, cropped picture in the folder and name it '{TEST_IMAGE_PATH}'")