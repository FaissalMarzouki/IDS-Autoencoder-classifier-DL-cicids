import joblib
import json
import pandas as pd
import numpy as np
from .base import KafkaProcessor
from config import ARTIFACTS_PATH

class DataPreprocessor(KafkaProcessor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scaler = joblib.load(f"{ARTIFACTS_PATH}scaler.joblib")
        self.percentiles = joblib.load(f"{ARTIFACTS_PATH}percentiles.joblib")
        with open(f"{ARTIFACTS_PATH}feature_names.json", "r") as f:
            self.feature_names = json.load(f)

    def process(self, data):
        # 1. Création d'un dictionnaire "propre" (on enlève les espaces des clés reçues)
        # On ne garde que les clés utiles pour le modèle
        clean_data = {}
        # On crée un mapping insensible aux espaces pour les données reçues
        input_map = {k.strip(): v for k, v in data.items() if isinstance(k, str)}

        # 2. Construction du vecteur selon l'ordre strict de feature_names
        final_values = []
        for col in self.feature_names:
            col_clean = col.strip()
            # On cherche la valeur, sinon 0.0
            val = input_map.get(col_clean, 0.0)
            final_values.append(val)

        # 3. Transformation en array Numpy pour éviter les UserWarnings de Scikit-Learn
        X = np.array(final_values).reshape(1, -1)
        
        # Remplacement des infinis/NaN par précaution
        X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

        # A. Clipping d'abord (utiliser les percentiles chargés dans l'init)
        X = np.clip(X, self.percentiles['p01'], self.percentiles['p99'])

        # 4. Normalisation
        df_scaled = self.scaler.transform(X)
        
        output = {
            "flow_id": data.get("flow_id", "unknown"),
            "features": df_scaled.tolist()[0],
            "metadata": {k: v for k, v in data.items() if k not in self.feature_names}
        }
        self.send_message(output)
