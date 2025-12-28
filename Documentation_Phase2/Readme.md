# Documentation du Pipeline IDS Kafka - Phase 1 Complétée

## Vue d'Ensemble

Ce document explique l'architecture du pipeline de détection d'intrusions en temps réel implémenté avec Apache Kafka, le modèle AutoencoderIDS, et prépare la phase 2 (intégration LLM).

---

## Architecture Actuelle (Phase 1)

```
┌─────────────────────────────────────────────────────────────────┐
│                    PIPELINE IDS KAFKA - PHASE 1                 │
└─────────────────────────────────────────────────────────────────┘

Dataset CSV (CICIDS2017)
    │
    ▼
┌──────────────────┐
│ TrafficProducer  │  → Simule le trafic réseau
│  (Générateur)    │     Lit depuis cicids2017_cleaned.csv
└────────┬─────────┘
         │ produce
         ▼
    ┌─────────────────┐
    │ ids-raw-data    │  Topic Kafka (3 partitions)
    │  (Topic)        │  Format: {flow_id, features[37], label, timestamp}
    └────────┬────────┘
             │ consume
             ▼
    ┌──────────────────┐
    │ DataPreprocessor │  → Valide et transforme les données
    │  (Consumer/      │     Normalisation, validation
    │   Producer)      │
    └────────┬─────────┘
             │ produce
             ▼
    ┌─────────────────┐
    │ ids-features    │  Topic Kafka (3 partitions)
    │  (Topic)        │  Format: {flow_id, features, label, preprocessed_at}
    └────────┬────────┘
             │ consume
             ▼
    ┌──────────────────┐
    │ ThreatDetector   │  → Détection avec AutoencoderIDS
    │  (Consumer/      │     Prédiction + Calcul de sévérité
    │   Producer)      │     PUBLIE UNIQUEMENT SI ATTAQUE
    └────────┬─────────┘
             │ produce (si attaque)
             ▼
    ┌─────────────────┐
    │ ids-alerts      │  Topic Kafka (1 partition)
    │  (Topic)        │  Format: {alert_type, confidence, severity, ...}
    └────────┬────────┘
             │ consume
             ▼
    ┌──────────────────┐
    │ AlertMonitor     │  → Affichage console avec couleurs
    │  (Consumer)      │     Statistiques en temps réel
    └──────────────────┘

    Phase 2 (À IMPLÉMENTER)
             │
             ▼
    ┌──────────────────┐
    │ LLMExplainer     │  → Génère explications avec LLM
    │  (Consumer/      │     Consomme depuis ids-alerts
    │   Producer)      │     Produit vers ids-explanations
    └────────┬─────────┘
             │ produce
             ▼
    ┌─────────────────┐
    │ids-explanations │  Topic Kafka (1 partition)
    │  (Topic)        │  Format: {explanation_text, analysis, ...}
    └─────────────────┘
```

---

## Composants du Système

### 1. **TrafficProducer** (Simulateur de Trafic)

**Rôle** : Génère des flux réseau depuis le dataset CICIDS2017 et les envoie vers Kafka.

**Fonctionnement** :
- Lit le fichier CSV `cicids2017_cleaned.csv`
- Sélectionne aléatoirement des flux (normal + attaques)
- Respecte le ratio d'attaques spécifié (`--attack-ratio`)
- Ajoute un délai configurable entre les messages (`--delay`)

**Topic de sortie** : `ids-raw-data`

**Format des messages** :
```json
{
  "flow_id": "sim_00000042",
  "features": [80.0, 0.0, 2.0, 128.0, ...],  // 37 features
  "label": "DDoS",
  "timestamp": 1703672400.0
}
```

**Code clé** :
```python
for i, flow in enumerate(self.simulator.generate_stream(count, attack_ratio)):
    self.producer.send('ids-raw-data', flow.to_dict())
    time.sleep(delay)
```

---

### 2. **DataPreprocessor** (Préprocesseur)

**Rôle** : Valide et transforme les données brutes avant la détection.

**Fonctionnement** :
- Consomme depuis `ids-raw-data`
- Valide la structure des données
- Ajoute des métadonnées (timestamp de préprocessing)
- Produit vers `ids-features`

**Topics** :
- **Input** : `ids-raw-data`
- **Output** : `ids-features`

**Format de sortie** :
```json
{
  "flow_id": "sim_00000042",
  "features": [80.0, 0.0, 2.0, ...],
  "label": "DDoS",
  "timestamp": 1703672400.0,
  "preprocessed_at": "2024-12-28T10:45:23.456789"
}
```

**Améliorations possibles** :
- Validation des valeurs (min/max, NaN)
- Normalisation supplémentaire
- Feature engineering

---

### 3. **ThreatDetector** (Détecteur de Menaces)

**Rôle** : Applique le modèle AutoencoderIDS et **publie uniquement les alertes d'attaques**.

**Fonctionnement** :
1. Consomme depuis `ids-features`
2. Charge le modèle PyTorch `autoencoder_ids_v1.1.0.pt`
3. Prédit la classe (7 types : Bots, Brute Force, DDoS, DoS, Normal, Port Scanning, Web Attacks)
4. Calcule la confiance et le score d'anomalie
5. Détermine la sévérité (CRITIQUE, ÉLEVÉE, MOYENNE, FAIBLE)
6. **PUBLIE VERS `ids-alerts` UNIQUEMENT SI ATTAQUE DÉTECTÉE**

**Topics** :
- **Input** : `ids-features`
- **Output** : `ids-alerts` (UNIQUEMENT pour les attaques)

**Format de sortie** :
```json
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
  ],
  "features_summary": {
    "preprocessed_at": "2024-12-28T10:45:23.123456",
    "original_timestamp": 1703672400.0
  }
}
```

**Calcul de la sévérité** :
```python
def _calculate_severity(self, prediction) -> str:
    if prediction.confidence >= 0.9:
        return "CRITIQUE"      # 90%+ confiance
    elif prediction.confidence >= 0.7:
        return "ÉLEVÉE"        # 70-90% confiance
    elif prediction.confidence >= 0.5:
        return "MOYENNE"       # 50-70% confiance
    else:
        return "FAIBLE"        # <50% confiance
```

**IMPORTANT** :
- Si le trafic est Normal, aucun message n'est envoyé vers `ids-alerts`
- Seules les attaques détectées génèrent des alertes
- Les explications seront générées par le LLMExplainer (Phase 2)

---

### 4. **AlertMonitor** (Moniteur d'Alertes)

**Rôle** : Affiche les alertes en temps réel dans la console avec formatage et statistiques.

**Fonctionnement** :
- Consomme depuis `ids-alerts`
- Affiche chaque alerte avec code couleur selon la sévérité
- Calcule des statistiques en temps réel
- Affiche un rapport final à l'arrêt (Ctrl+C)

**Topic d'entrée** : `ids-alerts`

**Affichage console** :
```
======================================================================
🚨 ALERTE SÉCURITÉ - Sévérité: CRITIQUE
======================================================================
  Horodatage:     2024-12-28T10:45:23.456789
  Flow ID:        sim_00000042
  Type d'attaque: DDoS
  Confiance:      94.7%
  Score anomalie: 0.002341
  Label réel:     DDoS
  Prédiction:     ✓ CORRECTE
======================================================================
```

**Codes couleur** :
- Rouge : CRITIQUE (confiance ≥90%)
- Jaune : ÉLEVÉE (confiance 70-90%)
- Bleu : MOYENNE (confiance 50-70%)
- Vert : FAIBLE (confiance <50%)

**Statistiques finales** :
```
STATISTIQUES DE SURVEILLANCE
======================================================================
  Durée:          102.3s
  Total alertes:  287
  Taux:           2.81 alertes/s

  Répartition par type:
    - DDoS                :  112 (39.0%)
    - DoS                 :   78 (27.2%)
    - Port Scanning       :   45 (15.7%)
    - Web Attacks         :   32 (11.1%)
    - Brute Force         :   15 (5.2%)
    - Bots                :    5 (1.7%)
======================================================================
```

---

## Flux de Données Détaillé

### Étape 1 : Génération du Trafic
```
TrafficProducer
    ↓
Lit cicids2017_cleaned.csv (500 flux)
    ↓
Sélectionne aléatoirement selon attack_ratio
    ↓
Envoie vers ids-raw-data avec délai
```

### Étape 2 : Préprocessing
```
DataPreprocessor consomme ids-raw-data
    ↓
Valide la structure
    ↓
Ajoute timestamp de preprocessing
    ↓
Produit vers ids-features
```

### Étape 3 : Détection
```
ThreatDetector consomme ids-features
    ↓
Charge features dans le modèle AutoencoderIDS
    ↓
Prédiction : classe + confiance + anomaly_score
    ↓
Calcule la sévérité
    ↓
SI attaque → Envoie vers ids-alerts
SI normal  → Rien (log console uniquement)
```

### Étape 4 : Monitoring
```
AlertMonitor consomme ids-alerts
    ↓
Affiche avec code couleur
    ↓
Met à jour les statistiques
    ↓
Ctrl+C → Affiche rapport final
```

---

## Utilisation

### Commandes Principales

```bash
# Test rapide (200 flux, 20% attaques, délai 0.05s)
python automated_ids_pipeline.py --count 200 --attack-ratio 0.2 --delay 0.05

# Test standard (1000 flux, 30% attaques)
python automated_ids_pipeline.py --count 1000 --attack-ratio 0.3 --delay 0.1

# Test intensif (5000 flux, 50% attaques, rapide)
python automated_ids_pipeline.py --count 5000 --attack-ratio 0.5 --delay 0.01

# Spécifier le serveur Kafka
python automated_ids_pipeline.py --count 500 --kafka-server localhost:9092
```

### Arguments Disponibles

| Argument | Type | Défaut | Description |
|----------|------|--------|-------------|
| `--count` | int | 1000 | Nombre de flux à traiter |
| `--attack-ratio` | float | 0.3 | Proportion d'attaques (0.0-1.0) |
| `--delay` | float | 0.1 | Délai entre messages (secondes) |
| `--dataset` | str | ../dataset/cicids2017_cleaned.csv | Chemin du dataset |
| `--kafka-server` | str | localhost:9093 | Adresse Kafka |

---

## Topics Kafka

| Topic | Partitions | Rôle | Format |
|-------|-----------|------|--------|
| **ids-raw-data** | 3 | Données brutes du simulateur | {flow_id, features, label, timestamp} |
| **ids-features** | 3 | Features préprocessées | {flow_id, features, label, preprocessed_at} |
| **ids-alerts** | 1 | Alertes d'attaques uniquement | {alert_type, confidence, severity, ...} |
| **ids-explanations** | 1 | Explications LLM (Phase 2) | {explanation_text, analysis, ...} |

---

## Ce que fait le fichier `automated_ids_pipeline.py`

### 1. **Architecture Multi-Thread**

Le script utilise le **threading Python** pour exécuter simultanément :
- DataPreprocessor (thread daemon)
- ThreatDetector (thread daemon)
- AlertMonitor (thread daemon)
- TrafficProducer (thread principal)

**Pourquoi des threads ?**
- Permet le traitement en **temps réel**
- Chaque composant fonctionne **indépendamment**
- Simule un véritable système distribué

```python
# Lancement des threads
t1 = threading.Thread(target=preprocessor.run, daemon=True)
t2 = threading.Thread(target=detector.run, daemon=True)
t3 = threading.Thread(target=monitor.run, daemon=True)

t1.start()
t2.start()
t3.start()
```

### 2. **Pattern Producer-Consumer de Kafka**

Chaque composant implémente le pattern **Producer-Consumer** :

```python
class DataPreprocessor:
    def __init__(self):
        # Consumer pour lire
        self.consumer = KafkaConsumer('ids-raw-data', ...)
        
        # Producer pour écrire
        self.producer = KafkaProducer(...)
    
    def run(self):
        for message in self.consumer:
            # Traiter
            processed = self.process_flow(message.value)
            
            # Publier
            self.producer.send('ids-features', processed)
```

### 3. **Gestion des Erreurs et Arrêt Propre**

```python
try:
    for message in self.consumer:
        # Traitement
        pass
except KeyboardInterrupt:
    print("Arrêt demandé")
finally:
    self.consumer.close()
    self.producer.close()
```

### 4. **Sérialisation JSON**

Tous les messages Kafka sont sérialisés en JSON :

```python
KafkaProducer(
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

KafkaConsumer(
    value_deserializer=lambda m: json.loads(m.decode('utf-8'))
)
```

---

## Phase 2 : Intégration LLM (À FAIRE)

### Objectif

Créer un composant **LLMExplainer** qui :
1. **Consomme** depuis `ids-alerts`
2. **Génère des explications** en langage naturel avec un LLM
3. **Produit** vers `ids-explanations`

### Architecture Cible

```
ids-alerts (alertes brutes)
    ↓
LLMExplainer
    │
    ├─ Lit l'alerte
    ├─ Extrait les features importantes
    ├─ Appelle un LLM (GPT, Claude, Llama, etc.)
    ├─ Génère explication détaillée
    │
    ↓
ids-explanations (explications en langage naturel)
```

### Format de Sortie Attendu (`ids-explanations`)

```json
{
  "timestamp": "2024-12-28T10:45:25.789012",
  "flow_id": "sim_00000042",
  "alert_reference": {
    "alert_type": "DDoS",
    "confidence": 0.9534,
    "severity": "CRITIQUE"
  },
  "explanation": {
    "summary": "Une attaque DDoS a été détectée avec une confiance très élevée de 95.3%.",
    "technical_analysis": "Le modèle a identifié des patterns caractéristiques d'une attaque DDoS : volume de trafic anormal, taux de paquets élevé, et signatures réseau typiques d'un flood de requêtes.",
    "why_detected": "Les 3 indicateurs principaux sont : 1) Taux de paquets/seconde 10x supérieur à la normale, 2) Durée de connexion extrêmement courte, 3) Distribution anormale des ports sources.",
    "risk_assessment": "Risque critique. Cette attaque pourrait saturer les ressources réseau et rendre les services indisponibles.",
    "recommended_actions": [
      "Bloquer immédiatement l'adresse IP source",
      "Activer les règles de rate limiting",
      "Notifier l'équipe SOC",
      "Vérifier la disponibilité des services critiques"
    ]
  },
  "llm_metadata": {
    "model": "claude-3-sonnet",
    "tokens_used": 245,
    "generation_time_ms": 1250
  }
}
```

---

## 📝 Tâches pour le Prochain Membre de l'Équipe (Phase 2)

### Mission : Implémenter le Composant LLMExplainer

Vous devez créer un nouveau fichier `llm_explainer.py` qui :

### 1. **Classe LLMExplainer**

```python
class LLMExplainer:
    """Génère des explications détaillées des alertes avec un LLM"""
    
    def __init__(self, llm_config: dict, bootstrap_servers: str):
        # Consumer depuis ids-alerts
        self.consumer = KafkaConsumer('ids-alerts', ...)
        
        # Producer vers ids-explanations
        self.producer = KafkaProducer(...)
        
        # Client LLM (OpenAI, Anthropic, Hugging Face, etc.)
        self.llm_client = self._init_llm(llm_config)
    
    def generate_explanation(self, alert: dict) -> dict:
        """Génère une explication avec le LLM"""
        # 1. Construire le prompt
        prompt = self._build_prompt(alert)
        
        # 2. Appeler le LLM
        response = self.llm_client.generate(prompt)
        
        # 3. Parser la réponse
        explanation = self._parse_llm_response(response)
        
        return explanation
    
    def run(self):
        """Boucle principale"""
        for message in self.consumer:
            alert = message.value
            
            # Générer explication
            explanation = self.generate_explanation(alert)
            
            # Publier
            self.producer.send('ids-explanations', explanation)
```

### 2. **Construction du Prompt LLM**

Créez une fonction qui transforme l'alerte en prompt structuré :

```python
def _build_prompt(self, alert: dict) -> str:
    return f"""
Tu es un expert en cybersécurité. Analyse cette alerte IDS et génère une explication détaillée.

ALERTE:
- Type: {alert['alert_type']}
- Confiance: {alert['confidence']:.1%}
- Sévérité: {alert['severity']}
- Score d'anomalie: {alert['anomaly_score']:.6f}

PROBABILITÉS:
{self._format_probabilities(alert['all_probabilities'])}

CONTEXTE:
- Flow ID: {alert['flow_id']}
- Timestamp: {alert['timestamp']}

GÉNÈRE:
1. Un résumé en une phrase
2. Une analyse technique détaillée
3. Pourquoi cette attaque a été détectée
4. Évaluation du risque
5. Actions recommandées (liste de 3-5 actions)

Réponds en JSON avec la structure suivante:
{{
  "summary": "...",
  "technical_analysis": "...",
  "why_detected": "...",
  "risk_assessment": "...",
  "recommended_actions": ["action1", "action2", ...]
}}
"""
```

### 3. **Intégration LLM**

Choisissez **un** LLM parmi :

#### Option A : **OpenAI GPT** (Recommandé)
```python
from openai import OpenAI

client = OpenAI(api_key="votre-clé")

response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": prompt}],
    temperature=0.3
)

explanation = json.loads(response.choices[0].message.content)
```

#### Option B : **Anthropic Claude**
```python
from anthropic import Anthropic

client = Anthropic(api_key="votre-clé")

response = client.messages.create(
    model="claude-3-sonnet-20240229",
    max_tokens=1024,
    messages=[{"role": "user", "content": prompt}]
)

explanation = json.loads(response.content[0].text)
```

#### Option C : **Hugging Face (Llama, Mistral, etc.)**
```python
from transformers import AutoTokenizer, AutoModelForCausalLM

tokenizer = AutoTokenizer.from_pretrained("meta-llama/Llama-2-7b-chat-hf")
model = AutoModelForCausalLM.from_pretrained("meta-llama/Llama-2-7b-chat-hf")

inputs = tokenizer(prompt, return_tensors="pt")
outputs = model.generate(**inputs, max_new_tokens=512)
explanation = tokenizer.decode(outputs[0])
```

#### Option D : **Ollama (Local)**
```python
import requests

response = requests.post('http://localhost:11434/api/generate', json={
    'model': 'llama2',
    'prompt': prompt,
    'stream': False
})

explanation = json.loads(response.json()['response'])
```

### 4. **Fichier de Configuration**

Créez llm_config.json :

```json
{
  "provider": "openai",
  "model": "gpt-4",
  "api_key_env": "OPENAI_API_KEY",
  "temperature": 0.3,
  "max_tokens": 1024,
  "timeout": 30
}
```

### 5. **Tests**

Créez test_llm_explainer.py :

```python
def test_explanation_generation():
    """Test la génération d'explication"""
    explainer = LLMExplainer(config)
    
    # Alerte de test
    alert = {
        'alert_type': 'DDoS',
        'confidence': 0.95,
        'severity': 'CRITIQUE',
        'anomaly_score': 0.002341,
        'all_probabilities': {...}
    }
    
    # Générer explication
    explanation = explainer.generate_explanation(alert)
    
    # Vérifications
    assert 'summary' in explanation
    assert 'technical_analysis' in explanation
    assert len(explanation['recommended_actions']) >= 3
    
    print("✓ Test réussi")
```

### 6. **Intégration dans le Pipeline**

Modifiez automated_ids_pipeline.py :

```python
from llm_explainer import LLMExplainer

def run_pipeline(...):
    # ...composants existants...
    
    # 4. LLMExplainer (Phase 2)
    explainer = LLMExplainer(llm_config, kafka_server)
    t4 = threading.Thread(target=explainer.run, daemon=True)
    t4.start()
    threads.append(t4)
    
    # ...reste du code...
```

---

## Diagramme de Séquence Complet (Phase 1 + Phase 2)

```
TrafficProducer     DataPreprocessor    ThreatDetector      AlertMonitor      LLMExplainer
       │                   │                   │                   │                 │
       │─── flow ─────────►│                   │                   │                 │
       │                   │                   │                   │                 │
       │                   │─── features ─────►│                   │                 │
       │                   │                   │                   │                 │
       │                   │                   │─ predict()        │                 │
       │                   │                   │                   │                 │
       │                   │                   │─── alert ────────►│                 │
       │                   │                   │                   │                 │
       │                   │                   │                   │─ display        │
       │                   │                   │                   │                 │
       │                   │                   │─── alert ─────────────────────────►│
       │                   │                   │                   │                 │
       │                   │                   │                   │                 │─ LLM call
       │                   │                   │                   │                 │
       │                   │                   │                   │◄─ explanation ──│
       │                   │                   │                   │                 │
```

---

## Critères de Succès (Phase 2)

LLMExplainer consomme correctement depuis ids-alerts
Génère des explications cohérentes et détaillées
Produit vers ids-explanations avec format JSON valide
Gère les erreurs LLM (timeout, quota, etc.)
Affiche les explications dans la console ou dashboard
Tests unitaires passent
Documentation mise à jour

---

## Dépendances Supplémentaires (Phase 2)

Ajoutez à `requirements.txt` :

```txt
# Existant
kafka-python>=2.0.2
torch>=2.0.0
numpy>=1.24.0
pandas>=2.0.0
scikit-learn>=1.3.0
joblib>=1.3.0

# Phase 2 - LLM
openai>=1.0.0              # Si OpenAI
anthropic>=0.18.0          # Si Claude
transformers>=4.30.0       # Si Hugging Face
torch>=2.0.0               # Si modèles locaux
requests>=2.31.0           # Si Ollama
```

---

## Contact et Support

Pour toute question sur l'implémentation :
- Consulter le code existant dans `automated_ids_pipeline.py`
- Lire la doc Kafka : https://kafka.apache.org/documentation/
- Exemples LLM : Voir section "Intégration LLM" ci-dessus

**Bonne chance pour la Phase 2 !**