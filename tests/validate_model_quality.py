"""
Test de validation de la qualité du modèle
Vérifie que le modèle peut distinguer les classes
"""
import numpy as np
import torch
import joblib
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import ARTIFACTS_PATH
from processors.detector import IDSDetector

def test_model_quality():
    """Teste si le modèle peut distinguer les classes"""
    print("="*80)
    print("🔬 TEST DE QUALITÉ DU MODÈLE")
    print("="*80)
    
    detector = IDSDetector(input_topic="test", output_topic="test")
    
    # Charger les classes
    classes = detector.label_encoder.classes_
    print(f"\n📊 Classes du modèle ({len(classes)}):")
    for i, cls in enumerate(classes):
        print(f"   {i}: {cls}")
    
    # Test: créer des données aléatoires et voir la distribution
    print(f"\n" + "="*80)
    print("TEST 1: Distribution avec données aléatoires")
    print("="*80)
    
    # Créer 100 samples aléatoires
    predictions = {cls: 0 for cls in classes}
    
    for i in range(100):
        # Données aléatoires normalisées (mean=0, std=1)
        random_features = np.random.randn(1, 37)
        
        with torch.no_grad():
            tensor = torch.tensor(random_features, dtype=torch.float32)
            logits = detector.model(tensor)
            probs = torch.softmax(logits, dim=1)
            conf, pred_idx = torch.max(probs, dim=1)
        
        pred_class = detector.label_encoder.inverse_transform([pred_idx.item()])[0]
        predictions[pred_class] += 1
    
    print(f"\n📈 Prédictions sur 100 samples aléatoires:")
    for cls in classes:
        print(f"   {cls:20s}: {predictions[cls]:3d} ({predictions[cls]/100*100:5.1f}%)")
    
    # Test 2: Vérifier que le modèle n'est pas gelé
    print(f"\n" + "="*80)
    print("TEST 2: Vérification des poids du modèle")
    print("="*80)
    
    total_params = sum(p.numel() for p in detector.model.parameters())
    trainable_params = sum(p.numel() for p in detector.model.parameters() if p.requires_grad)
    
    print(f"\n📦 Nombre de paramètres:")
    print(f"   Total: {total_params:,}")
    print(f"   Entraînables: {trainable_params:,}")
    
    # Afficher les min/max de quelques poids
    for name, param in list(detector.model.named_parameters())[:3]:
        print(f"\n   {name}:")
        print(f"     Min: {param.data.min():.6f}, Max: {param.data.max():.6f}")
    
    # Test 3: Vérifier la capacité discriminante du classifier
    print(f"\n" + "="*80)
    print("TEST 3: Énergie du classifier (poids finaux)")
    print("="*80)
    
    # Afficher les poids du dernier layer (classification)
    classifier = detector.model.classifier
    last_layer = list(classifier.modules())[-1]
    
    if hasattr(last_layer, 'weight'):
        weights = last_layer.weight.data
        print(f"\nPoids du classifier ({weights.shape}):")
        print(f"   Min: {weights.min():.4f}, Max: {weights.max():.4f}")
        
        # Vérifier qu'il y a de la variation entre classes
        weight_variance = weights.var(dim=0).mean()
        print(f"   Variance moyenne par neurone: {weight_variance:.6f}")
        
        if weight_variance < 0.001:
            print(f"   ALERTE: Variance très faible - le modèle peut être dégénéré!")

if __name__ == "__main__":
    test_model_quality()
