# Explication Technique du Pipeline IDS Kafka

## Table des Matières

1. [Vue d'ensemble](#vue-densemble)
2. [Comment fonctionne chaque composant](#comment-fonctionne-chaque-composant)
3. [Patterns Kafka utilisés](#patterns-kafka-utilisés)
4. [Threading et Concurrence](#threading-et-concurrence)
5. [Gestion des Données](#gestion-des-données)
6. [Points Importants](#points-importants)

---

## Vue d'ensemble

Le fichier `automated_ids_pipeline.py` implémente un **pipeline de détection d'intrusions en temps réel** utilisant :
- **Apache Kafka** pour le streaming de données
- **AutoencoderIDS** (PyTorch) pour la détection
- **Threading Python** pour le traitement parallèle

### Flux Simplifié

```
CSV → Producer → Topic1 → Consumer/Producer → Topic2 → Detector → Topic3 → Monitor
```

---

## Comment fonctionne chaque composant

### 1. **TrafficProducer** - Le Générateur de Trafic

```python
class TrafficProducer:
    def __init__(self, dataset_path, bootstrap_servers):
        # 1. Charge le simulateur (lit le CSV)
        self.simulator = TrafficSimulator(dataset_path)
        
        # 2. Crée un producer Kafka
        self.producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
```

**Ce qu'il fait** :
1. Lit le dataset CICIDS2017 (500 flux réseau dans votre cas)
2. Sélectionne aléatoirement des flux selon le ratio d'attaque
3. Envoie chaque flux vers le topic `ids-raw-data`
4. Attend `delay` secondes entre chaque envoi

**Exemple concret** :
```python
# Génère 200 flux avec 20% d'attaques
for i, flow in enumerate(simulator.generate_stream(200, 0.2)):
    # flow = {flow_id, features[37], label, timestamp}
    producer.send('ids-raw-data', flow.to_dict())
    time.sleep(0.05)  # Délai 50ms
```

**Pourquoi c'est important** :
- Simule un flux réseau réel
- Permet de tester le système avec différents ratios d'attaque
- Le délai évite de surcharger Kafka

---

### 2. **DataPreprocessor** - Le Validateur

```python
class DataPreprocessor:
    def __init__(self, bootstrap_servers):
        # Consumer : lit depuis ids-raw-data
        self.consumer = KafkaConsumer('ids-raw-data', ...)
        
        # Producer : écrit vers ids-features
        self.producer = KafkaProducer(...)
```

**Ce qu'il fait** :
1. **Consomme** les messages de `ids-raw-data`
2. **Valide** la structure des données
3. **Ajoute** des métadonnées (timestamp de preprocessing)
4. **Produit** vers `ids-features`

**Code clé** :
```python
def process_flow(self, raw_data: dict) -> dict:
    return {
        'flow_id': raw_data['flow_id'],
        'features': raw_data['features'],  # 37 valeurs numériques
        'label': raw_data['label'],        # ex: "DDoS"
        'timestamp': raw_data['timestamp'],
        'preprocessed_at': datetime.now().isoformat()  # NOUVEAU
    }

def run(self):
    for message in self.consumer:
        # 1. Lire le message
        raw_data = message.value
        
        # 2. Traiter
        features_data = self.process_flow(raw_data)
        
        # 3. Envoyer
        self.producer.send('ids-features', features_data)
        
        print(f"[OK] {raw_data['flow_id']} → ids-features")
```

**Pourquoi c'est important** :
- Sépare la génération de données du traitement
- Permet d'ajouter facilement des validations
- Trace quand chaque flux a été traité

---

### 3. **ThreatDetector** - Le Cerveau du Système

```python
class ThreatDetector:
    def __init__(self, models_dir, bootstrap_servers):
        # 1. Charge le modèle PyTorch
        self.predictor = IDSPredictor(models_dir)
        
        # 2. Consumer depuis ids-features
        self.consumer = KafkaConsumer('ids-features', ...)
        
        # 3. Producer vers ids-alerts
        self.producer = KafkaProducer(...)
```

**Ce qu'il fait** :
1. **Consomme** depuis `ids-features`
2. **Charge** les features dans le modèle AutoencoderIDS
3. **Prédit** la classe d'attaque + confiance + anomaly score
4. **Calcule** la sévérité (CRITIQUE/ÉLEVÉE/MOYENNE/FAIBLE)
5. **Publie** vers `ids-alerts` **SEULEMENT SI ATTAQUE**

**Code clé** :
```python
def detect(self, features_data: dict):
    # 1. Prédiction avec le modèle
    prediction = self.predictor.predict(
        features_data['features'],
        features_data['flow_id']
    )
    # prediction = {
    #     predicted_class: "DDoS",
    #     confidence: 0.9534,
    #     anomaly_score: 0.002341,
    #     is_attack: True,
    #     all_probabilities: {...}
    # }
    
    # 2. UNIQUEMENT SI ATTAQUE
    if prediction.is_attack:
        # Créer l'alerte
        alert = {
            'timestamp': datetime.now().isoformat(),
            'flow_id': features_data['flow_id'],
            'alert_type': prediction.predicted_class,
            'confidence': prediction.confidence,
            'anomaly_score': prediction.anomaly_score,
            'severity': self._calculate_severity(prediction),
            'true_label': features_data['label'],
            'correct': prediction.predicted_class == features_data['label'],
            'all_probabilities': prediction.all_probabilities,
            'top_3_classes': [...]
        }
        
        # Envoyer vers Kafka
        self.producer.send('ids-alerts', alert)
        print(f"[ALERTE] {prediction.predicted_class} ({prediction.confidence:.1%})")
    else:
        # Trafic normal - pas d'alerte
        print(f"[OK] Trafic normal (conf: {prediction.confidence:.1%})")
```

**Calcul de la sévérité** :
```python
def _calculate_severity(self, prediction) -> str:
    if prediction.confidence >= 0.9:
        return "CRITIQUE"    # Rouge
    elif prediction.confidence >= 0.7:
        return "ÉLEVÉE"      # Jaune
    elif prediction.confidence >= 0.5:
        return "MOYENNE"     # Bleu
    else:
        return "FAIBLE"      # Vert
```

**⚠️ CHANGEMENT IMPORTANT** :
- **Avant** : Envoyait toujours vers `ids-explanations`
- **Maintenant** : Envoie vers `ids-alerts` uniquement si attaque
- **Phase 2** : Le `LLMExplainer` consommera `ids-alerts` et produira `ids-explanations`

**Pourquoi c'est important** :
- Réduit le volume de données (pas d'alertes pour le trafic normal)
- Permet au LLM de traiter uniquement les vrais incidents
- Économise des ressources (appels API LLM coûteux)

---

### 4. **AlertMonitor** - L'Afficheur

```python
class AlertMonitor:
    def __init__(self, bootstrap_servers):
        # Consumer depuis ids-alerts
        self.consumer = KafkaConsumer('ids-alerts', ...)
        
        # Statistiques
        self.total_alerts = 0
        self.alerts_by_type = {}
        self.start_time = time.time()
```

**Ce qu'il fait** :
1. **Consomme** depuis `ids-alerts`
2. **Affiche** chaque alerte avec code couleur
3. **Calcule** des statistiques en temps réel
4. **Affiche** un rapport final à l'arrêt

**Code clé** :
```python
def display_alert(self, alert: dict):
    severity = alert['severity']
    
    # Codes couleur ANSI
    colors = {
        'CRITIQUE': '\033[91m',  # Rouge
        'ÉLEVÉE': '\033[93m',     # Jaune
        'MOYENNE': '\033[94m',    # Bleu
        'FAIBLE': '\033[92m'      # Vert
    }
    color = colors[severity]
    reset = '\033[0m'
    
    # Affichage formaté
    print("\n" + "="*70)
    print(f"{color}🚨 ALERTE SÉCURITÉ - Sévérité: {severity}{reset}")
    print("="*70)
    print(f"  Horodatage:     {alert['timestamp']}")
    print(f"  Flow ID:        {alert['flow_id']}")
    print(f"  Type d'attaque: {alert['alert_type']}")
    print(f"  Confiance:      {alert['confidence']:.1%}")
    print(f"  Score anomalie: {alert['anomaly_score']:.6f}")
    print("="*70)
    
    # Statistiques
    self.total_alerts += 1
    self.alerts_by_type[alert['alert_type']] = \
        self.alerts_by_type.get(alert['alert_type'], 0) + 1

def print_stats(self):
    elapsed = time.time() - self.start_time
    print("\n📊 STATISTIQUES DE SURVEILLANCE")
    print(f"  Durée:          {elapsed:.1f}s")
    print(f"  Total alertes:  {self.total_alerts}")
    print(f"  Taux:           {self.total_alerts / elapsed:.2f} alertes/s")
    print("\n  Répartition par type:")
    for attack_type, count in sorted(self.alerts_by_type.items()):
        pct = count / self.total_alerts * 100
        print(f"    - {attack_type:20}: {count:4} ({pct:.1f}%)")
```

**Pourquoi c'est important** :
- Feedback visuel immédiat
- Permet de voir le système fonctionner en temps réel
- Statistiques utiles pour l'évaluation

---

## Patterns Kafka utilisés

### 1. **Producer-Consumer Pattern**

Chaque composant implémente ce pattern :

```python
# Consumer (lit depuis un topic)
consumer = KafkaConsumer(
    'input-topic',
    bootstrap_servers='localhost:9093',
    group_id='unique-group-id',           # Important !
    value_deserializer=lambda m: json.loads(m.decode('utf-8')),
    auto_offset_reset='latest'            # Lit nouveaux messages uniquement
)

# Producer (écrit vers un topic)
producer = KafkaProducer(
    bootstrap_servers='localhost:9093',
    value_serializer=lambda v: json.dumps(v).encode('utf-8'),
    request_timeout_ms=30000,
    max_block_ms=30000
)

# Boucle de traitement
for message in consumer:
    # 1. Lire
    data = message.value
    
    # 2. Traiter
    result = process(data)
    
    # 3. Écrire
    producer.send('output-topic', result)
```

**Concepts clés** :
- **Consumer Group** : Permet le load balancing (plusieurs consumers lisent le même topic)
- **Deserializer** : Convertit bytes → dict Python
- **Serializer** : Convertit dict Python → bytes
- **auto_offset_reset** : `latest` = nouveaux messages, `earliest` = tous les messages

### 2. **Fan-out Pattern**

Un producer envoie vers plusieurs topics :

```python
# ThreatDetector envoie vers ids-alerts
producer.send('ids-alerts', alert)

# (Phase 2) LLMExplainer envoie vers ids-explanations
producer.send('ids-explanations', explanation)
```

### 3. **At-Least-Once Delivery**

Kafka garantit que chaque message est traité au moins une fois :

```python
# Consumer commit automatiquement après traitement
# Si crash avant commit → message retraité
for message in consumer:
    process(message.value)  # Si crash ici, message retraité
```

---

## Threading et Concurrence

### Architecture Multi-Thread

```python
def run_pipeline(...):
    threads = []
    
    # Thread 1: DataPreprocessor
    preprocessor = DataPreprocessor(kafka_server)
    t1 = threading.Thread(target=preprocessor.run, daemon=True)
    t1.start()
    threads.append(t1)
    
    # Thread 2: ThreatDetector
    detector = ThreatDetector(bootstrap_servers=kafka_server)
    t2 = threading.Thread(target=detector.run, daemon=True)
    t2.start()
    threads.append(t2)
    
    # Thread 3: AlertMonitor
    monitor = AlertMonitor(kafka_server)
    t3 = threading.Thread(target=monitor.run, daemon=True)
    t3.start()
    threads.append(t3)
    
    # Thread principal: TrafficProducer
    producer = TrafficProducer(dataset_path, kafka_server)
    producer.run(count, attack_ratio, delay)
```

**Concepts clés** :

1. **Daemon Thread** :
   ```python
   threading.Thread(..., daemon=True)
   ```
   - Se termine automatiquement quand le programme principal s'arrête
   - Pas besoin de `join()`
   - Idéal pour les services en arrière-plan

2. **Pourquoi plusieurs threads** :
   - Chaque consumer Kafka fait du **polling** (boucle infinie)
   - Sans threads, le premier consumer bloquerait les suivants
   - Les threads permettent le traitement **parallèle**

3. **Ordre d'exécution** :
   ```
   t=0s    Démarrer DataPreprocessor     (thread 1)
   t=1s    Démarrer ThreatDetector       (thread 2)
   t=2s    Démarrer AlertMonitor         (thread 3)
   t=3s    Démarrer TrafficProducer      (thread principal)
   ```
   - Les consumers démarrent d'abord (attendent les données)
   - Le producer démarre en dernier (génère les données)

4. **Gestion de l'arrêt** :
   ```python
   try:
       for message in consumer:
           process(message)
   except KeyboardInterrupt:
       print("Arrêt demandé")
   finally:
       consumer.close()
       producer.close()
   ```
   - `Ctrl+C` déclenche `KeyboardInterrupt`
   - `finally` garantit la fermeture propre

---

## Gestion des Données

### Format des Messages Kafka

Tous les messages sont en **JSON** :

```python
# Topic: ids-raw-data
{
  "flow_id": "sim_00000042",
  "features": [
    80.0,      # Port destination
    0.0,       # Flag FIN
    2.0,       # Nombre de paquets
    128.0,     # Taille moyenne des paquets
    # ... 33 autres features
  ],
  "label": "DDoS",
  "timestamp": 1703672400.0
}

# Topic: ids-features (après preprocessing)
{
  "flow_id": "sim_00000042",
  "features": [...],
  "label": "DDoS",
  "timestamp": 1703672400.0,
  "preprocessed_at": "2024-12-28T10:45:23.456789"  # AJOUTÉ
}

# Topic: ids-alerts (si attaque)
{
  "timestamp": "2024-12-28T10:45:23.456789",
  "flow_id": "sim_00000042",
  "alert_type": "DDoS",
  "confidence": 0.9534,
  "anomaly_score": 0.002341,
  "severity": "CRITIQUE",
  "true_label": "DDoS",
  "correct": true,
  "all_probabilities": {
    "Bots": 0.0012,
    "Brute Force": 0.0023,
    "DDoS": 0.9534,
    "DoS": 0.0312,
    "Normal Traffic": 0.0089,
    "Port Scanning": 0.0015,
    "Web Attacks": 0.0015
  },
  "top_3_classes": [
    ["DDoS", 0.9534],
    ["DoS", 0.0312],
    ["Normal Traffic", 0.0089]
  ]
}
```

### Sérialisation/Désérialisation

```python
# Sérialisation (Producer)
value_serializer=lambda v: json.dumps(v).encode('utf-8')
# dict → JSON string → bytes

# Désérialisation (Consumer)
value_deserializer=lambda m: json.loads(m.decode('utf-8'))
# bytes → JSON string → dict
```

**Pourquoi JSON** :
- Lisible par les humains
- Compatible avec tous les langages
- Facile à débugger
- Kafka supporte d'autres formats (Avro, Protobuf) mais JSON est plus simple

---

## Points Importants

### 1. **Séparation des Responsabilités**

Chaque composant a **une seule responsabilité** :
- `TrafficProducer` → Génération
- `DataPreprocessor` → Validation
- `ThreatDetector` → Détection
- `AlertMonitor` → Affichage

**Avantage** : Facile à modifier, tester, débugger

### 2. **Découplage via Kafka**

Les composants ne se connaissent pas :
```
Producer → Kafka ← Consumer
    ↓               ↑
Pas de lien direct !
```

**Avantage** :
- Peut ajouter/retirer des consumers sans modifier le producer
- Peut scaler indépendamment (ex: 3 ThreatDetector en parallèle)
- Peut remplacer un composant sans casser le système

### 3. **Flux Asynchrone**

```
Producer envoie un message
    ↓
Message dans Kafka (buffer)
    ↓
Consumer lit quand il est prêt
```

**Avantage** :
- Producer ne bloque pas en attendant le consumer
- Consumer peut traiter à son rythme
- Kafka gère la file d'attente

### 4. **Gestion d'Erreurs**

```python
try:
    for message in consumer:
        process(message)
except KeyboardInterrupt:
    print("Arrêt demandé")
except Exception as e:
    print(f"Erreur: {e}")
finally:
    consumer.close()
    producer.close()
```

**Important** :
- Toujours fermer les connexions Kafka
- Gérer `KeyboardInterrupt` pour arrêt propre
- Logger les erreurs pour debugging

### 5. **Configuration Kafka**

```python
# Timeouts importants
request_timeout_ms=30000,  # 30 secondes
max_block_ms=30000,        # 30 secondes
session_timeout_ms=30000   # 30 secondes
```

**Pourquoi** :
- Évite les timeouts prématurés
- Laisse le temps à Kafka de démarrer
- Gère la latence réseau

### 6. **Consumer Groups**

```python
KafkaConsumer(
    'topic',
    group_id='unique-group-id'  # IMPORTANT !
)
```

**Règle** : Chaque consumer doit avoir un `group_id` **différent** pour lire tous les messages

**Exemple** :
```
DataPreprocessor:  group_id='preprocessor-group'
ThreatDetector:    group_id='detector-group'
AlertMonitor:      group_id='monitor-group'
```

Si même `group_id` → load balancing (partage des messages)

---

## Résumé pour Débutants

### Comment lire le code

1. **Commencez par `run_pipeline()`** :
   - C'est le point d'entrée
   - Montre l'ordre de démarrage

2. **Lisez chaque classe dans l'ordre** :
   - `TrafficProducer` → génère
   - `DataPreprocessor` → valide
   - `ThreatDetector` → détecte
   - `AlertMonitor` → affiche

3. **Pour chaque classe, suivez ce pattern** :
   ```
   __init__  → Initialisation (Kafka clients)
   run()     → Boucle principale
   process() → Logique métier
   ```

### Concepts clés à retenir

1. **Kafka = File d'attente distribuée**
   - Producer envoie
   - Topic stocke
   - Consumer lit

2. **Threading = Parallélisme**
   - Plusieurs tâches en même temps
   - Chaque consumer dans son thread

3. **JSON = Format de données**
   - dict Python ↔ JSON ↔ bytes

4. **Pattern Producer-Consumer**
   - Lit depuis topic A
   - Traite
   - Écrit vers topic B

### Pour débugger

```python
# Ajouter des prints
print(f"[DEBUG] Message reçu: {message.value}")

# Vérifier les topics Kafka
docker exec kafka kafka-topics --list --bootstrap-server localhost:9092

# Lire un topic manuellement
docker exec -it kafka kafka-console-consumer \
  --topic ids-alerts \
  --bootstrap-server localhost:9092 \
  --from-beginning
```

---

## Ressources Supplémentaires

- **Kafka Documentation** : https://kafka.apache.org/documentation/
- **Threading Python** : https://docs.python.org/3/library/threading.html
- **Pattern Producer-Consumer** : https://en.wikipedia.org/wiki/Producer%E2%80%93consumer_problem

**Bon apprentissage !**