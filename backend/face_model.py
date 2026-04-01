import torch
import torch.nn as nn
import torch.nn.functional as F

class FaceEmbeddingNet(nn.Module):
    def __init__(self, embedding_dim=128):
        super().__init__()
        
        # Block 1: Looks for basic edges and lines
        self.block1 = nn.Sequential(
            nn.Conv2d(3, 32, kernel_size=3, padding=1), # 3 means RGB colors. 32 filters.
            nn.BatchNorm2d(32),                         # Keeps the math stable
            nn.PReLU(),                                 # The "activation" - decides what passes through
            nn.MaxPool2d(2, 2)                          # Shrinks the image to save memory
        )
        
        # Block 2: Looks for simple shapes
        self.block2 = nn.Sequential(
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.PReLU(),
            nn.MaxPool2d(2, 2)
        )
        
        # Block 3: Looks for complex shapes (eyes, noses)
        self.block3 = nn.Sequential(
            nn.Conv2d(64, 128, kernel_size=3, padding=1),
            nn.BatchNorm2d(128),
            nn.PReLU(),
            nn.MaxPool2d(2, 2)
        )
        
        # Block 4: The final feature map
        self.block4 = nn.Sequential(
            nn.Conv2d(128, 256, kernel_size=3, padding=1),
            nn.BatchNorm2d(256),
            nn.PReLU(),
            nn.MaxPool2d(2, 2)
        )
        
        # The Output Head: Turns the features into our 128-number ID badge
        self.global_avg_pool = nn.AdaptiveAvgPool2d(1)   
        self.fc1 = nn.Linear(256, 256)
        self.bn_fc = nn.BatchNorm1d(256)
        self.prelu_fc = nn.PReLU()
        self.dropout = nn.Dropout(0.4)                   # Randomly turns off neurons to prevent memorizing
        self.fc2 = nn.Linear(256, embedding_dim)         # Shrinks it down to exactly 128
        
    def forward(self, x):
        # This is the actual path the image takes through our factory
        x = self.block1(x)
        x = self.block2(x)
        x = self.block3(x)
        x = self.block4(x)
        x = self.global_avg_pool(x)
        
        x = x.view(x.size(0), -1)          # Flattens the 3D data into a 1D list
        
        x = self.fc1(x)
        x = self.bn_fc(x)
        x = self.prelu_fc(x)
        x = self.dropout(x)
        x = self.fc2(x)
        
        # SUPER IMPORTANT: L2 Normalization
        # This forces all our 128-number lists to be on the same scale (a unit sphere)
        # Without this, comparing distances later won't work!
        x = F.normalize(x, p=2, dim=1)     
        
        return x

# --- QUICK TEST TO MAKE SURE IT WORKS ---
if __name__ == "__main__":
    print("Building the brain...")
    model = FaceEmbeddingNet(embedding_dim=128)
    
    # Let's create a fake "dummy" image (1 image, 3 color channels, 112x112 pixels)
    # This simulates what will happen when we feed it a real cropped face
    dummy_image = torch.randn(2, 3, 112, 112) 
    
    # Run the dummy image through the brain
    output = model(dummy_image)
    
    print(f"Success! The brain output a list of {output.shape[1]} numbers.")
    print("Here are the first 5 numbers of the embedding:")
    print(output[0][:5].detach().numpy())