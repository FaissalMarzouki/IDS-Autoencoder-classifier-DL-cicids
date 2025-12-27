# IDS Kafka Pipeline - Guide d'Utilisation

## Description

Application de detection d'intrusions reseau en temps reel utilisant un modele 
Autoencoder+Classifier entraine sur le dataset CICIDS2017.

L'application consomme des flux reseau depuis Kafka, effectue des predictions 
avec le modele de deep learning, et publie les alertes sur les topics de sortie.


## Prerequis

Logiciels requis:
- Python 3.8+
- Docker avec le cluster Kafka (deja configure par le collegue)

Installation des dependances Python:
```
pip install torch numpy pandas scikit-learn joblib kafka-python
```


## Topics Kafka Utilises

Les topics suivants doivent etre disponibles dans le cluster:

| Topic | Direction | Description |
|-------|-----------|-------------|
| ids-raw-data | Entree | Flux reseau bruts a analyser |
| ids-features | Intermediaire | Features extraites (optionnel) |
| ids-alerts | Sortie | Alertes de detection |
| ids-explanations | Sortie | Explications detaillees des alertes |


## Modes d'Execution

### 1. Mode Simulation (sans Kafka - pour tests locaux)

Permet de tester le modele sans avoir besoin du cluster Kafka.
Utilise le dataset local pour simuler du trafic.

```
cd app
python kafka_ids_pipeline.py --mode simulation --count 1000
```

Options:
- --count N : Nombre de flux a traiter (defaut: 1000)
- --dataset PATH : Chemin vers le dataset CSV


### 2. Mode Producteur (envoi de trafic simule vers Kafka)

Envoie des flux simules depuis le dataset vers le topic ids-raw-data.
Utile pour tester le pipeline complet.

```
cd app
python kafka_ids_pipeline.py --mode producer --count 500 --delay 0.1
```

Options:
- --count N : Nombre de flux a envoyer
- --delay S : Delai entre chaque flux en secondes (defaut: 0.01)
- --bootstrap-servers HOST:PORT : Adresse du broker Kafka (defaut: localhost:9092)


### 3. Mode Consommateur (traitement des flux depuis Kafka)

Consomme les flux depuis ids-raw-data, effectue les predictions,
et publie les resultats sur ids-alerts et ids-explanations.

```
cd app
python kafka_ids_pipeline.py --mode consumer --max 1000
```

Options:
- --max N : Nombre maximum de messages a traiter (optionnel, sans limite par defaut)
- --bootstrap-servers HOST:PORT : Adresse du broker Kafka

Pour arreter: Ctrl+C (le rapport final sera affiche automatiquement)


### 4. Mode Complet (producteur + consommateur)

Lance simultanement le producteur et le consommateur pour un test complet.

```
cd app
python kafka_ids_pipeline.py --mode full --count 500
```


## Configuration du Broker Kafka

Si le broker Kafka n'est pas sur localhost:9092, specifier l'adresse:

```
python kafka_ids_pipeline.py --mode consumer --bootstrap-servers kafka-broker:9092
```

Pour un cluster multi-brokers:
```
python kafka_ids_pipeline.py --mode consumer --bootstrap-servers broker1:9092,broker2:9092
```


## Format des Messages Kafka

### Message d'entree (topic: ids-raw-data)

```json
{
    "flow_id": "flow_001",
    "features": [0.1, 0.2, 0.3, ...],
    "true_label": "DDoS",
    "timestamp": "2024-01-15T10:30:00Z"
}
```

Champs:
- features : Array de 37 valeurs numeriques (ordre dans models/feature_names.json)
- true_label : Optionnel, uniquement pour evaluation des performances
- flow_id : Identifiant unique du flux


### Message de sortie - Alertes (topic: ids-alerts)

```json
{
    "flow_id": "flow_001",
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

Valeurs possibles pour alert_type: ATTACK_DETECTED, NORMAL


### Message de sortie - Explications (topic: ids-explanations)

Publie uniquement pour les attaques detectees.

```json
{
    "flow_id": "flow_001",
    "timestamp": "2024-01-15T10:30:01Z",
    "explanation": {
        "predicted_class": "DDoS",
        "confidence": 0.95,
        "all_probabilities": {
            "Normal Traffic": 0.02,
            "DDoS": 0.95,
            "DoS": 0.02,
            "Bots": 0.001
        },
        "reconstruction_error": 0.041,
        "anomaly_score": 0.82,
        "reason": "Attaque DDoS detectee avec 95% de confiance"
    }
}
```


## Liste des 37 Features

Les features doivent etre fournies dans cet ordre exact:

 1. Destination Port
 2. Flow Duration
 3. Total Fwd Packets
 4. Total Length of Fwd Packets
 5. Fwd Packet Length Max
 6. Fwd Packet Length Min
 7. Fwd Packet Length Mean
 8. Fwd Packet Length Std
 9. Bwd Packet Length Max
10. Bwd Packet Length Min
11. Bwd Packet Length Mean
12. Bwd Packet Length Std
13. Flow Bytes/s
14. Flow Packets/s
15. Flow IAT Mean
16. Flow IAT Std
17. Flow IAT Max
18. Flow IAT Min
19. Fwd IAT Total
20. Fwd IAT Mean
21. Fwd IAT Std
22. Fwd IAT Max
23. Fwd IAT Min
24. Bwd IAT Total
25. Bwd IAT Mean
26. Bwd IAT Std
27. Bwd IAT Max
28. Bwd IAT Min
29. Fwd Header Length
30. Bwd Header Length
31. Fwd Packets/s
32. Bwd Packets/s
33. Min Packet Length
34. Max Packet Length
35. Packet Length Mean
36. Packet Length Std
37. Packet Length Variance

Fichier de reference: ../models/feature_names.json


## Classes de Detection

| ID | Classe | Description |
|----|--------|-------------|
| 0 | Bots | Machines infectees (botnets) |
| 1 | Brute Force | Attaques par force brute |
| 2 | DDoS | Deni de service distribue |
| 3 | DoS | Deni de service |
| 4 | Normal Traffic | Trafic legitime |
| 5 | Port Scanning | Scan de ports |
| 6 | Web Attacks | Attaques web (SQL injection, XSS) |


## Evaluation des Performances

Apres une session de traitement, un rapport JSON est genere dans le dossier metrics/.

Pour afficher une analyse detaillee:
```
python evaluate_performance.py
```

Metriques calculees:
- True Positives (TP): Attaques detectees correctement
- True Negatives (TN): Trafic normal identifie correctement
- False Positives (FP): Fausses alertes
- False Negatives (FN): Attaques manquees
- Precision, Recall, F1-Score par classe


## Structure des Fichiers

```
app/
    config.py              - Configuration (Kafka, modele, paths)
    predictor.py           - Classe de prediction (charge le modele)
    traffic_simulator.py   - Simulateur de trafic depuis le dataset
    metrics_tracker.py     - Calcul des metriques FP/FN/TP/TN
    kafka_ids_pipeline.py  - Pipeline principal (CLI)
    evaluate_performance.py - Script d'evaluation des performances
    metrics/               - Rapports JSON generes

models/
    autoencoder_ids_v1.1.0.pt  - Modele PyTorch
    model_config.json          - Configuration du modele
    scaler.joblib              - Normalisateur
    label_encoder.joblib       - Encodeur des labels
    feature_names.json         - Liste des 37 features
    percentiles.joblib         - Percentiles pour clipping
```


## Exemples d'Integration

### Envoyer un flux depuis Python

```python
from kafka import KafkaProducer
import json

producer = KafkaProducer(
    bootstrap_servers='localhost:9092',
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

flow = {
    "flow_id": "test_001",
    "features": [80, 1000, 10, 500, ...],  # 37 valeurs
    "timestamp": "2024-01-15T10:30:00Z"
}

producer.send('ids-raw-data', flow)
producer.flush()
```


### Recevoir les alertes depuis Python

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
        print(f"ALERTE: {alert['predicted_class']} - Confiance: {alert['confidence']}")
```


## Depannage

Erreur: kafka-python non installe
```
pip install kafka-python
```

Erreur: Connection refused au broker Kafka
- Verifier que le cluster Kafka est demarre
- Verifier l'adresse du broker avec --bootstrap-servers

Erreur: Topic not found
- Verifier que les topics sont crees dans Kafka
- Lister les topics: docker exec -it kafka kafka-topics --list --bootstrap-server localhost:9092

Performances lentes
- Reduire le delai avec --delay 0.001
- Augmenter les partitions des topics Kafka


## Auteur

Faissal Marzouki - Decembre 2024
