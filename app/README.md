# IDS Kafka Pipeline - Guide d'utilisation

## Description

Application de detection d'intrusions reseau en temps reel basee sur un modele 
Autoencoder+Classifier entraine sur le dataset CICIDS2017.

Le systeme consomme des flux reseau depuis Kafka, effectue des predictions 
avec le modele de deep learning, et publie les alertes sur des topics dedies.


## Structure des fichiers

```
app/
    config.py              - Configuration (Kafka, modele, simulation)
    predictor.py           - Classe de prediction IDS
    traffic_simulator.py   - Simulateur de trafic depuis le dataset
    metrics_tracker.py     - Suivi des metriques (FP, FN, TP, TN)
    kafka_ids_pipeline.py  - Pipeline Kafka principal
    evaluate_performance.py - Script d'evaluation des performances
    README.md              - Ce fichier
```


## Prerequis

### 1. Installer les dependances Python

```bash
pip install torch numpy pandas scikit-learn joblib kafka-python
```

### 2. Demarrer le cluster Kafka avec Docker

```bash
# Option 1: Avec docker-compose (recommande)
docker-compose up -d

# Option 2: Manuellement
docker run -d --name zookeeper -p 2181:2181 zookeeper:3.7

docker run -d --name kafka -p 9092:9092 \
  --link zookeeper \
  -e KAFKA_ZOOKEEPER_CONNECT=zookeeper:2181 \
  -e KAFKA_ADVERTISED_LISTENERS=PLAINTEXT://localhost:9092 \
  -e KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR=1 \
  confluentinc/cp-kafka:7.0.0
```

### 3. Creer les topics Kafka

Executer ces commandes depuis le conteneur Kafka:

```bash
# Topic pour les donnees brutes (entree)
docker exec -it kafka kafka-topics --create \
  --topic ids-raw-data \
  --bootstrap-server localhost:9092 \
  --partitions 3 \
  --replication-factor 1

# Topic pour les features extraites (intermediaire)
docker exec -it kafka kafka-topics --create \
  --topic ids-features \
  --bootstrap-server localhost:9092 \
  --partitions 3 \
  --replication-factor 1

# Topic pour les alertes (sortie principale)
docker exec -it kafka kafka-topics --create \
  --topic ids-alerts \
  --bootstrap-server localhost:9092 \
  --partitions 1 \
  --replication-factor 1

# Topic pour les explications detaillees (sortie secondaire)
docker exec -it kafka kafka-topics --create \
  --topic ids-explanations \
  --bootstrap-server localhost:9092 \
  --partitions 1 \
  --replication-factor 1
```

### 4. Verifier que les topics sont crees

```bash
docker exec -it kafka kafka-topics --list --bootstrap-server localhost:9092
```

Resultat attendu:
```
ids-alerts
ids-explanations
ids-features
ids-raw-data
```


## Utilisation

### Mode 1: Simulation locale (sans Kafka)

Pour tester le modele localement sans avoir besoin d'un cluster Kafka:

```bash
cd app
python kafka_ids_pipeline.py --mode simulation --count 1000
```

Ce mode:
- Charge le dataset CICIDS2017
- Genere des flux aleatoires
- Effectue des predictions
- Affiche les metriques en temps reel
- Sauvegarde un rapport JSON dans ./metrics/

### Mode 2: Producteur Kafka

Envoie des flux simules vers le topic ids-raw-data:

```bash
cd app
python kafka_ids_pipeline.py --mode producer --count 500 --delay 0.1
```

Parametres:
- --count : Nombre de flux a envoyer (defaut: 1000)
- --delay : Delai entre chaque flux en secondes (defaut: 0.01)
- --bootstrap-servers : Adresse du broker Kafka (defaut: localhost:9092)

### Mode 3: Consommateur Kafka

Traite les flux depuis ids-raw-data et publie les alertes:

```bash
cd app
python kafka_ids_pipeline.py --mode consumer --max 1000
```

Parametres:
- --max : Nombre maximum de messages a traiter (optionnel, sans limite par defaut)
- --bootstrap-servers : Adresse du broker Kafka (defaut: localhost:9092)

Pour arreter le consommateur: Ctrl+C

Le consommateur:
- Lit les flux depuis ids-raw-data
- Effectue une prediction avec le modele IDS
- Publie une alerte sur ids-alerts
- Publie une explication sur ids-explanations (si attaque detectee)
- Calcule les metriques en temps reel

### Mode 4: Pipeline complet

Lance le producteur et le consommateur en parallele:

```bash
cd app
python kafka_ids_pipeline.py --mode full --count 500
```


## Options de ligne de commande

| Option | Description | Valeurs |
|--------|-------------|---------|
| --mode | Mode d'execution | simulation, producer, consumer, full |
| --count | Nombre de flux a produire | Entier (defaut: 1000) |
| --max | Nombre max de messages a consommer | Entier (optionnel) |
| --delay | Delai entre les flux produits | Secondes (defaut: 0.01) |
| --bootstrap-servers | Adresse Kafka | host:port (defaut: localhost:9092) |
| --dataset | Chemin vers le dataset CSV | Chemin (defaut: ../dataset/cicids2017_cleaned.csv) |


## Format des messages Kafka

### Topic: ids-raw-data (entree)

Structure JSON attendue:

```json
{
    "flow_id": "flow_00000001",
    "features": [0.1, 0.2, 0.3, ...],
    "true_label": "DDoS",
    "timestamp": "2024-01-15T10:30:00Z"
}
```

Champs:
- flow_id (string): Identifiant unique du flux reseau
- features (array): Tableau de 37 valeurs numeriques representant les features reseau
- true_label (string, optionnel): Label reel pour l'evaluation des performances
- timestamp (string): Horodatage au format ISO 8601

### Topic: ids-alerts (sortie)

Structure JSON produite:

```json
{
    "flow_id": "flow_00000001",
    "timestamp": "2024-01-15T10:30:01Z",
    "alert_type": "ATTACK_DETECTED",
    "predicted_class": "DDoS",
    "confidence": 0.95,
    "anomaly_score": 0.82,
    "is_anomaly": true,
    "true_label": "DDoS",
    "is_correct": true
}
```

Champs:
- alert_type (string): "ATTACK_DETECTED" ou "NORMAL"
- predicted_class (string): Classe predite par le modele
- confidence (float): Niveau de confiance entre 0 et 1
- anomaly_score (float): Score d'anomalie base sur l'erreur de reconstruction
- is_anomaly (boolean): true si le score depasse le seuil configure

### Topic: ids-explanations (sortie)

Structure JSON produite (uniquement pour les attaques detectees):

```json
{
    "flow_id": "flow_00000001",
    "timestamp": "2024-01-15T10:30:01Z",
    "explanation": {
        "predicted_class": "DDoS",
        "confidence": 0.95,
        "all_probabilities": {
            "Normal Traffic": 0.02,
            "DDoS": 0.95,
            "DoS": 0.02,
            "Bots": 0.01,
            "Port Scanning": 0.00,
            "Web Attacks": 0.00,
            "Brute Force": 0.00
        },
        "reconstruction_error": 0.041,
        "anomaly_score": 0.82,
        "reason": "Attaque DDoS detectee avec 95% de confiance"
    }
}
```


## Integration avec votre application

### Exemple: Consommer les alertes en Python

```python
from kafka import KafkaConsumer
import json

consumer = KafkaConsumer(
    'ids-alerts',
    bootstrap_servers='localhost:9092',
    value_deserializer=lambda m: json.loads(m.decode('utf-8'))
)

for message in consumer:
    alert = message.value
    
    if alert['alert_type'] == 'ATTACK_DETECTED':
        print(f"ALERTE: {alert['predicted_class']}")
        print(f"Confiance: {alert['confidence']:.1%}")
        print(f"Flow ID: {alert['flow_id']}")
        # Ajouter votre logique de traitement ici
```

### Exemple: Envoyer des flux depuis votre application

```python
from kafka import KafkaProducer
import json
from datetime import datetime

producer = KafkaProducer(
    bootstrap_servers='localhost:9092',
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

# Preparer un flux (37 features requises)
flow = {
    "flow_id": "my_flow_001",
    "features": [0.0] * 37,  # Remplacer par vos vraies features
    "timestamp": datetime.now().isoformat()
}

# Envoyer vers Kafka
producer.send('ids-raw-data', flow)
producer.flush()
```


## Evaluation des performances

Pour analyser les performances du modele apres une simulation:

```bash
cd app
python evaluate_performance.py
```

Ce script affiche:
- Resume global (accuracy, debit, temps d'execution)
- Matrice de confusion (TP, TN, FP, FN)
- Metriques par classe (Precision, Recall, F1-Score)
- Taux de detection et taux de faux positifs
- Score global sur 100


## Liste des classes detectees

| ID | Classe | Description |
|----|--------|-------------|
| 0 | Bots | Machines infectees par des botnets |
| 1 | Brute Force | Attaques par force brute sur authentification |
| 2 | DDoS | Distributed Denial of Service |
| 3 | DoS | Denial of Service |
| 4 | Normal Traffic | Trafic reseau legitime |
| 5 | Port Scanning | Reconnaissance par scan de ports |
| 6 | Web Attacks | Attaques web (SQL injection, XSS, etc.) |


## Configuration

Modifier le fichier config.py pour ajuster les parametres:

```python
# Configuration Kafka
KAFKA_CONFIG.bootstrap_servers = "localhost:9092"
KAFKA_CONFIG.topic_raw_data = "ids-raw-data"
KAFKA_CONFIG.topic_alerts = "ids-alerts"
KAFKA_CONFIG.topic_explanations = "ids-explanations"

# Configuration du modele
MODEL_CONFIG.models_dir = "../models"
MODEL_CONFIG.anomaly_threshold = 0.5
MODEL_CONFIG.high_confidence_threshold = 0.85

# Configuration de la simulation
SIMULATION_CONFIG.dataset_path = "../dataset/cicids2017_cleaned.csv"
SIMULATION_CONFIG.batch_size = 100
```


## Performances attendues

Resultats obtenus sur 5000 flux de test:

| Metrique | Valeur |
|----------|--------|
| Accuracy globale | 90.56% |
| Detection Rate (Recall) | 100.00% |
| Taux de False Positive | 11.14% |
| Taux de False Negative | 0.00% |
| Debit de traitement | 814 flux/s |

Note: Le modele est configure pour etre conservateur. Il prefere generer 
des fausses alertes (False Positives) plutot que de manquer une attaque 
(False Negatives). C'est le comportement souhaite pour un systeme IDS.


## Depannage

### Erreur: kafka-python non installe

```bash
pip install kafka-python
```

### Erreur: Connexion Kafka refusee

Verifier que Kafka est en cours d'execution:

```bash
docker ps | grep kafka
```

Si le conteneur n'est pas actif, le demarrer:

```bash
docker start kafka
```

### Erreur: Topic non trouve

Creer les topics en suivant la section "Creer les topics Kafka" ci-dessus.

### Erreur: Modele non trouve

Verifier que le dossier models/ contient tous les fichiers necessaires:
- autoencoder_ids_v1.1.0.pt (poids du modele)
- model_config.json (configuration)
- scaler.joblib (normalisation)
- label_encoder.joblib (encodage des classes)
- feature_names.json (noms des features)
- percentiles.joblib (valeurs de clipping)

### Erreur: Dataset non trouve

Verifier que le fichier dataset/cicids2017_cleaned.csv existe.


## Auteur

Faissal Marzouki - Decembre 2024
