import torch
import numpy as np
from PIL import Image
from torchvision import transforms
from facenet_pytorch import MTCNN
from face_model import FaceEmbeddingNet

class FaceRecognitionEngine:
    def __init__(self, weights_path="trained_face_brain.pth", threshold=0.8):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.threshold = threshold
        
        # 1. Load the Detector (MTCNN)
        self.detector = MTCNN(keep_all=True, device=self.device)
        
        # 2. Load Your Custom Brain
        self.model = FaceEmbeddingNet(embedding_dim=128).to(self.device)
        self.model.load_state_dict(torch.load(weights_path, map_location=self.device, weights_only=True))
        self.model.eval()
        
        # 3. Preprocessing steps
        self.preprocess = transforms.Compose([
            transforms.Resize((112, 112)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.5, 0.5, 0.5], std=[0.5, 0.5, 0.5])
        ])

    def get_embedding(self, pil_image):
        """Used when enrolling a brand new student into the system."""
        # Detect face, crop, and generate the 128-number list
        box, _ = self.detector.detect(pil_image)
        if box is None:
            return None # No face found
            
        x1, y1, x2, y2 = [int(c) for c in box[0]]
        face_crop = pil_image.crop((max(0, x1-20), max(0, y1-20), min(pil_image.width, x2+20), min(pil_image.height, y2+20)))
        
        tensor = self.preprocess(face_crop).unsqueeze(0).to(self.device)
        with torch.no_grad():
            embedding = self.model(tensor).cpu().squeeze().numpy().tolist() # Convert to standard Python list
        return embedding

    def scan_classroom(self, pil_image, database_embeddings):
        """Used during a lecture to mark attendance."""
        # database_embeddings should be a dict: {"student_id": [128 floats]}
        boxes, _ = self.detector.detect(pil_image)
        results = []
        
        if boxes is None:
            return results
            
        for box in boxes:
            x1, y1, x2, y2 = [int(c) for c in box]
            face_crop = pil_image.crop((max(0, x1-20), max(0, y1-20), min(pil_image.width, x2+20), min(pil_image.height, y2+20)))
            
            tensor = self.preprocess(face_crop).unsqueeze(0).to(self.device)
            with torch.no_grad():
                query_emb = self.model(tensor).cpu().squeeze().numpy()
                
            best_match = "Unknown"
            best_dist = float('inf')
            
            for student_id, stored_emb in database_embeddings.items():
                stored_emb_np = np.array(stored_emb)
                dist = np.linalg.norm(query_emb - stored_emb_np)
                if dist < best_dist:
                    best_dist = float(dist)
                    if dist < self.threshold:
                        best_match = student_id
                        
            # Return standard Python dictionaries for Shaunak to turn into JSON
            results.append({
                "student_id": best_match,
                "distance": best_dist,
                "bounding_box": [x1, y1, x2, y2]
            })
            
        return results