# Guide d'Intégration LLM - Phase 2

## Bienvenue !

Tu vas implémenter le **LLMExplainer**, le composant qui génère des explications en langage naturel pour les alertes de sécurité.

---

## Ton Objectif

Créer un composant qui :
1. Consomme depuis le topic `ids-alerts`
2. Génère des explications avec un LLM
3. Produit vers le topic `ids-explanations`

---

## Ce qui existe déjà (Phase 1)

```
Dataset → Producer → ids-raw-data → Preprocessor → ids-features → Detector → ids-alerts
                                                                                   ↓
                                                                          [TON TRAVAIL]
                                                                                   ↓
                                                                          ids-explanations
```

**Ce que tu reçois dans `ids-alerts`** :

```json
{
  "timestamp": "2024-12-28T10:45:23.456789",
  "flow_id": "sim_00000042",
  "alert_type": "DDoS",
  "confidence": 0.9534,
  "anomaly_score": 0.002341,
  "severity": "CRITIQUE",
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

---

## Étape 1 : Créer le fichier `llm_explainer.py`

### Structure de base

```python
#!/usr/bin/env python3
"""
LLM Explainer pour le Pipeline IDS
Génère des explications détaillées des alertes de sécurité
"""

import json
import time
from datetime import datetime
from typing import Dict
from kafka import KafkaProducer, KafkaConsumer

# TODO: Choisir un client LLM (voir Étape 2)
# from openai import OpenAI
# from anthropic import Anthropic


class LLMExplainer:
    """Génère des explications avec un LLM pour les alertes IDS"""
    
    def __init__(self, llm_config: dict, bootstrap_servers: str = 'localhost:9093'):
        """
        Args:
            llm_config: Configuration du LLM (provider, model, api_key, etc.)
            bootstrap_servers: Adresse du serveur Kafka
        """
        # Consumer depuis ids-alerts
        self.consumer = KafkaConsumer(
            'ids-alerts',
            bootstrap_servers=bootstrap_servers,
            group_id='llm-explainer-group',
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='latest',
            session_timeout_ms=30000
        )
        
        # Producer vers ids-explanations
        self.producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            request_timeout_ms=30000,
            max_block_ms=30000
        )
        
        # Configuration LLM
        self.llm_config = llm_config
        self.llm_client = self._init_llm(llm_config)
        
        # Statistiques
        self.total_explanations = 0
        self.total_tokens = 0
        self.start_time = time.time()
        
        print("[LLMExplainer] Connecté à Kafka")
        print(f"[LLMExplainer] LLM: {llm_config['provider']} - {llm_config['model']}")
    
    def _init_llm(self, config: dict):
        """Initialise le client LLM selon le provider"""
        provider = config['provider']
        
        if provider == 'openai':
            # TODO: Implémenter OpenAI
            pass
        elif provider == 'anthropic':
            # TODO: Implémenter Anthropic Claude
            pass
        elif provider == 'ollama':
            # TODO: Implémenter Ollama (local)
            pass
        else:
            raise ValueError(f"Provider non supporté: {provider}")
    
    def _build_prompt(self, alert: dict) -> str:
        """Construit le prompt pour le LLM"""
        # TODO: Voir Étape 3
        pass
    
    def generate_explanation(self, alert: dict) -> dict:
        """Génère une explication détaillée de l'alerte"""
        # TODO: Voir Étape 4
        pass
    
    def run(self):
        """Boucle principale du consumer"""
        print("[LLMExplainer] En attente d'alertes...")
        
        try:
            for message in self.consumer:
                alert = message.value
                
                print(f"\n[LLMExplainer] Traitement de l'alerte {alert['flow_id']}...")
                
                # Générer l'explication
                explanation = self.generate_explanation(alert)
                
                # Publier vers ids-explanations
                self.producer.send('ids-explanations', explanation)
                
                self.total_explanations += 1
                
                print(f"[LLMExplainer] ✓ Explication générée et publiée")
        
        except KeyboardInterrupt:
            print("\n[LLMExplainer] Arrêt demandé")
            self._print_stats()
        finally:
            self.consumer.close()
            self.producer.close()
    
    def _print_stats(self):
        """Affiche les statistiques"""
        elapsed = time.time() - self.start_time
        print("\n" + "="*70)
        print("📊 STATISTIQUES LLM EXPLAINER")
        print("="*70)
        print(f"  Durée:               {elapsed:.1f}s")
        print(f"  Explications:        {self.total_explanations}")
        print(f"  Tokens utilisés:     {self.total_tokens}")
        if self.total_explanations > 0:
            print(f"  Tokens/explication:  {self.total_tokens / self.total_explanations:.0f}")
            print(f"  Temps/explication:   {elapsed / self.total_explanations:.2f}s")
        print("="*70)


# Point d'entrée
if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='LLM Explainer pour IDS')
    parser.add_argument('--kafka-server', default='localhost:9093',
                        help='Adresse du serveur Kafka')
    parser.add_argument('--llm-provider', default='openai',
                        choices=['openai', 'anthropic', 'ollama'],
                        help='Provider LLM')
    parser.add_argument('--llm-model', default='gpt-4',
                        help='Modèle LLM à utiliser')
    
    args = parser.parse_args()
    
    # Configuration LLM
    llm_config = {
        'provider': args.llm_provider,
        'model': args.llm_model,
        'api_key': None,  # TODO: Charger depuis env variable
        'temperature': 0.3,
        'max_tokens': 1024
    }
    
    # Lancer l'explainer
    explainer = LLMExplainer(llm_config, args.kafka_server)
    explainer.run()
```

---

## Étape 2 : Choisir et Implémenter le LLM

### Option A : OpenAI GPT (Recommandé - Facile)

**Installation** :
```bash
pip install openai
```

**Implémentation** :
```python
from openai import OpenAI
import os

def _init_llm(self, config: dict):
    if config['provider'] == 'openai':
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY non définie dans l'environnement")
        
        return OpenAI(api_key=api_key)
    # ...

def generate_explanation(self, alert: dict) -> dict:
    # 1. Construire le prompt
    prompt = self._build_prompt(alert)
    
    # 2. Appeler l'API OpenAI
    start_time = time.time()
    response = self.llm_client.chat.completions.create(
        model=self.llm_config['model'],  # "gpt-4" ou "gpt-3.5-turbo"
        messages=[
            {"role": "system", "content": "Tu es un expert en cybersécurité spécialisé dans l'analyse d'intrusions réseau."},
            {"role": "user", "content": prompt}
        ],
        temperature=self.llm_config['temperature'],
        max_tokens=self.llm_config['max_tokens']
    )
    generation_time = (time.time() - start_time) * 1000  # ms
    
    # 3. Parser la réponse
    llm_response = response.choices[0].message.content
    explanation_data = json.loads(llm_response)
    
    # 4. Construire le message final
    explanation = {
        'timestamp': datetime.now().isoformat(),
        'flow_id': alert['flow_id'],
        'alert_reference': {
            'alert_type': alert['alert_type'],
            'confidence': alert['confidence'],
            'severity': alert['severity']
        },
        'explanation': explanation_data,
        'llm_metadata': {
            'model': self.llm_config['model'],
            'tokens_used': response.usage.total_tokens,
            'generation_time_ms': round(generation_time, 2)
        }
    }
    
    # Statistiques
    self.total_tokens += response.usage.total_tokens
    
    return explanation
```

**Configuration** :
```bash
export OPENAI_API_KEY="sk-..."
python llm_explainer.py --llm-provider openai --llm-model gpt-4
```

---

### Option B : Anthropic Claude

**Installation** :
```bash
pip install anthropic
```

**Implémentation** :
```python
from anthropic import Anthropic
import os

def _init_llm(self, config: dict):
    if config['provider'] == 'anthropic':
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY non définie")
        
        return Anthropic(api_key=api_key)
    # ...

def generate_explanation(self, alert: dict) -> dict:
    prompt = self._build_prompt(alert)
    
    start_time = time.time()
    response = self.llm_client.messages.create(
        model=self.llm_config['model'],  # "claude-3-sonnet-20240229"
        max_tokens=self.llm_config['max_tokens'],
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    generation_time = (time.time() - start_time) * 1000
    
    llm_response = response.content[0].text
    explanation_data = json.loads(llm_response)
    
    explanation = {
        'timestamp': datetime.now().isoformat(),
        'flow_id': alert['flow_id'],
        'alert_reference': {
            'alert_type': alert['alert_type'],
            'confidence': alert['confidence'],
            'severity': alert['severity']
        },
        'explanation': explanation_data,
        'llm_metadata': {
            'model': self.llm_config['model'],
            'tokens_used': response.usage.input_tokens + response.usage.output_tokens,
            'generation_time_ms': round(generation_time, 2)
        }
    }
    
    self.total_tokens += response.usage.input_tokens + response.usage.output_tokens
    
    return explanation
```

**Configuration** :
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
python llm_explainer.py --llm-provider anthropic --llm-model claude-3-sonnet-20240229
```

---

### Option C : Ollama (Local - Gratuit)

**Installation** :
```bash
# Installer Ollama
curl https://ollama.ai/install.sh | sh

# Télécharger un modèle
ollama pull llama2
```

**Implémentation** :
```python
import requests

def _init_llm(self, config: dict):
    if config['provider'] == 'ollama':
        # Pas besoin de client, juste l'URL
        return {'url': 'http://localhost:11434/api/generate'}
    # ...

def generate_explanation(self, alert: dict) -> dict:
    prompt = self._build_prompt(alert)
    
    start_time = time.time()
    response = requests.post(self.llm_client['url'], json={
        'model': self.llm_config['model'],  # "llama2"
        'prompt': prompt,
        'stream': False
    })
    generation_time = (time.time() - start_time) * 1000
    
    llm_response = response.json()['response']
    explanation_data = json.loads(llm_response)
    
    explanation = {
        'timestamp': datetime.now().isoformat(),
        'flow_id': alert['flow_id'],
        'alert_reference': {
            'alert_type': alert['alert_type'],
            'confidence': alert['confidence'],
            'severity': alert['severity']
        },
        'explanation': explanation_data,
        'llm_metadata': {
            'model': self.llm_config['model'],
            'tokens_used': -1,  # Ollama ne renvoie pas les tokens
            'generation_time_ms': round(generation_time, 2)
        }
    }
    
    return explanation
```

**Configuration** :
```bash
ollama serve  # Démarre le serveur
python llm_explainer.py --llm-provider ollama --llm-model llama2
```

---

## Étape 3 : Construire le Prompt

```python
def _build_prompt(self, alert: dict) -> str:
    """Construit un prompt structuré pour le LLM"""
    
    # Descriptions des types d'attaques
    attack_descriptions = {
        'DDoS': "Distributed Denial of Service - Saturation des ressources réseau par des requêtes massives",
        'DoS': "Denial of Service - Saturation des ressources par un attaquant unique",
        'Brute Force': "Tentatives répétées de connexion pour deviner des identifiants",
        'Port Scanning': "Scan des ports pour identifier les services vulnérables",
        'Web Attacks': "Attaques web (SQL Injection, XSS, etc.)",
        'Bots': "Activité automatisée malveillante (botnets)"
    }
    
    # Niveaux de risque selon la sévérité
    risk_levels = {
        'CRITIQUE': "Risque critique nécessitant une action immédiate",
        'ÉLEVÉE': "Risque élevé nécessitant une attention rapide",
        'MOYENNE': "Risque modéré à surveiller",
        'FAIBLE': "Risque faible, surveillance recommandée"
    }
    
    # Construire le prompt
    prompt = f"""Tu es un expert en cybersécurité. Analyse cette alerte de sécurité et génère une explication détaillée.

## ALERTE DÉTECTÉE

**Type d'attaque:** {alert['alert_type']}
**Description:** {attack_descriptions.get(alert['alert_type'], 'Type inconnu')}

**Confiance de détection:** {alert['confidence']:.1%}
**Sévérité:** {alert['severity']}
**Niveau de risque:** {risk_levels[alert['severity']]}
**Score d'anomalie:** {alert['anomaly_score']:.6f}

## ANALYSE DU MODÈLE

**Top 3 prédictions:**
"""
    
    # Ajouter les top 3 classes
    for i, (class_name, prob) in enumerate(alert['top_3_classes'], 1):
        prompt += f"\n{i}. {class_name}: {prob:.1%}"
    
    prompt += f"""

**Toutes les probabilités:**
"""
    
    # Ajouter toutes les probabilités triées
    for class_name, prob in sorted(alert['all_probabilities'].items(), key=lambda x: x[1], reverse=True):
        prompt += f"\n- {class_name}: {prob:.1%}"
    
    prompt += """

## TÂCHE

Génère une explication complète en JSON avec la structure suivante:

{
  "summary": "Résumé en une phrase courte et claire",
  "technical_analysis": "Analyse technique détaillée : pourquoi cette attaque a été détectée, quels patterns réseau sont caractéristiques",
  "why_detected": "Explication des 3 principaux indicateurs qui ont conduit à cette détection",
  "risk_assessment": "Évaluation du risque : impact potentiel sur le système et les services",
  "recommended_actions": [
    "Action 1 spécifique et concrète",
    "Action 2 spécifique et concrète",
    "Action 3 spécifique et concrète",
    "Action 4 spécifique et concrète (optionnelle)",
    "Action 5 spécifique et concrète (optionnelle)"
  ]
}

**IMPORTANT:**
- Réponds UNIQUEMENT en JSON valide, sans texte avant ou après
- Sois précis et technique dans l'analyse
- Les actions recommandées doivent être concrètes et actionnables
- Adapte ton analyse à la sévérité de l'alerte
"""
    
    return prompt
```

---

## Étape 4 : Tester l'Explainer

### Test Unitaire

Créez `test_llm_explainer.py` :

```python
#!/usr/bin/env python3
"""Tests pour le LLM Explainer"""

import json
from llm_explainer import LLMExplainer

def test_prompt_building():
    """Test la construction du prompt"""
    llm_config = {
        'provider': 'openai',
        'model': 'gpt-4',
        'api_key': 'test',
        'temperature': 0.3,
        'max_tokens': 1024
    }
    
    explainer = LLMExplainer(llm_config)
    
    # Alerte de test
    alert = {
        'alert_type': 'DDoS',
        'confidence': 0.95,
        'severity': 'CRITIQUE',
        'anomaly_score': 0.002341,
        'all_probabilities': {
            'DDoS': 0.95,
            'DoS': 0.03,
            'Normal Traffic': 0.02
        },
        'top_3_classes': [
            ['DDoS', 0.95],
            ['DoS', 0.03],
            ['Normal Traffic', 0.02]
        ]
    }
    
    # Tester le prompt
    prompt = explainer._build_prompt(alert)
    
    print("Prompt généré:")
    print("="*70)
    print(prompt)
    print("="*70)
    
    # Vérifications
    assert 'DDoS' in prompt
    assert '95' in prompt or '95.0%' in prompt
    assert 'CRITIQUE' in prompt
    print("\n✓ Test du prompt réussi")

def test_explanation_format():
    """Test le format de l'explication"""
    # Exemple de réponse LLM attendue
    llm_response = {
        'summary': 'Attaque DDoS détectée avec confiance élevée',
        'technical_analysis': 'Pattern de trafic anormal...',
        'why_detected': 'Indicateurs 1, 2, 3...',
        'risk_assessment': 'Risque critique...',
        'recommended_actions': [
            'Action 1',
            'Action 2',
            'Action 3'
        ]
    }
    
    # Vérifier la structure
    assert 'summary' in llm_response
    assert 'technical_analysis' in llm_response
    assert 'why_detected' in llm_response
    assert 'risk_assessment' in llm_response
    assert 'recommended_actions' in llm_response
    assert isinstance(llm_response['recommended_actions'], list)
    assert len(llm_response['recommended_actions']) >= 3
    
    print("✓ Test du format réussi")

if __name__ == '__main__':
    print("Tests du LLM Explainer\n")
    test_prompt_building()
    test_explanation_format()
    print("\n✅ Tous les tests réussis")
```

**Exécuter** :
```bash
python test_llm_explainer.py
```

---

## Étape 5 : Intégrer dans le Pipeline

Modifiez `automated_ids_pipeline.py` :

```python
from llm_explainer import LLMExplainer

def run_pipeline(count, attack_ratio, delay, dataset_path, kafka_server):
    # ... code existant ...
    
    # 4. LLMExplainer (Phase 2)
    llm_config = {
        'provider': 'openai',  # ou 'anthropic', 'ollama'
        'model': 'gpt-4',
        'api_key': None,  # Chargé depuis env
        'temperature': 0.3,
        'max_tokens': 1024
    }
    
    explainer = LLMExplainer(llm_config, kafka_server)
    t4 = threading.Thread(target=explainer.run, daemon=True)
    t4.start()
    threads.append(t4)
    time.sleep(1)
    
    print("\n[PIPELINE] Tous les composants sont démarrés (y compris LLM) ✓\n")
    # ... reste du code ...
```

---

## Étape 6 : Tester le Pipeline Complet

```bash
# Terminal 1: Lancer le pipeline complet
export OPENAI_API_KEY="sk-..."
python automated_ids_pipeline.py --count 50 --attack-ratio 0.3 --delay 0.1

# Terminal 2: Observer les explications
docker exec -it kafka kafka-console-consumer \
  --topic ids-explanations \
  --bootstrap-server localhost:9092 \
  --from-beginning
```

**Résultat attendu dans `ids-explanations`** :

```json
{
  "timestamp": "2024-12-28T11:30:45.123456",
  "flow_id": "sim_00000042",
  "alert_reference": {
    "alert_type": "DDoS",
    "confidence": 0.9534,
    "severity": "CRITIQUE"
  },
  "explanation": {
    "summary": "Attaque DDoS massive détectée avec une confiance de 95.3%, indiquant un flood de requêtes coordonné visant à saturer les ressources réseau.",
    "technical_analysis": "Le modèle a identifié des signatures caractéristiques d'une attaque DDoS distribuée : volume de trafic anormalement élevé (10x la normale), distribution temporelle en burst, multiples sources IP, taux de paquets/seconde extrêmement élevé, et durées de connexion microscopiques typiques d'un flood SYN.",
    "why_detected": "Trois indicateurs principaux ont déclenché l'alerte : (1) Taux de paquets par seconde 15 fois supérieur à la baseline normale, (2) Distribution anormale des ports sources suggérant une randomisation automatisée, (3) Score d'anomalie de 0.002341 nettement au-dessus du seuil de détection de 0.001.",
    "risk_assessment": "Risque CRITIQUE. Cette attaque peut rendre les services indisponibles pour les utilisateurs légitimes, causer des pertes financières significatives, et potentiellement masquer d'autres activités malveillantes. L'impact estimé est une interruption totale de service pendant la durée de l'attaque.",
    "recommended_actions": [
      "Activer immédiatement les règles de rate limiting sur le firewall pour limiter les connexions par IP source",
      "Bloquer les adresses IP sources identifiées via ACL ou blacklisting automatique",
      "Contacter le fournisseur d'accès Internet pour activer le filtrage DDoS au niveau FAI",
      "Notifier l'équipe SOC/SecOps avec priorité P1 pour intervention immédiate",
      "Vérifier la disponibilité des services critiques et activer les plans de continuité si nécessaire"
    ]
  },
  "llm_metadata": {
    "model": "gpt-4",
    "tokens_used": 456,
    "generation_time_ms": 2340.5
  }
}
```

---

## Checklist de Complétion

- [ ] llm_explainer.py créé avec la classe LLMExplainer
- [ ] Client LLM initialisé (OpenAI, Anthropic, ou Ollama)
- [ ] Fonction _build_prompt() implémentée
- [ ] Fonction generate_explanation() implémentée
- [ ] Consommation depuis ids-alerts fonctionne
- [ ] Production vers ids-explanations fonctionne
- [ ] Tests unitaires créés et passent
- [ ] Intégration dans automated_ids_pipeline.py
- [ ] Pipeline complet testé de bout en bout
- [ ] Documentation mise à jour
- [ ] Gestion des erreurs (timeout, quota LLM, etc.)
- [ ] Statistiques affichées (tokens, temps de génération)

---

## Ressources

- **OpenAI API** : https://platform.openai.com/docs/api-reference
- **Anthropic Claude** : https://docs.anthropic.com/
- **Ollama** : https://ollama.ai/
- **Kafka Python** : https://kafka-python.readthedocs.io/

---

## Dépannage

### Erreur : "OPENAI_API_KEY not found"

```bash
export OPENAI_API_KEY="sk-..."
```

### Erreur : "Kafka timeout"

Vérifier que Kafka est démarré :
```bash
docker ps | grep kafka
```

### Erreur : "Rate limit exceeded"

Le LLM a atteint sa limite de requêtes. Attendre ou :
```python
# Ajouter un délai entre les appels
time.sleep(1)
```

### Erreur : "JSON decode error"

Le LLM n'a pas retourné du JSON valide. Améliorer le prompt :
```python
prompt += "\n\nRéponds UNIQUEMENT en JSON valide, sans markdown ni texte additionnel."
```

---

## Résultat Final

Après implémentation, ton pipeline complet ressemblera à :

```
Dataset → Producer → ids-raw-data → Preprocessor → ids-features → Detector → ids-alerts → LLMExplainer → ids-explanations
                                                                                   ↓
                                                                              AlertMonitor
                                                                            (affichage console)
```

**Félicitations, tu as complété la Phase 2 !**