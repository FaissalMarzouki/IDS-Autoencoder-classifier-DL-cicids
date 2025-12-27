"""
Traffic Simulator Module
Simule du trafic reseau a partir du dataset CICIDS2017
"""

import pandas as pd
import numpy as np
import json
from typing import List, Dict, Optional, Generator
from dataclasses import dataclass


@dataclass
class NetworkFlow:
    """Represente un flux reseau"""
    flow_id: str
    features: np.ndarray
    label: str
    timestamp: float
    
    def to_dict(self) -> Dict:
        return {
            'flow_id': self.flow_id,
            'features': self.features.tolist(),
            'label': self.label,
            'timestamp': self.timestamp
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict())


class TrafficSimulator:
    """Simule du trafic reseau depuis le dataset CICIDS2017"""
    
    def __init__(self, dataset_path: str):
        """
        Args:
            dataset_path: Chemin vers cicids2017_cleaned.csv
        """
        self.df = pd.read_csv(dataset_path)
        
        # Features du modele (37 features)
        self.feature_columns = [
            "Destination Port", "Flow Duration", "Total Fwd Packets",
            "Total Length of Fwd Packets", "Fwd Packet Length Max",
            "Fwd Packet Length Min", "Fwd Packet Length Mean",
            "Bwd Packet Length Max", "Bwd Packet Length Min",
            "Flow Bytes/s", "Flow Packets/s", "Flow IAT Mean",
            "Flow IAT Std", "Flow IAT Max", "Flow IAT Min",
            "Fwd IAT Mean", "Fwd IAT Std", "Fwd IAT Min",
            "Bwd IAT Total", "Bwd IAT Mean", "Bwd IAT Std",
            "Bwd IAT Max", "Bwd IAT Min", "Bwd Packets/s",
            "Min Packet Length", "Max Packet Length", "Packet Length Mean",
            "Packet Length Variance", "FIN Flag Count", "PSH Flag Count",
            "ACK Flag Count", "Init_Win_bytes_forward", "Init_Win_bytes_backward",
            "min_seg_size_forward", "Active Mean", "Active Max", "Active Min"
        ]
        
        # Verifier que toutes les features existent
        available = [c for c in self.feature_columns if c in self.df.columns]
        self.feature_columns = available
        
        # Detecter la colonne label (peut etre 'Label' ou 'Attack Type')
        if 'Label' in self.df.columns:
            self.label_column = 'Label'
        elif 'Attack Type' in self.df.columns:
            self.label_column = 'Attack Type'
        else:
            raise ValueError("Colonne label non trouvee (Label ou Attack Type)")
        
        self._flow_counter = 0
        
        # Index par type d'attaque
        self.attack_types = self.df[self.label_column].unique().tolist()
        self.indices_by_type = {
            attack: self.df[self.df[self.label_column] == attack].index.tolist()
            for attack in self.attack_types
        }
    
    def get_random_flow(self, attack_type: Optional[str] = None) -> NetworkFlow:
        """
        Retourne un flux aleatoire du dataset
        
        Args:
            attack_type: Type d'attaque specifique ou None pour aleatoire
        """
        if attack_type and attack_type in self.indices_by_type:
            idx = np.random.choice(self.indices_by_type[attack_type])
        else:
            idx = np.random.randint(0, len(self.df))
        
        row = self.df.iloc[idx]
        self._flow_counter += 1
        
        return NetworkFlow(
            flow_id=f"sim_{self._flow_counter:08d}",
            features=row[self.feature_columns].values.astype(np.float32),
            label=row[self.label_column],
            timestamp=float(self._flow_counter)
        )
    
    def generate_stream(
        self, 
        count: int = 100, 
        attack_ratio: float = 0.3,
        attack_types: Optional[List[str]] = None
    ) -> Generator[NetworkFlow, None, None]:
        """
        Genere un stream de flux reseau
        
        Args:
            count: Nombre de flux a generer
            attack_ratio: Proportion d'attaques (0.0 a 1.0)
            attack_types: Types d'attaques a inclure
        """
        if attack_types is None:
            attack_types = [t for t in self.attack_types if t != 'Normal Traffic']
        
        for i in range(count):
            if np.random.random() < attack_ratio and attack_types:
                attack_type = np.random.choice(attack_types)
            else:
                attack_type = 'Normal Traffic'
            
            yield self.get_random_flow(attack_type)
    
    def get_attack_types(self) -> List[str]:
        """Retourne la liste des types d'attaques disponibles"""
        return self.attack_types
    
    def get_class_distribution(self) -> Dict[str, int]:
        """Retourne la distribution des classes"""
        return self.df[self.label_column].value_counts().to_dict()
