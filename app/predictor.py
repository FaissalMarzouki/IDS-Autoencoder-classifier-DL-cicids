"""
IDS Predictor Module
Charge le modele AutoencoderIDS et effectue des predictions
"""

import torch
import torch.nn as nn
import numpy as np
import joblib
import json
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, asdict


@dataclass
class PredictionResult:
    """Resultat d'une prediction IDS"""
    flow_id: str
    predicted_class: str
    predicted_class_id: int
    confidence: float
    anomaly_score: float
    is_attack: bool
    all_probabilities: Dict[str, float]
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


class AutoencoderIDS(nn.Module):
    """Architecture Autoencoder pour IDS"""
    
    def __init__(
        self, 
        input_dim: int,
        latent_dim: int = 16,
        hidden_dims: List[int] = [128, 64, 32],
        num_classes: int = 7,
        dropout: float = 0.3
    ):
        super(AutoencoderIDS, self).__init__()
        
        self.input_dim = input_dim
        self.latent_dim = latent_dim
        self.num_classes = num_classes
        
        # ENCODER
        encoder_layers = []
        prev_dim = input_dim
        for hidden_dim in hidden_dims:
            encoder_layers.extend([
                nn.Linear(prev_dim, hidden_dim),
                nn.BatchNorm1d(hidden_dim),
                nn.LeakyReLU(0.2),
                nn.Dropout(dropout)
            ])
            prev_dim = hidden_dim
        encoder_layers.append(nn.Linear(prev_dim, latent_dim))
        self.encoder = nn.Sequential(*encoder_layers)
        
        # DECODER
        decoder_layers = []
        prev_dim = latent_dim
        for hidden_dim in reversed(hidden_dims):
            decoder_layers.extend([
                nn.Linear(prev_dim, hidden_dim),
                nn.BatchNorm1d(hidden_dim),
                nn.LeakyReLU(0.2),
                nn.Dropout(dropout * 0.5)
            ])
            prev_dim = hidden_dim
        decoder_layers.append(nn.Linear(prev_dim, input_dim))
        self.decoder = nn.Sequential(*decoder_layers)
        
        # CLASSIFIER
        classifier_input = latent_dim + 1
        self.classifier = nn.Sequential(
            nn.Linear(classifier_input, 64),
            nn.BatchNorm1d(64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, 32),
            nn.BatchNorm1d(32),
            nn.ReLU(),
            nn.Dropout(dropout * 0.5),
            nn.Linear(32, num_classes)
        )
    
    def encode(self, x: torch.Tensor) -> torch.Tensor:
        return self.encoder(x)
    
    def decode(self, z: torch.Tensor) -> torch.Tensor:
        return self.decoder(z)
    
    def compute_reconstruction_error(self, x: torch.Tensor, x_reconstructed: torch.Tensor) -> torch.Tensor:
        return torch.mean((x - x_reconstructed) ** 2, dim=1, keepdim=True)
    
    def forward(self, x: torch.Tensor, return_all: bool = False):
        latent = self.encode(x)
        reconstructed = self.decode(latent)
        recon_error = self.compute_reconstruction_error(x, reconstructed)
        classifier_input = torch.cat([latent, recon_error], dim=1)
        class_logits = self.classifier(classifier_input)
        
        if return_all:
            return class_logits, reconstructed, latent, recon_error
        return class_logits, reconstructed, recon_error


class IDSPredictor:
    """Classe principale pour les predictions IDS"""
    
    def __init__(self, models_dir: str = '../models'):
        self.models_dir = models_dir
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        # Charger la configuration
        with open(f'{models_dir}/model_config.json', 'r') as f:
            self.config = json.load(f)
        
        # Charger les noms des features
        with open(f'{models_dir}/feature_names.json', 'r') as f:
            self.feature_names = json.load(f)
        
        # Charger le scaler et label encoder
        self.scaler = joblib.load(f'{models_dir}/scaler.joblib')
        self.label_encoder = joblib.load(f'{models_dir}/label_encoder.joblib')
        self.percentiles = joblib.load(f'{models_dir}/percentiles.joblib')
        
        # Charger le modele
        self.model = AutoencoderIDS(
            input_dim=self.config['input_dim'],
            latent_dim=self.config['latent_dim'],
            hidden_dims=self.config['hidden_dims'],
            num_classes=self.config['num_classes']
        ).to(self.device)
        
        # Charger le checkpoint (format complet avec metadata)
        checkpoint = torch.load(f'{models_dir}/autoencoder_ids_v1.1.0.pt', 
                               map_location=self.device, weights_only=False)
        
        # Extraire le state_dict selon le format
        if isinstance(checkpoint, dict) and 'model_state_dict' in checkpoint:
            state_dict = checkpoint['model_state_dict']
        else:
            state_dict = checkpoint
        
        self.model.load_state_dict(state_dict)
        self.model.eval()
        
        # Seuils
        self.anomaly_threshold = self.config['thresholds']['anomaly']
        self.class_names = self.config['class_names']
        
        self._flow_counter = 0
    
    def preprocess(self, features: np.ndarray) -> torch.Tensor:
        """Preprocesse les features brutes"""
        features = np.array(features).reshape(1, -1).astype(np.float64)
        
        # Clipping avec percentiles (format dict avec 'p01' et 'p99')
        p01 = self.percentiles['p01']
        p99 = self.percentiles['p99']
        features = np.clip(features, p01, p99)
        
        # Normalisation
        features_scaled = self.scaler.transform(features)
        
        return torch.tensor(features_scaled, dtype=torch.float32).to(self.device)
    
    def predict(self, features: np.ndarray, flow_id: Optional[str] = None) -> PredictionResult:
        """Effectue une prediction sur un flux reseau"""
        
        if flow_id is None:
            self._flow_counter += 1
            flow_id = f"flow_{self._flow_counter:08d}"
        
        # Preprocess
        x = self.preprocess(features)
        
        # Prediction
        with torch.no_grad():
            logits, reconstructed, recon_error = self.model(x)
            probabilities = torch.softmax(logits, dim=1)
            
            predicted_class_id = torch.argmax(probabilities, dim=1).item()
            confidence = probabilities[0, predicted_class_id].item()
            anomaly_score = recon_error.item()
        
        predicted_class = self.class_names[predicted_class_id]
        is_attack = predicted_class != 'Normal Traffic'
        
        # Probabilites par classe
        all_probs = {
            self.class_names[i]: round(probabilities[0, i].item(), 4)
            for i in range(len(self.class_names))
        }
        
        return PredictionResult(
            flow_id=flow_id,
            predicted_class=predicted_class,
            predicted_class_id=predicted_class_id,
            confidence=round(confidence, 4),
            anomaly_score=round(anomaly_score, 6),
            is_attack=is_attack,
            all_probabilities=all_probs
        )
    
    def predict_batch(self, features_batch: np.ndarray) -> List[PredictionResult]:
        """Prediction sur un batch de flux"""
        results = []
        for features in features_batch:
            results.append(self.predict(features))
        return results
