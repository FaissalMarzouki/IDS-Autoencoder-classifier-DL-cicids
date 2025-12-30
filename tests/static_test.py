import sys
import os
import json
import torch

# Ajouter le chemin racine pour l'import des modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from processors.preprocessor import DataPreprocessor
from processors.detector import IDSDetector

def run_static_test():
    print("🧪 DÉBUT DU TEST STATIQUE DU PIPELINE")
    
    # 1. Mock de donnée brute (Exemple d'attaque Bot/DDoS simplifiée)
    raw_data = {
        "flow_id": "test-flow-101",
        "Destination Port": 80,
        "Flow Duration": 500,
        "Total Fwd Packets": 20,
        "Total Length of Fwd Packets": 4500,
        "Fwd Packet Length Max": 1000,
        "src_ip": "192.168.1.50",
        "dst_ip": "10.0.0.1"
    }
    
    # 2. Initialisation des composants (en mode test, sans Kafka)
    # On surcharge les classes pour intercepter les messages au lieu de les envoyer à Kafka
    class TestPreprocessor(DataPreprocessor):
        def __init__(self): super().__init__("raw", "features")
        def send_message(self, data): self.last_output = data

    class TestDetector(IDSDetector):
        def __init__(self): super().__init__("features", "alerts")
        def send_message(self, data): self.last_output = data

    preproc = TestPreprocessor()
    detector = TestDetector()

    # 3. Exécution du flux
    print("[1/2] Test du Preprocessor...")
    preproc.process(raw_data)
    features_output = preproc.last_output
    print(f"✅ Features générées (Taille: {len(features_output['features'])})")

    print("[2/2] Test du Detector...")
    detector.process(features_output)
    
    if hasattr(detector, 'last_output'):
        alert = detector.last_output
        print(f" ALERTE DÉTECTÉE : {alert['prediction']} (Confiance: {alert['confidence']:.2%})")
    else:
        print(" Aucune menace détectée pour ce flux (Trafic Normal).")

    print("\n TEST TERMINÉ AVEC SUCCÈS")

if __name__ == "__main__":
    run_static_test()
