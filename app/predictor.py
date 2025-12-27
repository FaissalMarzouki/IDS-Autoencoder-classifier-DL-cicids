# ============================================================================
# PREDICTOR.PY - Classe de prédiction IDS utilisant le modèle entraîné
# ============================================================================
"""
Module de prédiction pour le système IDS.
Charge le modèle PyTorch entraîné et effectue des prédictions en temps réel.
"""

import torch
import torch.nn as nn
import numpy as np
import joblib
import json
import os
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Tuple
from datetime import datetime


# ============================================================================
# DATACLASS POUR LES RÉSULTATS
# ============================================================================

@dataclass
class PredictionResult:
    """Résultat d'une prédiction IDS."""
    flow_id: str
    timestamp: str
    predicted_class: str
    predicted_class_id: int
    confidence: float
    anomaly_score: float
    is_attack: bool
    is_anomaly: bool
    all_probabilities: Dict[str, float]
    reconstruction_error: float
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


# ============================================================================
# ARCHITECTURE DU MODÈLE (identique au notebook)
# ============================================================================

class AutoencoderIDS(nn.Module):
    """Architecture Autoencoder hybride pour la détection d'intrusions."""
    
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


# ============================================================================
# CLASSE PREDICTOR
# ============================================================================

class IDSPredictor:
    """
    Classe principale pour effectuer des prédictions IDS.
    
    Usage:
        predictor = IDSPredictor('./models')
        result = predictor.predict(features_array)
        print(result.predicted_class, result.confidence)
    """
    
    def __init__(self, models_dir: str = "../models"):
        """
        Initialise le prédicteur en chargeant tous les artefacts.
        
        Args:
            models_dir: Chemin vers le dossier contenant les modèles
        """
        self.models_dir = models_dir
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        # Charger la configuration
        self._load_config()
        
        # Charger les artefacts de preprocessing
        self._load_preprocessing()
        
        # Charger le modèle
        self._load_model()
        
        # Compteur pour les IDs de flux
        self._flow_counter = 0
        
        print(f"✅ IDSPredictor initialisé sur {self.device}")
        print(f"   • Classes: {self.class_names}")
        print(f"   • Features: {self.config['input_dim']}")
    
    def _load_config(self):
        """Charge la configuration du modèle."""
        config_path = os.path.join(self.models_dir, "model_config.json")
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        
        self.class_names = self.config['class_names']
        self.thresholds = self.config.get('thresholds', {
            'anomaly': 0.5,
            'high_confidence': 0.85
        })
    
    def _load_preprocessing(self):
        """Charge les artefacts de preprocessing."""
        # Scaler
        scaler_path = os.path.join(self.models_dir, "scaler.joblib")
        self.scaler = joblib.load(scaler_path)
        
        # Label Encoder
        le_path = os.path.join(self.models_dir, "label_encoder.joblib")
        self.label_encoder = joblib.load(le_path)
        
        # Feature names
        features_path = os.path.join(self.models_dir, "feature_names.json")
        with open(features_path, 'r') as f:
            self.feature_names = json.load(f)
        
        # Percentiles (pour clipping)
        percentiles_path = os.path.join(self.models_dir, "percentiles.joblib")
        if os.path.exists(percentiles_path):
            self.percentiles = joblib.load(percentiles_path)
        else:
            self.percentiles = None
    
    def _load_model(self):
        """Charge le modèle PyTorch."""
        self.model = AutoencoderIDS(
            input_dim=self.config['input_dim'],
            latent_dim=self.config['latent_dim'],
            hidden_dims=self.config['hidden_dims'],
            num_classes=self.config['num_classes']
        ).to(self.device)
        
        model_path = os.path.join(self.models_dir, "autoencoder_ids_v1.1.0.pt")
        checkpoint = torch.load(model_path, map_location=self.device, weights_only=False)
        
        # Le modèle peut être sauvegardé soit directement (state_dict) 
        # soit dans un checkpoint complet avec 'model_state_dict'
        if isinstance(checkpoint, dict) and 'model_state_dict' in checkpoint:
            self.model.load_state_dict(checkpoint['model_state_dict'])
        else:
            self.model.load_state_dict(checkpoint)
        
        self.model.eval()
    
    def preprocess(self, features: np.ndarray) -> np.ndarray:
        """
        Prétraite les features avant prédiction.
        
        Args:
            features: Array de features brutes (1D ou 2D)
            
        Returns:
            Features normalisées
        """
        # Assurer que c'est 2D
        if features.ndim == 1:
            features = features.reshape(1, -1)
        
        # Clipping des outliers si percentiles disponibles
        if self.percentiles is not None:
            # Support pour différents formats de clés
            lower_key = 'lower' if 'lower' in self.percentiles else 'p01'
            upper_key = 'upper' if 'upper' in self.percentiles else 'p99'
            
            features = np.clip(
                features, 
                self.percentiles[lower_key], 
                self.percentiles[upper_key]
            )
        
        # Normalisation
        features_scaled = self.scaler.transform(features)
        
        return features_scaled
    
    def predict(
        self, 
        features: np.ndarray, 
        flow_id: Optional[str] = None
    ) -> PredictionResult:
        """
        Effectue une prédiction sur un flux réseau.
        
        Args:
            features: Array de features (shape: (n_features,) ou (1, n_features))
            flow_id: ID optionnel du flux (auto-généré si non fourni)
            
        Returns:
            PredictionResult contenant tous les détails de la prédiction
        """
        # Générer un ID si nécessaire
        if flow_id is None:
            self._flow_counter += 1
            flow_id = f"flow_{self._flow_counter:08d}"
        
        # Prétraitement
        features_processed = self.preprocess(features)
        
        # Conversion en tensor
        x = torch.tensor(features_processed, dtype=torch.float32).to(self.device)
        
        # Prédiction
        with torch.no_grad():
            logits, reconstructed, recon_error = self.model(x)
            probabilities = torch.softmax(logits, dim=1)
        
        # Extraction des résultats
        probs_np = probabilities.cpu().numpy()[0]
        predicted_class_id = int(np.argmax(probs_np))
        confidence = float(probs_np[predicted_class_id])
        recon_error_value = float(recon_error.cpu().numpy()[0, 0])
        
        # Déterminer si c'est une attaque
        predicted_class = self.class_names[predicted_class_id]
        is_attack = predicted_class != "Normal Traffic"
        
        # Score d'anomalie normalisé (basé sur reconstruction error)
        # Plus le score est élevé, plus c'est suspect
        anomaly_score = min(recon_error_value / self.thresholds['anomaly'], 1.0)
        is_anomaly = recon_error_value > self.thresholds['anomaly']
        
        # Dictionnaire des probabilités
        all_probs = {
            self.class_names[i]: float(probs_np[i]) 
            for i in range(len(self.class_names))
        }
        
        return PredictionResult(
            flow_id=flow_id,
            timestamp=datetime.now().isoformat(),
            predicted_class=predicted_class,
            predicted_class_id=predicted_class_id,
            confidence=confidence,
            anomaly_score=anomaly_score,
            is_attack=is_attack,
            is_anomaly=is_anomaly,
            all_probabilities=all_probs,
            reconstruction_error=recon_error_value
        )
    
    def predict_batch(
        self, 
        features_batch: np.ndarray,
        flow_ids: Optional[List[str]] = None
    ) -> List[PredictionResult]:
        """
        Effectue des prédictions sur un batch de flux.
        
        Args:
            features_batch: Array de features (shape: (n_samples, n_features))
            flow_ids: Liste optionnelle d'IDs de flux
            
        Returns:
            Liste de PredictionResult
        """
        n_samples = features_batch.shape[0]
        
        if flow_ids is None:
            flow_ids = [None] * n_samples
        
        results = []
        for i in range(n_samples):
            result = self.predict(features_batch[i], flow_ids[i])
            results.append(result)
        
        return results


# ============================================================================
# TEST STANDALONE
# ============================================================================

if __name__ == "__main__":
    import sys
    
    # Test basique
    print("=" * 60)
    print("TEST DU PREDICTOR IDS")
    print("=" * 60)
    
    try:
        predictor = IDSPredictor("../models")
        
        # Créer un flux de test (features aléatoires)
        test_features = np.random.randn(predictor.config['input_dim'])
        
        result = predictor.predict(test_features)
        
        print(f"\n📊 Résultat de prédiction:")
        print(f"   • Classe: {result.predicted_class}")
        print(f"   • Confiance: {result.confidence:.2%}")
        print(f"   • Score anomalie: {result.anomaly_score:.3f}")
        print(f"   • Est attaque: {result.is_attack}")
        print(f"   • Est anomalie: {result.is_anomaly}")
        
        print("\n✅ Test réussi!")
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        sys.exit(1)
