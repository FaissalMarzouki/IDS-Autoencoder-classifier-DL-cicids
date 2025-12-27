import numpy as np
import torch
import json
import joblib
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from processors.preprocessor import DataPreprocessor
from processors.detector import IDSDetector
from config import ARTIFACTS_PATH

def debug_inference():
    """Debug l'inférence du modèle avec des features synthétiques"""
    print("=" * 80)
    print("🔍 DEBUG MODE - Analyse du Pipeline")
    print("=" * 80)
    
    # Initialiser
    preprocessor = DataPreprocessor(input_topic="debug_in", output_topic="debug_out")
    detector = IDSDetector(input_topic="debug_in", output_topic="debug_out")
    
    # Charger les percentiles
    percentiles = joblib.load(f"{ARTIFACTS_PATH}percentiles.joblib")
    print(f"\n📊 Percentiles chargés:")
    print(f"   p01: {percentiles.get('p01', 'N/A')}")
    print(f"   p99: {percentiles.get('p99', 'N/A')}")
    
    # Afficher les statistiques du scaler
    print(f"\n🔧 Statistiques du Scaler:")
    print(f"   Mean (sample): {detector.scaler.mean_[:5]}")
    print(f"   Scale: {detector.scaler.scale_[:5]}")
    
    # Test 1: Données normales
    print(f"\n" + "=" * 80)
    print("TEST 1: Trafic NORMAL")
    print("=" * 80)
    
    normal_data = {}
    for col in preprocessor.feature_names:
        normal_data[col] = 100.0  # Valeur neutre
    
    normal_data["Destination Port"] = 443
    normal_data["Total Fwd Packets"] = 20.0
    normal_data["Flow Duration"] = 50000.0
    
    print(f"\nInput (5 features): {list(normal_data.items())[:5]}")
    
    preprocessed = None
    def capture_normal(data):
        global preprocessed
        preprocessed = data
    preprocessor.send_message = capture_normal
    preprocessor.process(normal_data)
    
    if preprocessed:
        features = np.array(preprocessed['features']).reshape(1, -1)
        print(f"Features shape: {features.shape}")
        print(f"Features (5 first): {features[0, :5]}")
        print(f"Features min/max: {features.min():.4f} / {features.max():.4f}")
        
        # Inférence
        with torch.no_grad():
            tensor = torch.tensor(features, dtype=torch.float32)
            logits = detector.model(tensor)
            probs = torch.softmax(logits, dim=1)
            conf, pred_idx = torch.max(probs, dim=1)
        
        pred_class = detector.label_encoder.inverse_transform([pred_idx.item()])[0]
        print(f"\n🎯 Prédiction: {pred_class} (confidence: {conf.item():.2%})")
        print(f"   Toutes les probas: {probs[0].cpu().numpy()}")
    
    # Test 2: Données DDoS extrêmes
    print(f"\n" + "=" * 80)
    print("TEST 2: Attaque DDoS EXTRÊME")
    print("=" * 80)
    
    ddos_data = {}
    for col in preprocessor.feature_names:
        ddos_data[col] = 100.0  # Base
    
    # Caractéristiques DDoS: TRÈS ÉLEVÉES
    ddos_data["Total Fwd Packets"] = 100000.0
    ddos_data["Total Length of Fwd Packets"] = 50000000.0
    ddos_data["Flow Duration"] = 5.0
    ddos_data["Flow Bytes/s"] = 10000000.0
    ddos_data["Flow Packets/s"] = 20000.0
    
    print(f"\nInput DDoS extremes:")
    print(f"   Total Fwd Packets: {ddos_data['Total Fwd Packets']}")
    print(f"   Flow Bytes/s: {ddos_data['Flow Bytes/s']}")
    
    preprocessor.send_message = capture_normal
    preprocessor.process(ddos_data)
    
    if preprocessed:
        features = np.array(preprocessed['features']).reshape(1, -1)
        print(f"\nFeatures shape: {features.shape}")
        print(f"Features (5 first): {features[0, :5]}")
        print(f"Features min/max: {features.min():.4f} / {features.max():.4f}")
        
        # Inférence
        with torch.no_grad():
            tensor = torch.tensor(features, dtype=torch.float32)
            logits = detector.model(tensor)
            probs = torch.softmax(logits, dim=1)
            conf, pred_idx = torch.max(probs, dim=1)
        
        pred_class = detector.label_encoder.inverse_transform([pred_idx.item()])[0]
        print(f"\n🎯 Prédiction: {pred_class} (confidence: {conf.item():.2%})")
        print(f"   Toutes les probas: {probs[0].cpu().numpy()}")
    
    # Test 3: Analyse de l'espace latent
    print(f"\n" + "=" * 80)
    print("TEST 3: Analyse Espace Latent")
    print("=" * 80)
    
    with torch.no_grad():
        tensor = torch.tensor(features, dtype=torch.float32)
        latent = detector.model.encoder(tensor)
        reconstructed = detector.model.decoder(latent)
        recon_error = torch.mean((tensor - reconstructed)**2, dim=1, keepdim=True)
    
    print(f"\nLatent shape: {latent.shape}")
    print(f"Latent values: {latent[0].cpu().numpy()[:8]}")
    print(f"Reconstruction error: {recon_error.item():.6f}")
    
    print(f"\n✅ Debug terminé!")

if __name__ == "__main__":
    debug_inference()
