# processors/preprocessor.py
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
        with open(f"{ARTIFACTS_PATH}feature_names.json", "r") as f:
            self.feature_names = json.load(f)

    def process(self, data):
        # 1. Créer le DF et s'assurer que toutes les colonnes requises existent
        df = pd.DataFrame([data])
        
        # Ajouter les colonnes manquantes (si le capteur ne les envoie pas toutes)
        for col in self.feature_names:
            if col not in df.columns:
                df[col] = 0.0

        # 2. Nettoyage identique au notebook
        X = df[self.feature_names].copy()
        X = X.replace([np.inf, -np.inf], np.nan)
        X = X.fillna(0.0) # On utilise 0.0 car la médiane n'est pas exportée

        # 3. Normalisation
        df_scaled = self.scaler.transform(X)
        
        output = {
            "flow_id": data.get("flow_id", "unknown"),
            "features": df_scaled.tolist()[0],
            "metadata": {k: v for k, v in data.items() if k not in self.feature_names}
        }
        self.send_message(output)
