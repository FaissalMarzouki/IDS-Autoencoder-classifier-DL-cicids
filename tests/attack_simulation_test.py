import numpy as np
import torch
import json
import os
import sys

# Configuration du chemin pour importer les modules locaux
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from processors.preprocessor import DataPreprocessor
from processors.detector import IDSDetector

class FullFlowTest:
    def __init__(self):
        print("🛠️  Initialisation du pipeline de test...")
        # Initialisation avec des topics fictifs
        self.preprocessor = DataPreprocessor(input_topic="raw_test", output_topic="feat_test")
        self.detector = IDSDetector(input_topic="feat_test", output_topic="alerts_test")
        
        # Intercepteur pour le passage entre Preprocessor et Detector
        self.preprocessed_output = None
        self.preprocessor.send_message = self._capture_output

    def _capture_output(self, data):
        self.preprocessed_output = data

    def generate_raw_traffic(self, scenario="normal"):
        """Génère les données d'entrée brutes"""
        # On utilise les noms de colonnes exacts attendus par votre scaler
        expected = self.preprocessor.feature_names
        data = {"flow_id": f"flow_{scenario}_{np.random.randint(100)}"}
        
        # Valeurs par défaut
        for f in expected: data[f] = 0.0

        if scenario == "ddos":
            # On force des valeurs qui s'écartent du trafic normal
            data[" Destination Port"] = 80
            data[" Total Fwd Packets"] = 15000.0
            data[" Flow Duration"] = 10.0
            data[" Flow Bytes/s"] = 5000000.0
        elif scenario == "portscan":
            data[" Destination Port"] = 22
            data[" Flow Duration"] = 1.0
            data[" SYN Flag Count"] = 1.0
        else: # normal
            data[" Destination Port"] = 443
            data[" Total Fwd Packets"] = 10.0
            data[" Flow Duration"] = 50000.0

        return data

    def run(self):
        scenarios = ["normal", "ddos", "portscan"]
        
        print(f"\n{'='*80}")
        print(f"🚀 DÉMARRAGE DU TEST DE FLUX COMPLET (DEBUG MODE)")
        print(f"{'='*80}")

        for sc in scenarios:
            print(f"\n\n>>> 🟢 SCÉNARIO : {sc.upper()}")
            
            # --- ÉTAPE 1 : GÉNÉRATION ---
            print(f"\n[Étape 1] Génération des données brutes")
            raw_data = self.generate_raw_traffic(sc)
            # On n'affiche que les colonnes modifiées pour la lisibilité
            relevant_input = {k: v for k, v in raw_data.items() if v != 0 and k != "flow_id"}
            print(f"  📥 INPUT  (Raw): {json.dumps(relevant_input, indent=2)}")

            # --- ÉTAPE 2 : PREPROCESSING ---
            print(f"\n[Étape 2] Preprocessing (Clipping & Scaling)")
            self.preprocessor.process(raw_data)
            
            if self.preprocessed_output:
                # Affichage des 5 premières features scalées pour vérification
                sample_features = self.preprocessed_output['features'][:5]
                print(f"  📥 INPUT  (au Preprocessor): {len(raw_data)} colonnes")
                print(f"  📤 OUTPUT (Scaled): {sample_features}... (Total: {len(self.preprocessed_output['features'])} features)")
            
                # --- ÉTAPE 3 : DETECTION ---
                print(f"\n[Étape 3] Analyse par l'Autoencoder + Classifier")
                self.detector.process(self.preprocessed_output)
            
            # Reset
            self.preprocessed_output = None

# On modifie temporairement le process du Detector pour voir les probabilités
def verbose_detector_process(self, data):
    # 1. Scaling final (clipping interne au detector)
    feat_array = np.array(data['features']).reshape(1, -1)
    feat_clipped = np.clip(feat_array, self.percentiles['p01'], self.percentiles['p99'])
    # On évite le warning en passant .values ou un array sans noms de colonnes
    feat_scaled = self.scaler.transform(feat_clipped)
    
    # 2. Inférence
    features_tensor = torch.tensor(feat_scaled, dtype=torch.float32)
    with torch.no_grad():
        logits = self.model(features_tensor)
        probs = torch.softmax(logits, dim=1)
        conf, pred_idx = torch.max(probs, dim=1)
    
    prediction = self.label_encoder.inverse_transform([pred_idx.item()])[0]
    
    # Affichage du résultat interne
    print(f"  📥 INPUT  (Tensor): {features_tensor.shape}")
    print(f"  📤 OUTPUT (Pred): {prediction}")
    print(f"  📊 CONFIDENCE: {conf.item():.2%}")
    
    if prediction != "Normal Traffic":
        print(f"  🚨 ALERT GENERATED: {prediction}")

# Injection de la méthode verbeuse
IDSDetector.process = verbose_detector_process

if __name__ == "__main__":
    tester = FullFlowTest()
    tester.run()
