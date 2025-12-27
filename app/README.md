# IDS Kafka Pipeline - Guide d'Utilisation

Application de detection d'intrusions en temps reel utilisant le modele AutoencoderIDS avec Apache Kafka.

## Table des Matieres

1. [Architecture du Systeme](#architecture-du-systeme)
2. [Pre-requis](#pre-requis)
3. [Installation](#installation)
4. [Configuration du Cluster Kafka](#configuration-du-cluster-kafka)
5. [Modes d'Utilisation](#modes-dutilisation)
6. [Guide Detaille par Mode](#guide-detaille-par-mode)
7. [Format des Messages Kafka](#format-des-messages-kafka)
8. [Metriques et Evaluation](#metriques-et-evaluation)
9. [Exemples de Workflows](#exemples-de-workflows)
10. [Troubleshooting](#troubleshooting)

---

## Architecture du Systeme

```
                                    CLUSTER KAFKA
                                    +------------------+
                                    |                  |
+----------------+    produce       |  ids-raw-data    |
|   Producer     | ---------------> |  (3 partitions)  |
| (Simulateur)   |                  |                  |
+----------------+                  +--------+---------+
                                             |
                                             | consume
                                             v
                                    +------------------+
                                    |    Consumer      |
                                    |  (IDS Predictor) |
                                    +--------+---------+
                                             |
                         +-------------------+-------------------+
                         |                                       |
                         v                                       v
              +------------------+                    +------------------+
              |   ids-alerts     |                    | ids-explanations |
              | (1 partition)    |                    | (1 partition)    |
              +------------------+                    +------------------+
```

### Fichiers du Projet

```
app/
|-- kafka_ids_pipeline.py   # Script principal (3 modes)
|-- predictor.py            # Module de prediction avec le modele
|-- traffic_simulator.py    # Simulateur de trafic reseau
|-- metrics_tracker.py      # Calcul des metriques (FP, FN, etc.)
|-- requirements.txt        # Dependances Python
|-- README.md               # Ce fichier
+-- metrics/                # Rapports de simulation
```

---

## Pre-requis

### Logiciels Requis

- Python 3.8 ou superieur
- Docker avec le cluster Kafka en cours d'execution
- Acces au cluster Kafka sur localhost:9092

### Verification de l'Environnement

```bash
# Verifier Python
python --version

# Verifier que Docker est en cours d'execution
docker ps

# Verifier que Kafka est accessible
docker exec -it kafka kafka-broker-api-versions --bootstrap-server localhost:9092
```

---

## Installation

### Etape 1: Cloner le Repository

```bash
git clone https://github.com/FaissalMarzouki/IDS-Autoencoder-classifier-DL-cicids.git
cd IDS-Autoencoder-classifier-DL-cicids/app
```

### Etape 2: Installer les Dependances Python

```bash
pip install -r requirements.txt
```

Dependances principales:
- torch >= 2.0.0
- numpy >= 1.24.0
- pandas >= 2.0.0
- scikit-learn >= 1.3.0
- joblib >= 1.3.0
- kafka-python >= 2.0.2

### Etape 3: Verifier les Fichiers du Modele

Les fichiers suivants doivent exister dans le dossier ../models/:

```
models/
|-- autoencoder_ids_v1.1.0.pt    # Poids du modele PyTorch
|-- model_config.json            # Configuration du modele
|-- scaler.joblib                # Normalisateur StandardScaler
|-- label_encoder.joblib         # Encodeur des labels
|-- feature_names.json           # Liste des 37 features
+-- percentiles.joblib           # Percentiles pour le clipping
```

---

## Configuration du Cluster Kafka

### Topics Requis

Le cluster Kafka doit contenir les 4 topics suivants:

| Topic | Role | Partitions | Description |
|-------|------|------------|-------------|
| ids-raw-data | Input | 3 | Donnees brutes de trafic reseau |
| ids-features | Intermediaire | 3 | Features extraites (optionnel) |
| ids-alerts | Output | 1 | Alertes de detection d'attaques |
| ids-explanations | Output | 1 | Explications detaillees des predictions |

### Verification des Topics Existants

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

### Creation des Topics (si necessaire)

Si les topics n'existent pas, les creer avec les commandes suivantes:

```bash
# Topic ids-raw-data
docker exec -it kafka kafka-topics --create \
  --topic ids-raw-data \
  --bootstrap-server localhost:9092 \
  --partitions 3 \
  --replication-factor 1

# Topic ids-features
docker exec -it kafka kafka-topics --create \
  --topic ids-features \
  --bootstrap-server localhost:9092 \
  --partitions 3 \
  --replication-factor 1

# Topic ids-alerts
docker exec -it kafka kafka-topics --create \
  --topic ids-alerts \
  --bootstrap-server localhost:9092 \
  --partitions 1 \
  --replication-factor 1

# Topic ids-explanations
docker exec -it kafka kafka-topics --create \
  --topic ids-explanations \
  --bootstrap-server localhost:9092 \
  --partitions 1 \
  --replication-factor 1
```

### Verification de la Configuration d'un Topic

```bash
docker exec -it kafka kafka-topics --describe \
  --topic ids-raw-data \
  --bootstrap-server localhost:9092
```

---

## Modes d'Utilisation

Le script kafka_ids_pipeline.py supporte 3 modes de fonctionnement:

| Mode | Description | Kafka Requis |
|------|-------------|--------------|
| simulation | Test local sans Kafka | Non |
| producer | Envoie des flux vers Kafka | Oui |
| consumer | Recoit et analyse les flux | Oui |

### Arguments de Ligne de Commande

```
Arguments obligatoires:
  --mode          Mode: producer, consumer, simulation

Arguments optionnels:
  --count         Nombre de flux a traiter (defaut: 100)
  --attack-ratio  Proportion d'attaques entre 0.0 et 1.0 (defaut: 0.3)
  --delay         Delai entre messages en secondes (defaut: 0)
  --models-dir    Chemin vers le dossier des modeles (defaut: ../models)
  --dataset       Chemin vers le dataset CSV (defaut: ../dataset/cicids2017_cleaned.csv)
  --kafka-server  Adresse du serveur Kafka (defaut: localhost:9092)
  --verbose, -v   Afficher chaque prediction
  --no-save       Ne pas sauvegarder le rapport de metriques
```

---

## Guide Detaille par Mode

### Mode 1: Simulation (Test Local)

Ce mode permet de tester le modele sans avoir besoin de Kafka.

#### Commande de Base

```bash
python kafka_ids_pipeline.py --mode simulation --count 100
```

#### Options Avancees

```bash
# Test avec 500 flux et 40% d'attaques, affichage detaille
python kafka_ids_pipeline.py --mode simulation --count 500 --attack-ratio 0.4 --verbose

# Test massif (1000 flux, 30% attaques, sans verbose)
python kafka_ids_pipeline.py --mode simulation --count 1000 --attack-ratio 0.3

# Test sans sauvegarde du rapport
python kafka_ids_pipeline.py --mode simulation --count 200 --no-save
```

#### Exemple de Sortie

```
============================================================
IDS KAFKA PIPELINE
============================================================

Chargement du modele...
  - Classes: ['Bots', 'Brute Force', 'DDoS', 'DoS', 'Normal Traffic', 'Port Scanning', 'Web Attacks']
  - Features: 37

Chargement du dataset...
  - Flux disponibles: 2520751
  - Types d'attaques: 7

[SIMULATION] Test de 1000 flux sans Kafka
  - Attack ratio: 30%
  - Verbose: False

  Traite: 100/1000 (Accuracy: 93.0%)
  Traite: 200/1000 (Accuracy: 94.0%)
  ...

============================================================
RAPPORT DE DETECTION IDS
============================================================

Flux traites: 1000
Duree: 58.30s (17.2 flux/s)

--- METRIQUES BINAIRES (Attack vs Normal) ---
Accuracy:     92.00%
Precision:    79.53%
Recall:       99.68%
F1-Score:     88.47%

--- ERREURS ---
Faux Positifs (FP): 79 (11.42%)
Faux Negatifs (FN): 1 (0.32%)

--- MATRICE DE CONFUSION ---
True Positives:  307
True Negatives:  613
False Positives: 79
False Negatives: 1

============================================================
```

---

### Mode 2: Producer (Envoi vers Kafka)

Ce mode envoie des flux reseau simules vers le topic ids-raw-data.

#### Commande de Base

```bash
python kafka_ids_pipeline.py --mode producer --count 1000
```

#### Options Avancees

```bash
# Envoi de 500 flux avec 50% d'attaques
python kafka_ids_pipeline.py --mode producer --count 500 --attack-ratio 0.5

# Envoi avec delai de 100ms entre chaque message (simulation temps reel)
python kafka_ids_pipeline.py --mode producer --count 1000 --delay 0.1

# Envoi vers un serveur Kafka distant
python kafka_ids_pipeline.py --mode producer --count 500 --kafka-server 192.168.1.100:9092
```

#### Verification des Messages Envoyes

Dans un autre terminal, lire les messages du topic:

```bash
docker exec -it kafka kafka-console-consumer \
  --topic ids-raw-data \
  --bootstrap-server localhost:9092 \
  --from-beginning \
  --max-messages 5
```

---

### Mode 3: Consumer (Reception et Analyse)

Ce mode consomme les flux depuis ids-raw-data, execute le modele IDS, et publie les resultats.

#### Commande de Base

```bash
python kafka_ids_pipeline.py --mode consumer
```

#### Options

```bash
# Consumer avec affichage detaille
python kafka_ids_pipeline.py --mode consumer --verbose

# Consumer connecte a un serveur distant
python kafka_ids_pipeline.py --mode consumer --kafka-server 192.168.1.100:9092
```

#### Flux de Donnees

1. Lecture depuis: ids-raw-data
2. Traitement: Prediction avec le modele AutoencoderIDS
3. Publication des alertes vers: ids-alerts (uniquement si attaque detectee)
4. Publication des explications vers: ids-explanations (pour chaque flux)

#### Arret du Consumer

Appuyer sur Ctrl+C pour arreter proprement. Le rapport final sera affiche.

---

## Format des Messages Kafka

### Topic: ids-raw-data (Input)

Format des messages envoyes par le producer:

```json
{
  "flow_id": "sim_00000001",
  "features": [80.0, 0.0, 2.0, 128.0, ...],
  "label": "Normal Traffic",
  "timestamp": 1703672400.0
}
```

Champs:
- flow_id: Identifiant unique du flux
- features: Tableau de 37 valeurs numeriques (features reseau)
- label: Label reel (pour evaluation)
- timestamp: Horodatage Unix

### Topic: ids-alerts (Output)

Format des alertes publiees quand une attaque est detectee:

```json
{
  "timestamp": "2024-12-27T10:30:00.123456",
  "flow_id": "sim_00000001",
  "alert_type": "DDoS",
  "is_attack": true,
  "confidence": 0.9534,
  "anomaly_score": 0.002341,
  "true_label": "DDoS",
  "correct": true
}
```

Champs:
- timestamp: Date et heure de l'alerte
- flow_id: Identifiant du flux concerne
- alert_type: Type d'attaque detectee
- is_attack: Toujours true (seules les attaques sont publiees ici)
- confidence: Confiance de la prediction (0.0 a 1.0)
- anomaly_score: Score d'anomalie base sur l'erreur de reconstruction
- true_label: Label reel (pour evaluation)
- correct: True si la prediction correspond au label reel

### Topic: ids-explanations (Output)

Format des explications detaillees pour chaque flux:

```json
{
  "timestamp": "2024-12-27T10:30:00.123456",
  "flow_id": "sim_00000001",
  "prediction": {
    "flow_id": "sim_00000001",
    "predicted_class": "DDoS",
    "predicted_class_id": 2,
    "confidence": 0.9534,
    "anomaly_score": 0.002341,
    "is_attack": true,
    "all_probabilities": {
      "Bots": 0.0012,
      "Brute Force": 0.0023,
      "DDoS": 0.9534,
      "DoS": 0.0312,
      "Normal Traffic": 0.0089,
      "Port Scanning": 0.0015,
      "Web Attacks": 0.0015
    }
  },
  "true_label": "DDoS",
  "analysis": {
    "is_correct": true,
    "top_3_classes": [
      ["DDoS", 0.9534],
      ["DoS", 0.0312],
      ["Normal Traffic", 0.0089]
    ]
  }
}
```

---

## Metriques et Evaluation

### Metriques Calculees

| Metrique | Description |
|----------|-------------|
| Accuracy | Pourcentage de predictions correctes |
| Precision | TP / (TP + FP) - Fiabilite des alertes |
| Recall | TP / (TP + FN) - Taux de detection des attaques |
| F1-Score | Moyenne harmonique de Precision et Recall |
| FPR | Taux de faux positifs (fausses alertes) |
| FNR | Taux de faux negatifs (attaques manquees) |

### Definition des Erreurs

- True Positive (TP): Attaque correctement detectee
- True Negative (TN): Trafic normal correctement identifie
- False Positive (FP): Trafic normal detecte comme attaque (fausse alerte)
- False Negative (FN): Attaque non detectee (manquee)

### Rapports de Metriques

Les rapports sont sauvegardes dans le dossier metrics/ au format JSON:

```bash
metrics/simulation_report_20241227_153417.json
```

Exemple de contenu:

```json
{
  "summary": {
    "total_flows": 1000,
    "attacks_detected": 386,
    "normal_traffic": 614
  },
  "confusion": {
    "true_positives": 307,
    "true_negatives": 613,
    "false_positives": 79,
    "false_negatives": 1
  },
  "metrics": {
    "accuracy": 0.92,
    "precision": 0.7953,
    "recall": 0.9968,
    "f1_score": 0.8847,
    "false_positive_rate": 0.1142,
    "false_negative_rate": 0.0032
  },
  "timing": {
    "duration_seconds": 58.30,
    "flows_per_second": 17.2
  }
}
```

---

## Exemples de Workflows

### Workflow 1: Test Rapide du Modele

```bash
# Terminal unique
cd app
python kafka_ids_pipeline.py --mode simulation --count 200 --verbose
```

### Workflow 2: Pipeline Kafka Complet

```bash
# Terminal 1: Demarrer le consumer
cd app
python kafka_ids_pipeline.py --mode consumer --verbose

# Terminal 2: Demarrer le producer
cd app
python kafka_ids_pipeline.py --mode producer --count 1000 --attack-ratio 0.3 --delay 0.01

# Terminal 3: Observer les alertes
docker exec -it kafka kafka-console-consumer \
  --topic ids-alerts \
  --bootstrap-server localhost:9092
```

### Workflow 3: Monitoring des Alertes en Temps Reel

```bash
# Terminal 1: Consumer en arriere-plan
python kafka_ids_pipeline.py --mode consumer &

# Terminal 2: Lire les alertes
docker exec -it kafka kafka-console-consumer \
  --topic ids-alerts \
  --bootstrap-server localhost:9092 \
  --property print.timestamp=true

# Terminal 3: Lire les explications
docker exec -it kafka kafka-console-consumer \
  --topic ids-explanations \
  --bootstrap-server localhost:9092
```

---

## Troubleshooting

### Erreur: Kafka non accessible

Symptome:
```
[WARN] Kafka non disponible: NoBrokersAvailable
```

Solutions:
1. Verifier que Docker est en cours d'execution: docker ps
2. Verifier que le conteneur Kafka est demarre
3. Verifier l'adresse du serveur avec --kafka-server

### Erreur: Modele non trouve

Symptome:
```
FileNotFoundError: models/autoencoder_ids_v1.1.0.pt
```

Solution:
Verifier que le dossier models/ contient tous les fichiers requis.

### Erreur: Dataset non trouve

Symptome:
```
FileNotFoundError: dataset/cicids2017_cleaned.csv
```

Solution:
Telecharger le dataset depuis CICIDS2017 et le placer dans le dossier dataset/.

### Erreur: Version sklearn incompatible

Symptome:
```
InconsistentVersionWarning: Trying to unpickle estimator StandardScaler from version X
```

Solution:
Ce warning peut etre ignore. Pour l'eliminer, reinstaller sklearn avec la meme version utilisee pour l'entrainement.

### Performance lente

Solutions:
1. Reduire le nombre de flux avec --count
2. Desactiver le mode verbose
3. Utiliser un GPU si disponible (le modele detecte automatiquement CUDA)

---

## Classes Detectees

Le modele detecte 7 types de trafic:

| ID | Classe | Description |
|----|--------|-------------|
| 0 | Bots | Machines infectees (botnets) |
| 1 | Brute Force | Attaques par force brute |
| 2 | DDoS | Distributed Denial of Service |
| 3 | DoS | Denial of Service |
| 4 | Normal Traffic | Trafic legitime |
| 5 | Port Scanning | Scan de ports |
| 6 | Web Attacks | SQL Injection, XSS, etc. |

---

## Contact

Pour toute question, contacter l'equipe du projet.
