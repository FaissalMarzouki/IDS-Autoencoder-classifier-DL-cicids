# processors/detector.py
import torch
import torch.nn as nn
import joblib
from .base import KafkaProcessor
from config import ARTIFACTS_PATH, INPUT_DIM, LATENT_DIM, NUM_CLASSES

class AutoencoderIDS(nn.Module):
    def __init__(self):
        super().__init__()
        # On définit exactement la structure attendue par les clés "encoder.0", "encoder.2"
        self.encoder = nn.Sequential(
            nn.Linear(INPUT_DIM, 128), # encoder.0
            nn.ReLU(),                 # encoder.1
            nn.Linear(128, LATENT_DIM) # encoder.2
        )
        self.classifier = nn.Linear(LATENT_DIM, NUM_CLASSES)
        
    def forward(self, x):
        latent = self.encoder(x)
        logits = self.classifier(latent)
        return logits

class IDSDetector(KafkaProcessor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model = AutoencoderIDS()
        
        # --- CORRECTION ICI ---
        # 1. Charger le checkpoint complet
        checkpoint = torch.load(
            f"{ARTIFACTS_PATH}autoencoder_ids_v1.1.0.pt", 
            map_location=torch.device('cpu') # Assure la compatibilité si entraîné sur GPU
        )
        
        # 2. Charger uniquement la partie 'model_state_dict' dans le modèle
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.model.eval()
        
        self.label_encoder = joblib.load(f"{ARTIFACTS_PATH}label_encoder.joblib")
        print("✅ Modèle chargé avec succès depuis le checkpoint.")
