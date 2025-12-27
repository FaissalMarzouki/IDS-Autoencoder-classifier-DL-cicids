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
        """Génère les données d'entrée brutes avec signatures distinctives des attaques"""
        expected = self.preprocessor.feature_names
        data = {"flow_id": f"flow_{scenario}_{np.random.randint(100)}"}
        
        # Initialiser avec valeurs moyennes réalistes
        for f in expected: 
            data[f] = 50.0

        if scenario == "ddos":
            # ☠️ DDoS: Beaucoup de DONNÉES transmises (très gros paquets)
            data["Destination Port"] = 80
            data["Total Fwd Packets"] = 100000.0  
            data["Total Bwd Packets"] = 1000.0
            data["Total Length of Fwd Packets"] = 50000000.0  # 50MB!
            data["Total Length of Bwd Packets"] = 100000.0
            data["Flow Duration"] = 5.0  
            data["Flow Bytes/s"] = 10000000.0  # 10MB/s!
            data["Flow Packets/s"] = 20000.0
            data["Fwd Packet Length Mean"] = 500.0  # Gros paquets
            data["Fwd Packet Length Max"] = 1500.0
            data["Bwd Packet Length Mean"] = 100.0
            data["ACK Flag Count"] = 50000.0
            data["PSH Flag Count"] = 50000.0  # Beaucoup de PUSH = données
            data["FIN Flag Count"] = 50.0
            data["SYN Flag Count"] = 100.0
            
        elif scenario == "dos":
            # 🔥 DoS: SYN Flood - beaucoup de paquets de CONTRÔLE (petits)
            data["Destination Port"] = 80
            data["Total Fwd Packets"] = 50000.0  # Moins de paquets que DDoS
            data["Total Bwd Packets"] = 100.0
            data["Total Length of Fwd Packets"] = 2000000.0  # Beaucoup moins de données
            data["Total Length of Bwd Packets"] = 4000.0
            data["Flow Duration"] = 10.0
            data["Flow Bytes/s"] = 200000.0  # Moins de débit
            data["Flow Packets/s"] = 5000.0
            data["Fwd Packet Length Mean"] = 40.0  # Très petits paquets (SYN)
            data["Fwd Packet Length Max"] = 60.0
            data["Bwd Packet Length Mean"] = 40.0
            data["SYN Flag Count"] = 25000.0  # 50% des paquets sont SYN
            data["ACK Flag Count"] = 25000.0  # L'autre 50% ACK
            data["PSH Flag Count"] = 100.0  # Peu de données
            data["FIN Flag Count"] = 50.0
            
        elif scenario == "portscan":
            # 🔍 Port Scan: TRÈS courts, SYN uniquement, pas de réponse
            data["Destination Port"] = 22
            data["Total Fwd Packets"] = 1.0
            data["Total Bwd Packets"] = 0.0
            data["Total Length of Fwd Packets"] = 40.0
            data["Total Length of Bwd Packets"] = 0.0
            data["Flow Duration"] = 0.01  # Extrêmement court
            data["Flow Bytes/s"] = 4000.0
            data["Flow Packets/s"] = 100.0
            data["Fwd Packet Length Mean"] = 40.0
            data["Fwd Packet Length Max"] = 40.0
            data["Fwd Packet Length Min"] = 40.0
            data["SYN Flag Count"] = 1.0  # 100% SYN
            data["ACK Flag Count"] = 0.0
            data["PSH Flag Count"] = 0.0
            data["FIN Flag Count"] = 0.0
            data["Bwd Packet Length Mean"] = 0.0
            data["Bwd Packet Length Max"] = 0.0
            data["Bwd IAT Mean"] = 0.0
            data["Bwd Packets/s"] = 0.0
            
        else:  # "normal" traffic
            # ✅ Trafic normal: équilibré et modéré
            data["Destination Port"] = 443
            data["Total Fwd Packets"] = 30.0
            data["Total Bwd Packets"] = 25.0
            data["Total Length of Fwd Packets"] = 6000.0
            data["Total Length of Bwd Packets"] = 5000.0
            data["Flow Duration"] = 60000.0  
            data["Flow Bytes/s"] = 200.0  
            data["Flow Packets/s"] = 1.0  
            data["Fwd Packet Length Mean"] = 200.0
            data["Bwd Packet Length Mean"] = 200.0
            data["Fwd Packet Length Max"] = 1500.0
            data["Fwd Packet Length Min"] = 20.0
            data["ACK Flag Count"] = 25.0
            data["PSH Flag Count"] = 15.0
            data["FIN Flag Count"] = 1.0
            data["SYN Flag Count"] = 1.0
            data["Bwd Packet Length Max"] = 1500.0

        return data

    def run(self):
        scenarios = ["normal", "ddos", "dos", "portscan"]
        
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

# Modifie le process du Detector pour debug complet
def verbose_detector_process(self, data):
    """Process avec affichage détaillé du pipeline"""
    # 1. Features du préprocesseur
    feat_array = np.array(data['features']).reshape(1, -1)
    
    # 2. Note: le clipping a déjà été fait dans le preprocessor!
    # Le detector ne fait que scaler des données déjà clippées
    
    # 3. Transform par le scaler (déjà fitted)
    feat_scaled = self.scaler.transform(feat_array)
    
    # 4. Inférence
    features_tensor = torch.tensor(feat_scaled, dtype=torch.float32)
    with torch.no_grad():
        logits = self.model(features_tensor)
        probs = torch.softmax(logits, dim=1)
        conf, pred_idx = torch.max(probs, dim=1)
    
    prediction = self.label_encoder.inverse_transform([pred_idx.item()])[0]
    
    # Affichage du résultat interne
    print(f"  📥 INPUT  (Tensor): {features_tensor.shape}")
    print(f"  🔄 Features (scaled, first 5): {feat_scaled[0, :5]}")
    print(f"  📤 OUTPUT (Pred): {prediction}")
    print(f"  📊 CONFIDENCE: {conf.item():.2%}")
    
    # Afficher la distribution des probabilités
    class_names = ['Bots', 'Brute Force', 'DDoS', 'DoS', 'Normal Traffic', 'Port Scanning', 'Web Attacks']
    top_3_idx = torch.topk(probs, 3, dim=1)[1][0].cpu().numpy()
    print(f"  📊 Top 3 prédictions:")
    for i, idx in enumerate(top_3_idx):
        print(f"     {i+1}. {class_names[idx]}: {probs[0, idx].item():.2%}")
    
    if prediction != "Normal Traffic":
        print(f"  🚨 ALERT GENERATED: {prediction}")

# Injection de la méthode verbeuse
IDSDetector.process = verbose_detector_process

if __name__ == "__main__":
    tester = FullFlowTest()
    tester.run()
