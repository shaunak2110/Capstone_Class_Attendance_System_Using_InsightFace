import os
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms
from PIL import Image

# Import the brain we just built! (Make sure you renamed the file to face_model.py)
from face_model import FaceEmbeddingNet

# --- 1. THE DATA LOADER ---
# This acts as a librarian, fetching images and turning them into PyTorch tensors
class FaceDataset(Dataset):
    def __init__(self, root_dir):
        self.root_dir = root_dir
        self.image_paths = []
        self.labels = []
        self.classes = sorted(os.listdir(root_dir))
        
        # Give each person an integer ID (0, 1, 2, 3)
        self.class_to_idx = {cls_name: i for i, cls_name in enumerate(self.classes)}
        
        for cls_name in self.classes:
            cls_dir = os.path.join(root_dir, cls_name)
            if not os.path.isdir(cls_dir): continue
            for img_name in os.listdir(cls_dir):
                self.image_paths.append(os.path.join(cls_dir, img_name))
                self.labels.append(self.class_to_idx[cls_name])
                
        # Basic transformations: resize to 112x112 and convert to PyTorch numbers
        self.transform = transforms.Compose([
            transforms.Resize((112, 112)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.5, 0.5, 0.5], std=[0.5, 0.5, 0.5])
        ])

    def __len__(self):
        return len(self.image_paths)

    def __getitem__(self, idx):
        img_path = self.image_paths[idx]
        image = Image.open(img_path).convert('RGB')
        image = self.transform(image)
        label = self.labels[idx]
        return image, label

# --- 2. THE TRIPLET LOSS (ONLINE HARD MINING) ---
# This is the referee for our "Guess Who" game
class TripletLoss(nn.Module):
    def __init__(self, margin=0.3):
        super().__init__()
        self.margin = margin
    
    def forward(self, embeddings, labels):
        # Calculate the distance between every single image in the batch
        dot_product = torch.mm(embeddings, embeddings.t())
        sq_norm = dot_product.diag()
        distances = sq_norm.unsqueeze(0) - 2 * dot_product + sq_norm.unsqueeze(1)
        pairwise_dist = F.relu(distances).sqrt()
        
        loss = 0.0
        num_valid = 0
        
        for i in range(len(labels)):
            anchor_label = labels[i]
            
            # Find the HARDEST positive (Same person, but the model thinks they look different)
            pos_mask = (labels == anchor_label)
            pos_mask[i] = False # Don't compare with self
            if not pos_mask.any(): continue
            hardest_positive = pairwise_dist[i][pos_mask].max()
            
            # Find the HARDEST negative (Different person, but the model thinks they look similar)
            neg_mask = (labels != anchor_label)
            if not neg_mask.any(): continue
            hardest_negative = pairwise_dist[i][neg_mask].min()
            
            # Calculate loss: pushes positives close, pushes negatives far
            triplet_loss = F.relu(hardest_positive - hardest_negative + self.margin)
            loss += triplet_loss
            num_valid += 1
        
        return loss / num_valid if num_valid > 0 else torch.tensor(0.0)

# --- 3. THE TRAINING LOOP ---
def main():
    print("Setting up the training room...")
    
    # Configuration
    BATCH_SIZE = 32 # How many images to look at at once
    EPOCHS = 20     # How many times to read the entire dataset
    
    # Check if we can use the GPU (makes it much faster)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")
    
    # Load the data and the model
    dataset = FaceDataset("dataset_augmented")
    dataloader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True, drop_last=True)
    
    model = FaceEmbeddingNet(embedding_dim=128).to(device)
    criterion = TripletLoss(margin=0.3)
    
    # The Optimizer updates the factory gears based on the loss
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-4)
    # The Scheduler slowly lowers the learning rate so the model can fine-tune
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=EPOCHS)
    
    print(f"Found {len(dataset)} augmented images. Starting training for {EPOCHS} epochs!\n")
    
    for epoch in range(EPOCHS):
        model.train()
        total_loss = 0
        
        for images, labels in dataloader:
            images, labels = images.to(device), labels.to(device)
            
            optimizer.zero_grad()               # Reset gradients
            embeddings = model(images)          # Get ID badges
            loss = criterion(embeddings, labels)# Calculate score
            loss.backward()                     # Calculate how to adjust gears
            
            # This keeps the math stable if it gets too crazy
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0) 
            optimizer.step()                    # Actually adjust the gears
            
            total_loss += loss.item()
            
        scheduler.step()
        
        avg_loss = total_loss / len(dataloader)
        print(f"Epoch {epoch+1}/{EPOCHS} | Loss: {avg_loss:.4f} | LR: {scheduler.get_last_lr()[0]:.6f}")

    # Save the trained brain!
    torch.save(model.state_dict(), "trained_face_brain.pth")
    print("\nTraining Complete! Brain saved as 'trained_face_brain.pth'")

if __name__ == "__main__":
    main()