"""
Service de streaming de dataset CICIDS2017
Lit le CSV, fait les prédictions avec le modèle, publie dans Kafka
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
import torch
import joblib
import json
import time
from datetime import datetime
from kafka import KafkaProducer
from pathlib import Path

# Imports depuis le projet principal
from config import KAFKA_CONFIG
from llm_service.llm_client import LLMClient


class AutoencoderIDS(torch.nn.Module):
    """Architecture identique au notebook"""
    def __init__(self, input_dim=37, latent_dim=16, hidden_dims=[128, 64, 32], num_classes=7, dropout=0.3):
        super(AutoencoderIDS, self).__init__()
        
        # ENCODER
        encoder_layers = []
        prev_dim = input_dim
        for h in hidden_dims:
            encoder_layers.extend([
                torch.nn.Linear(prev_dim, h),
                torch.nn.BatchNorm1d(h),
                torch.nn.LeakyReLU(0.2),
                torch.nn.Dropout(dropout)
            ])
            prev_dim = h
        encoder_layers.append(torch.nn.Linear(prev_dim, latent_dim))
        self.encoder = torch.nn.Sequential(*encoder_layers)
        
        # DECODER
        decoder_layers = []
        prev_dim = latent_dim
        for h in reversed(hidden_dims):
            decoder_layers.extend([
                torch.nn.Linear(prev_dim, h),
                torch.nn.BatchNorm1d(h),
                torch.nn.LeakyReLU(0.2),
                torch.nn.Dropout(dropout * 0.5)
            ])
            prev_dim = h
        decoder_layers.append(torch.nn.Linear(prev_dim, input_dim))
        self.decoder = torch.nn.Sequential(*decoder_layers)
        
        # CLASSIFIER (architecture identique à detector.py)
        self.classifier = torch.nn.Sequential(
            torch.nn.Linear(latent_dim + 1, 64),
            torch.nn.BatchNorm1d(64),
            torch.nn.ReLU(),
            torch.nn.Dropout(dropout),
            torch.nn.Linear(64, 32),
            torch.nn.BatchNorm1d(32),
            torch.nn.ReLU(),
            torch.nn.Dropout(dropout * 0.5),
            torch.nn.Linear(32, num_classes)
        )
    
    def forward(self, x):
        # Encodage
        latent = self.encoder(x)
        
        # Reconstruction
        reconstructed = self.decoder(latent)
        
        # Erreur de reconstruction
        recon_error = torch.mean((x - reconstructed) ** 2, dim=1, keepdim=True)
        
        # Classification
        classifier_input = torch.cat([latent, recon_error], dim=1)
        logits = self.classifier(classifier_input)
        
        return logits, reconstructed, recon_error


class DatasetPredictor:
    """Lit le dataset, prédit avec le modèle, publie dans Kafka"""
    
    def __init__(self, dataset_path, model_dir='../../models/artifacts', interval=2.0):
        """
        Args:
            dataset_path: Chemin vers le fichier CSV CICIDS2017
            model_dir: Dossier contenant le modèle et les artefacts
            interval: Intervalle en secondes entre chaque prédiction
        """
        self.dataset_path = dataset_path
        self.model_dir = Path(model_dir)
        self.interval = interval
        self.device = torch.device('cpu')
        
        print(f"📂 Chargement des artefacts depuis {self.model_dir}...")
        
        # Charger les artefacts
        self.scaler = joblib.load(self.model_dir / 'scaler.joblib')
        self.label_encoder = joblib.load(self.model_dir / 'label_encoder.joblib')
        self.percentiles = joblib.load(self.model_dir / 'percentiles.joblib')
        
        with open(self.model_dir / 'feature_names.json', 'r') as f:
            self.feature_names = json.load(f)
        
        with open(self.model_dir / 'model_config.json', 'r') as f:
            self.model_config = json.load(f)
        
        print(f"✅ Features: {len(self.feature_names)}")
        print(f"✅ Classes: {list(self.label_encoder.classes_)}")
        
        # Charger le modèle
        print(f"🧠 Chargement du modèle...")
        self.model = AutoencoderIDS(
            input_dim=self.model_config['input_dim'],
            latent_dim=self.model_config['latent_dim'],
            hidden_dims=self.model_config['hidden_dims'],
            num_classes=self.model_config['num_classes'],
            dropout=self.model_config.get('dropout', 0.3)
        )
        
        checkpoint = torch.load(
            self.model_dir / 'autoencoder_ids_v1.1.0.pt',
            map_location=self.device
        )
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.model.eval()
        print(f"✅ Modèle chargé (version {self.model_config.get('model_version', 'N/A')})")
        
        # Kafka Producer
        self.producer = KafkaProducer(
            bootstrap_servers=KAFKA_CONFIG['bootstrap_servers'],
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        print(f"✅ Kafka connecté: {KAFKA_CONFIG['bootstrap_servers']}")
        
        # Charger le dataset
        print(f"📊 Chargement du dataset: {dataset_path}")
        self.df = pd.read_csv(dataset_path)
        print(f"✅ Dataset chargé: {len(self.df)} lignes")
        
        # Statistiques
        self.stats = {
            'total_sent': 0,
            'attacks_sent': 0,
            'normal_sent': 0,
            'start_time': None
        }
    
    def preprocess_row(self, row):
        """Prétraitement identique au notebook"""
        # Créer DataFrame avec une seule ligne
        df = pd.DataFrame([row])
        
        # S'assurer que toutes les features sont présentes
        for col in self.feature_names:
            if col not in df.columns:
                df[col] = 0.0
        
        # Sélectionner les features
        X = df[self.feature_names].copy()
        
        # Nettoyage (comme dans le notebook)
        X = X.replace([np.inf, -np.inf], np.nan)
        X = X.fillna(0.0)
        
        # Clipping avec percentiles
        X_clipped = np.clip(X.values, self.percentiles['p01'], self.percentiles['p99'])
        
        # Normalisation
        X_scaled = self.scaler.transform(X_clipped)
        
        return X_scaled
    
    def predict(self, X_scaled):
        """Prédiction avec le modèle"""
        X_tensor = torch.tensor(X_scaled, dtype=torch.float32)
        
        with torch.no_grad():
            logits, reconstructed, recon_error = self.model(X_tensor)
            probs = torch.softmax(logits, dim=1)
            confidence, pred_idx = torch.max(probs, dim=1)
        
        # Convertir en classes lisibles
        predicted_class = self.label_encoder.inverse_transform([pred_idx.item()])[0]
        class_probs = {
            self.label_encoder.classes_[i]: float(probs[0][i])
            for i in range(len(self.label_encoder.classes_))
        }
        
        # Anomaly score
        anomaly_score = float(recon_error[0][0])
        
        # Top features (différence entre original et reconstruit)
        original = X_tensor[0].numpy()
        reconstructed_np = reconstructed[0].numpy()
        feature_errors = np.abs(original - reconstructed_np)
        top_indices = np.argsort(feature_errors)[-5:][::-1]
        
        top_features = [
            {
                'name': self.feature_names[idx],
                'feature': self.feature_names[idx],  # pour compat dashboard
                'value': float(original[idx]),
                'error': float(feature_errors[idx]),
                'importance': float(feature_errors[idx])
            }
            for idx in top_indices
        ]
        
        return {
            'predicted_class': predicted_class,
            'confidence': float(confidence),
            'anomaly_score': anomaly_score,
            'reconstruction_error': anomaly_score,
            'class_probabilities': class_probs,
            'top_features': top_features
        }
    
    def create_alert(self, row, prediction, flow_id):
        """Créer l'alerte au format attendu par Phase3"""
        # Déterminer si c'est une attaque
        is_attack = prediction['predicted_class'] != 'Normal Traffic'
        is_anomaly = prediction['anomaly_score'] > self.model_config.get('anomaly_threshold', 0.5)
        
        alert = {
            'flow_id': flow_id,
            'timestamp': datetime.now().isoformat(),
            'predicted_class': prediction['predicted_class'],
            'confidence': prediction['confidence'],
            'anomaly_score': prediction['anomaly_score'],
            'reconstruction_error': prediction['reconstruction_error'],
            'is_attack': is_attack,
            'is_anomaly': is_anomaly,
            'class_probabilities': prediction['class_probabilities'],
            'top_features': prediction['top_features'],
            'model_version': self.model_config.get('model_version', '1.1.0'),
            'source': 'dataset_streaming'
        }
        
        return alert
    
    def stream_dataset(self, max_rows=None, only_attacks=False):
        """
        Stream le dataset ligne par ligne avec prédictions
        
        Args:
            max_rows: Nombre max de lignes à traiter (None = tout)
            only_attacks: Si True, n'envoie que les attaques détectées
        """
        print(f"\n🚀 Démarrage du streaming...")
        print(f"   Intervalle: {self.interval}s par ligne")
        print(f"   Topic Kafka: {KAFKA_CONFIG['topics']['alerts']}")
        if only_attacks:
            print(f"   ⚠️  Mode: Attaques uniquement")
        print()
        
        self.stats['start_time'] = time.time()
        rows_to_process = min(len(self.df), max_rows) if max_rows else len(self.df)
        
        try:
            for idx, row in self.df.iterrows():
                if max_rows and idx >= max_rows:
                    break
                
                # Prétraitement
                X_scaled = self.preprocess_row(row)
                
                # Prédiction
                prediction = self.predict(X_scaled)
                
                # Créer l'alerte
                flow_id = f'flow_{int(time.time())}_{idx}'
                alert = self.create_alert(row, prediction, flow_id)
                
                # Filtrer si only_attacks
                if only_attacks and not alert['is_attack']:
                    continue
                
                # Publier dans Kafka
                self.producer.send(
                    KAFKA_CONFIG['topics']['alerts'],
                    alert
                )
                self.producer.flush()
                
                # Stats
                self.stats['total_sent'] += 1
                if alert['is_attack']:
                    self.stats['attacks_sent'] += 1
                else:
                    self.stats['normal_sent'] += 1
                
                # Affichage
                attack_emoji = "🚨" if alert['is_attack'] else "✅"
                print(f"{attack_emoji} [{self.stats['total_sent']:04d}/{rows_to_process}] "
                      f"{alert['predicted_class']:20s} "
                      f"(conf: {alert['confidence']:.2f}, "
                      f"anomaly: {alert['anomaly_score']:.3f})")
                
                # Attendre avant la prochaine ligne
                time.sleep(self.interval)
        
        except KeyboardInterrupt:
            print(f"\n⏹️  Arrêt demandé par l'utilisateur")
        finally:
            self.print_stats()
            self.producer.close()
    
    def print_stats(self):
        """Afficher les statistiques"""
        if self.stats['start_time']:
            duration = time.time() - self.stats['start_time']
            print(f"\n" + "="*60)
            print(f"📊 STATISTIQUES")
            print(f"="*60)
            print(f"Total envoyé:     {self.stats['total_sent']}")
            print(f"Attaques:         {self.stats['attacks_sent']} "
                  f"({100*self.stats['attacks_sent']/max(self.stats['total_sent'],1):.1f}%)")
            print(f"Trafic normal:    {self.stats['normal_sent']} "
                  f"({100*self.stats['normal_sent']/max(self.stats['total_sent'],1):.1f}%)")
            print(f"Durée:            {duration:.1f}s")
            print(f"Débit:            {self.stats['total_sent']/max(duration,1):.2f} alertes/s")
            print(f"="*60)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Stream CICIDS2017 dataset avec prédictions vers Kafka')
    parser.add_argument('dataset_path', help='Chemin vers le fichier CSV CICIDS2017')
    parser.add_argument('--interval', type=float, default=2.0, 
                       help='Intervalle en secondes entre chaque ligne (défaut: 2.0)')
    parser.add_argument('--max-rows', type=int, default=None,
                       help='Nombre max de lignes à traiter (défaut: tout)')
    parser.add_argument('--only-attacks', action='store_true',
                       help='N\'envoyer que les attaques détectées')
    parser.add_argument('--model-dir', default='../../models/artifacts',
                       help='Dossier contenant le modèle et artefacts')
    
    args = parser.parse_args()
    
    # Vérifier que le fichier existe
    if not os.path.exists(args.dataset_path):
        print(f"❌ Erreur: Fichier non trouvé: {args.dataset_path}")
        return
    
    # Créer le predictor et streamer
    predictor = DatasetPredictor(
        dataset_path=args.dataset_path,
        model_dir=args.model_dir,
        interval=args.interval
    )
    
    # Démarrer le streaming
    predictor.stream_dataset(
        max_rows=args.max_rows,
        only_attacks=args.only_attacks
    )


if __name__ == '__main__':
    main()
