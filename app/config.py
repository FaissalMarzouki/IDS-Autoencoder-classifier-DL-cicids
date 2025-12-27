# ============================================================================
# CONFIG.PY - Configuration centralisée pour l'IDS Kafka Pipeline
# ============================================================================
"""
Configuration pour le système IDS avec Kafka.
Modifier ces valeurs selon votre environnement.
"""

from dataclasses import dataclass, field
from typing import List, Dict
import os

@dataclass
class KafkaConfig:
    """Configuration Kafka."""
    bootstrap_servers: str = "localhost:9092"
    
    # Topics
    topic_raw_data: str = "ids-raw-data"
    topic_features: str = "ids-features"
    topic_alerts: str = "ids-alerts"
    topic_explanations: str = "ids-explanations"
    
    # Consumer settings
    consumer_group_id: str = "ids-consumer-group"
    auto_offset_reset: str = "earliest"
    
    # Producer settings
    acks: str = "all"
    retries: int = 3


@dataclass
class ModelConfig:
    """Configuration du modèle IDS."""
    models_dir: str = "../models"
    
    # Fichiers du modèle
    model_file: str = "autoencoder_ids_v1.1.0.pt"
    config_file: str = "model_config.json"
    scaler_file: str = "scaler.joblib"
    label_encoder_file: str = "label_encoder.joblib"
    feature_names_file: str = "feature_names.json"
    percentiles_file: str = "percentiles.joblib"
    
    # Seuils de détection
    anomaly_threshold: float = 0.5
    high_confidence_threshold: float = 0.85
    alert_threshold: float = 0.7  # Seuil pour générer une alerte


@dataclass
class SimulationConfig:
    """Configuration de la simulation."""
    dataset_path: str = "../dataset/cicids2017_cleaned.csv"
    
    # Paramètres de simulation
    batch_size: int = 100
    delay_between_batches: float = 1.0  # secondes
    
    # Distribution du trafic simulé (probabilités)
    traffic_distribution: Dict[str, float] = field(default_factory=lambda: {
        "Normal Traffic": 0.7,
        "DDoS": 0.1,
        "DoS": 0.08,
        "Port Scanning": 0.05,
        "Bots": 0.03,
        "Web Attacks": 0.02,
        "Brute Force": 0.02
    })


@dataclass
class MetricsConfig:
    """Configuration des métriques."""
    output_dir: str = "./metrics"
    report_interval: int = 100  # Générer un rapport tous les N flux


# Instance globale de configuration
KAFKA_CONFIG = KafkaConfig()
MODEL_CONFIG = ModelConfig()
SIMULATION_CONFIG = SimulationConfig()
METRICS_CONFIG = MetricsConfig()
