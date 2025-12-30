import os

# Kafka Config
KAFKA_BOOTSTRAP_SERVERS = "localhost:9093"
TOPICS = {
    "raw": "ids-raw-data",
    "features": "ids-features",
    "alerts": "ids-alerts",
    "explanations": "ids-explanations"
}

# Model Config (Issu de config.json / notebook)
ARTIFACTS_PATH = "models/artifacts/"
INPUT_DIM = 37
LATENT_DIM = 16
NUM_CLASSES = 7
HIDDEN_DIMS = [128, 64, 32]
DEVICE = "cpu" # Ou 'cuda' si disponible
