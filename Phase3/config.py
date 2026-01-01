"""
Configuration centralisée pour Phase3
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Charger le fichier .env
load_dotenv()

# ============================================================================
# CHEMINS DU PROJET
# ============================================================================

# Répertoire racine de Phase3
PHASE3_ROOT = Path(__file__).parent.resolve()

# Répertoire racine du projet principal
PROJECT_ROOT = PHASE3_ROOT.parent

# Chemin vers les modèles (dans le dossier principal)
MODELS_DIR = PROJECT_ROOT / 'models'

# Chemin vers le dataset CICIDS2017
DATASET_DIR = Path('/home/ellayli/enset_CCN/s5/IA/project/IDS-Autoencoder-classifier-DL-cicids/MachineLearningCSV/MachineLearningCVE')

# ============================================================================
# KAFKA CONFIGURATION
# ============================================================================

KAFKA_CONFIG = {
    'bootstrap_servers': os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092'),
    'topics': {
        'alerts': os.getenv('KAFKA_ALERT_TOPIC', 'ids-alerts'),
        'explanations': os.getenv('KAFKA_EXPLANATION_TOPIC', 'ids-explanations'),
        'raw_data': 'ids-raw-data',      # Topic du pipeline principal
        'features': 'ids-features'        # Topic du pipeline principal
    },
    'consumer_groups': {
        'llm_service': 'llm-service-group',
        'dashboard': 'dashboard-group'
    },
    'producer_config': {
        'acks': 'all',
        'retries': 3
    },
    'consumer_config': {
        'auto_offset_reset': 'latest',
        'session_timeout_ms': 30000,
        'request_timeout_ms': 40000,
        'enable_auto_commit': True,
        'max_poll_records': 100
    },
    'consumer_group': 'phase3-consumer-group',
    'auto_offset_reset': 'latest',
    'session_timeout_ms': 30000,
    'request_timeout_ms': 40000
}

# ============================================================================
# LLM CONFIGURATION
# ============================================================================

LLM_CONFIG = {
    'provider': os.getenv('LLM_PROVIDER', 'google'),  # openai, anthropic, ollama, groq, openrouter, google
    'model': os.getenv('LLM_MODEL', 'gemini-1.5-flash-latest'),
    'temperature': float(os.getenv('LLM_TEMPERATURE', '0.3')),
    # Augmenté pour éviter les réponses tronquées (ajuster via LLM_MAX_TOKENS si besoin)
    'max_tokens': int(os.getenv('LLM_MAX_TOKENS', '2000')),
    
    # System prompt pour le LLM
    'system_prompt': """Tu es un expert en cybersécurité spécialisé dans l'analyse d'alertes IDS.
    
Ton rôle est d'expliquer les alertes de sécurité de manière claire et actionnable pour une équipe SOC.

Instructions:
1. Analyse le type d'attaque détecté et explique sa nature
2. Identifie les features les plus contributives et leur signification
3. Évalue la sévérité réelle basée sur le contexte
4. Fournis des recommandations concrètes et immédiates
5. Attribue un niveau de priorité (P1=Critique, P2=Élevé, P3=Moyen, P4=Faible)

Format de réponse:
- Résumé (2-3 phrases)
- Analyse technique
- Impact potentiel
- Recommandations (liste à puces)
- Priorité""",
    
    # API Keys
    'openai_api_key': os.getenv('OPENAI_API_KEY'),
    'anthropic_api_key': os.getenv('ANTHROPIC_API_KEY'),
    'groq_api_key': os.getenv('GROQ_API_KEY'),
    'groq_api_keys': [k.strip() for k in os.getenv('GROQ_API_KEYS', '').split(',') if k.strip()],
    'openrouter_api_key': os.getenv('OPENROUTER_API_KEY'),
    'google_api_key': os.getenv('GOOGLE_API_KEY'),
    'ollama_base_url': os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
}

# ============================================================================
# DASHBOARD CONFIGURATION
# ============================================================================

DASHBOARD_CONFIG = {
    'port': int(os.getenv('DASHBOARD_PORT', '8501')),
    'refresh_rate': int(os.getenv('DASHBOARD_REFRESH_RATE', '2')),
    'max_items_display': 200,
    'chart_update_interval': 5  # secondes
}

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

LOG_CONFIG = {
    'level': os.getenv('LOG_LEVEL', 'INFO'),
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'log_dir': PHASE3_ROOT / 'logs'
}

# Créer le dossier logs s'il n'existe pas
LOG_CONFIG['log_dir'].mkdir(exist_ok=True)

# ============================================================================
# MODEL CONFIGURATION
# ============================================================================

MODEL_CONFIG = {
    'model_path': MODELS_DIR / 'autoencoder_ids_v1.1.0.pt',
    'scaler_path': MODELS_DIR / 'scaler.joblib',
    'label_encoder_path': MODELS_DIR / 'label_encoder.joblib',
    'percentiles_path': MODELS_DIR / 'percentiles.joblib',
    'feature_names_path': MODELS_DIR / 'feature_names.json',
    'model_config_path': MODELS_DIR / 'model_config.json',
    
    # Paramètres du modèle
    'input_dim': 37,
    'latent_dim': 16,
    'hidden_dims': [128, 64, 32],
    'num_classes': 7,
    'dropout': 0.3,
    
    # Seuils
    'anomaly_threshold': 0.05,
    'confidence_threshold': 0.5
}

# ============================================================================
# CLASSES IDS
# ============================================================================

IDS_CLASSES = [
    'Normal Traffic',
    'DDoS',
    'DoS',
    'Brute Force',
    'Web Attacks',
    'Bots',
    'Port Scanning'
]

# ============================================================================
# FEATURES DU MODÈLE (37 features)
# ============================================================================

FEATURE_COLUMNS = [
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

# ============================================================================
# VALIDATION
# ============================================================================

def validate_config():
    """Valide que la configuration est correcte"""
    errors = []
    
    # Vérifier que les modèles existent
    if not MODEL_CONFIG['model_path'].exists():
        errors.append(f"Modèle non trouvé: {MODEL_CONFIG['model_path']}")
    
    if not MODEL_CONFIG['scaler_path'].exists():
        errors.append(f"Scaler non trouvé: {MODEL_CONFIG['scaler_path']}")
    
    # Vérifier l'API key LLM
    provider = LLM_CONFIG['provider']
    if provider == 'groq' and not (LLM_CONFIG['groq_api_key'] or LLM_CONFIG['groq_api_keys']):
        errors.append("GROQ_API_KEY ou GROQ_API_KEYS manquante dans .env")
    elif provider == 'openai' and not LLM_CONFIG['openai_api_key']:
        errors.append("OPENAI_API_KEY manquante dans .env")
    elif provider == 'anthropic' and not LLM_CONFIG['anthropic_api_key']:
        errors.append("ANTHROPIC_API_KEY manquante dans .env")
    elif provider == 'google' and not LLM_CONFIG['google_api_key']:
        errors.append("GOOGLE_API_KEY manquante dans .env")
    
    if errors:
        print("❌ Erreurs de configuration:")
        for error in errors:
            print(f"  - {error}")
        return False
    
    return True


if __name__ == '__main__':
    print("🔍 Validation de la configuration...")
    print(f"📁 PHASE3_ROOT: {PHASE3_ROOT}")
    print(f"📁 PROJECT_ROOT: {PROJECT_ROOT}")
    print(f"📁 MODELS_DIR: {MODELS_DIR}")
    print(f"📁 DATASET_DIR: {DATASET_DIR}")
    print(f"🤖 LLM Provider: {LLM_CONFIG['provider']}")
    print(f"🤖 LLM Model: {LLM_CONFIG['model']}")
    print(f"📊 Kafka: {KAFKA_CONFIG['bootstrap_servers']}")
    
    if validate_config():
        print("✅ Configuration valide!")
    else:
        print("❌ Configuration invalide!")
