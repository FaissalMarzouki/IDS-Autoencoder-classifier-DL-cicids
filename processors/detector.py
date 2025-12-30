import torch
import torch.nn as nn
import joblib
import numpy as np
from .base import KafkaProcessor
from config import ARTIFACTS_PATH, INPUT_DIM, LATENT_DIM, NUM_CLASSES, HIDDEN_DIMS

class AutoencoderIDS(nn.Module):
    def __init__(self, input_dim=37, latent_dim=16, hidden_dims=[128, 64, 32], num_classes=7, dropout=0.3):
        super(AutoencoderIDS, self).__init__()
        
        # --- ENCODER (Identique au notebook) ---
        encoder_layers = []
        prev_dim = input_dim
        for h in hidden_dims:
            encoder_layers.extend([
                nn.Linear(prev_dim, h),
                nn.BatchNorm1d(h),
                nn.LeakyReLU(0.2),
                nn.Dropout(dropout)
            ])
            prev_dim = h
        encoder_layers.append(nn.Linear(prev_dim, latent_dim))
        self.encoder = nn.Sequential(*encoder_layers)
        
        # --- DECODER (Requis pour charger le state_dict) ---
        decoder_layers = []
        prev_dim = latent_dim
        for h in reversed(hidden_dims):
            decoder_layers.extend([
                nn.Linear(prev_dim, h),
                nn.BatchNorm1d(h),
                nn.LeakyReLU(0.2),
                nn.Dropout(dropout * 0.5)
            ])
            prev_dim = h
        decoder_layers.append(nn.Linear(prev_dim, input_dim))
        self.decoder = nn.Sequential(*decoder_layers)
        
        # --- CLASSIFIER (Prend latent + recon_error) ---
        self.classifier = nn.Sequential(
            nn.Linear(latent_dim + 1, 64),
            nn.BatchNorm1d(64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, 32),
            nn.BatchNorm1d(32),
            nn.ReLU(),
            nn.Dropout(dropout * 0.5),
            nn.Linear(32, num_classes)
        )

    def forward(self, x):
        latent = self.encoder(x)
        reconstructed = self.decoder(latent)
        # MSE par sample
        recon_error = torch.mean((x - reconstructed)**2, dim=1, keepdim=True)
        # Concaténation (C'est ici que le +1 intervient)
        clf_input = torch.cat([latent, recon_error], dim=1)
        return self.classifier(clf_input)

class IDSDetector(KafkaProcessor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.device = torch.device('cpu')
        
        # Charger le modèle
        self.model = AutoencoderIDS(
            input_dim=INPUT_DIM, 
            latent_dim=LATENT_DIM, 
            hidden_dims=HIDDEN_DIMS, 
            num_classes=NUM_CLASSES
        )
        
        checkpoint = torch.load(f"{ARTIFACTS_PATH}autoencoder_ids_v1.1.0.pt", map_location=self.device)
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.model.eval()
        
        # Charger les artefacts de preprocessing
        self.scaler = joblib.load(f"{ARTIFACTS_PATH}scaler.joblib")
        self.percentiles = joblib.load(f"{ARTIFACTS_PATH}percentiles.joblib")
        self.label_encoder = joblib.load(f"{ARTIFACTS_PATH}label_encoder.joblib")
        
        print("✅ Détecteur initialisé avec l'architecture hybride complète.")

    def process(self, data):
        # 1. On récupère les features DÉJÀ scalées par le preprocessor
        feat_array = np.array(data['features']).reshape(1, -1)
        
        # 2. Conversion directe en Tensor (PAS DE SCALER ICI !)
        features_tensor = torch.tensor(feat_array, dtype=torch.float32).to(self.device)
        
        # 3. Inférence
        self.model.eval()
        with torch.no_grad():
            logits = self.model(features_tensor)
            probs = torch.softmax(logits, dim=1)
            conf, pred_idx = torch.max(probs, dim=1)
            
        prediction = self.label_encoder.inverse_transform([pred_idx.item()])[0]
        
        # Debug pour le test
        # print(f"🔍 [DEBUG] Prediction: {prediction} | Confidence: {conf.item():.2%}")
        
        if prediction != "Normal Traffic":
            print(f"🚨 ALERT: {prediction} (Confiance: {conf.item():.2%})")