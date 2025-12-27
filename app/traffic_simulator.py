# ============================================================================
# TRAFFIC_SIMULATOR.PY - Simulateur de trafic réseau depuis le dataset
# ============================================================================
"""
Module de simulation de trafic réseau pour tester l'IDS.
Lit le dataset CICIDS2017 et génère des flux pour la simulation.
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import List, Dict, Optional, Generator, Tuple
import random
import json


@dataclass
class SimulatedFlow:
    """Un flux réseau simulé."""
    flow_id: str
    features: np.ndarray
    label: str
    original_index: int
    
    def to_dict(self) -> dict:
        return {
            "flow_id": self.flow_id,
            "features": self.features.tolist(),
            "label": self.label,
            "original_index": self.original_index
        }


class TrafficSimulator:
    """
    Simulateur de trafic réseau basé sur le dataset CICIDS2017.
    
    Usage:
        simulator = TrafficSimulator('./dataset/cicids2017_cleaned.csv')
        
        # Obtenir un flux aléatoire
        flow = simulator.get_random_flow()
        
        # Obtenir un flux d'un type spécifique
        flow = simulator.get_random_flow(attack_type='DDoS')
        
        # Générer un batch
        batch = simulator.generate_batch(100)
        
        # Stream continu
        for flow in simulator.stream_flows(rate=10):
            process(flow)
    """
    
    def __init__(
        self, 
        dataset_path: str, 
        feature_columns: Optional[List[str]] = None,
        feature_names_path: Optional[str] = None
    ):
        """
        Initialise le simulateur.
        
        Args:
            dataset_path: Chemin vers le fichier CSV du dataset
            feature_columns: Liste des colonnes à utiliser comme features
            feature_names_path: Chemin vers le fichier JSON des noms de features du modèle
        """
        print(f"📂 Chargement du dataset: {dataset_path}")
        self.df = pd.read_csv(dataset_path)
        print(f"   • Lignes: {len(self.df):,}")
        print(f"   • Colonnes: {len(self.df.columns)}")
        
        # Identifier la colonne de label
        self.label_col = self._find_label_column()
        print(f"   • Colonne label: {self.label_col}")
        
        # Identifier les colonnes de features
        if feature_columns:
            self.feature_columns = feature_columns
        elif feature_names_path:
            # Charger les noms de features depuis le fichier JSON du modèle
            import json
            with open(feature_names_path, 'r') as f:
                self.feature_columns = json.load(f)
        else:
            # Essayer de charger depuis le chemin par défaut
            default_path = "../models/feature_names.json"
            import os
            if os.path.exists(default_path):
                import json
                with open(default_path, 'r') as f:
                    self.feature_columns = json.load(f)
            else:
                self.feature_columns = self._identify_feature_columns()
        
        # Vérifier que toutes les features existent dans le dataset
        missing = [f for f in self.feature_columns if f not in self.df.columns]
        if missing:
            print(f"   ⚠️ Features manquantes dans dataset: {missing}")
            self.feature_columns = [f for f in self.feature_columns if f in self.df.columns]
        
        print(f"   • Features utilisées: {len(self.feature_columns)}")
        
        # Indexer par type d'attaque pour accès rapide
        self._index_by_attack_type()
        
        # Compteur de flux
        self._flow_counter = 0
        
        print(f"✅ Simulateur prêt!")
    
    def _find_label_column(self) -> str:
        """Trouve la colonne contenant les labels."""
        possible_names = ['Label', 'label', 'Attack', 'attack', 'class', 'Class', 
                         'Attack Type', 'attack_type', 'AttackType', 'attack type']
        for name in possible_names:
            if name in self.df.columns:
                return name
        raise ValueError("Colonne de label non trouvée!")
    
    def _identify_feature_columns(self) -> List[str]:
        """Identifie les colonnes de features numériques."""
        # Exclure les colonnes non-features
        exclude = [self.label_col, 'Flow ID', 'Source IP', 'Destination IP', 
                   'Timestamp', 'Source Port', 'Destination Port']
        
        feature_cols = []
        for col in self.df.columns:
            if col not in exclude and self.df[col].dtype in ['float64', 'int64', 'float32', 'int32']:
                feature_cols.append(col)
        
        return feature_cols
    
    def _index_by_attack_type(self):
        """Crée un index des lignes par type d'attaque."""
        self.attack_indices = {}
        self.attack_types = self.df[self.label_col].unique().tolist()
        
        print(f"\n📊 Distribution des classes:")
        for attack_type in self.attack_types:
            indices = self.df[self.df[self.label_col] == attack_type].index.tolist()
            self.attack_indices[attack_type] = indices
            print(f"   • {attack_type}: {len(indices):,}")
    
    def get_random_flow(self, attack_type: Optional[str] = None) -> SimulatedFlow:
        """
        Obtient un flux aléatoire du dataset.
        
        Args:
            attack_type: Type d'attaque spécifique (None = aléatoire)
            
        Returns:
            SimulatedFlow
        """
        if attack_type:
            if attack_type not in self.attack_indices:
                raise ValueError(f"Type d'attaque inconnu: {attack_type}. "
                               f"Disponibles: {list(self.attack_indices.keys())}")
            idx = random.choice(self.attack_indices[attack_type])
        else:
            idx = random.randint(0, len(self.df) - 1)
        
        self._flow_counter += 1
        
        return SimulatedFlow(
            flow_id=f"sim_{self._flow_counter:08d}",
            features=self.df.loc[idx, self.feature_columns].values.astype(np.float32),
            label=self.df.loc[idx, self.label_col],
            original_index=idx
        )
    
    def generate_batch(
        self, 
        size: int, 
        distribution: Optional[Dict[str, float]] = None
    ) -> List[SimulatedFlow]:
        """
        Génère un batch de flux.
        
        Args:
            size: Nombre de flux à générer
            distribution: Distribution des types d'attaque (None = dataset original)
            
        Returns:
            Liste de SimulatedFlow
        """
        flows = []
        
        if distribution:
            # Générer selon la distribution spécifiée
            for attack_type, prob in distribution.items():
                count = int(size * prob)
                for _ in range(count):
                    flows.append(self.get_random_flow(attack_type))
        else:
            # Générer aléatoirement depuis le dataset
            for _ in range(size):
                flows.append(self.get_random_flow())
        
        # Mélanger
        random.shuffle(flows)
        
        return flows[:size]
    
    def stream_flows(
        self, 
        total: Optional[int] = None,
        attack_type: Optional[str] = None
    ) -> Generator[SimulatedFlow, None, None]:
        """
        Génère un stream continu de flux.
        
        Args:
            total: Nombre total de flux (None = infini)
            attack_type: Type d'attaque spécifique (None = mélangé)
            
        Yields:
            SimulatedFlow
        """
        count = 0
        while total is None or count < total:
            yield self.get_random_flow(attack_type)
            count += 1
    
    def get_features_as_array(self, flows: List[SimulatedFlow]) -> Tuple[np.ndarray, List[str]]:
        """
        Convertit une liste de flux en arrays numpy.
        
        Args:
            flows: Liste de SimulatedFlow
            
        Returns:
            (features_array, labels_list)
        """
        features = np.array([f.features for f in flows])
        labels = [f.label for f in flows]
        return features, labels
    
    @property
    def available_attack_types(self) -> List[str]:
        """Retourne la liste des types d'attaque disponibles."""
        return list(self.attack_indices.keys())


# ============================================================================
# TEST STANDALONE
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("TEST DU SIMULATEUR DE TRAFIC")
    print("=" * 60)
    
    try:
        simulator = TrafficSimulator("../dataset/cicids2017_cleaned.csv")
        
        print("\n--- Test: flux aléatoire ---")
        flow = simulator.get_random_flow()
        print(f"   ID: {flow.flow_id}")
        print(f"   Label: {flow.label}")
        print(f"   Features shape: {flow.features.shape}")
        
        print("\n--- Test: flux spécifique (DDoS) ---")
        flow = simulator.get_random_flow("DDoS")
        print(f"   Label: {flow.label}")
        
        print("\n--- Test: batch de 10 flux ---")
        batch = simulator.generate_batch(10)
        labels = [f.label for f in batch]
        print(f"   Labels: {labels}")
        
        print("\n✅ Tests réussis!")
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
