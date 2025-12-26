
#  IDS-Autoencoder-Classifier-DL-CICIDS

## État d'Avancement du Projet

* [x] **Phase 1** : Entraînement du modèle hybride (Autoencoder + Classifier) - **Terminé**
* [x] **Phase 2** : Exportation des artefacts (Modèle, Scaler, Labels) - **Terminé**
* [ ] **Phase 3** : Pipeline de streaming temps-réel (Kafka + Preprocessors) - **En cours** 
* [ ] **Phase 4** : Module d'explicabilité (LLM Explainer) - **À venir** 
* [ ] **Phase 5** : Dashboard de monitoring (ELK Stack) - **À venir** 

## Architecture du Système

Le projet a évolué d'un script unique vers une architecture modulaire orientée micro-services :

1. **Ingestion** : Les flux réseau bruts arrivent via Kafka (`raw_data`).
2. **Preprocessing** : Nettoyage, gestion des valeurs `inf/nan` et normalisation (37 features sélectionnées).
3. **Detection** : Modèle hybride calculant à la fois l'erreur de reconstruction et la classe d'attaque.
4. **Explainer** : Analyse des alertes pour générer des rapports lisibles par l'homme.

## Structure du Repository

```bash
.
├── config.py                 # Configuration globale (Dimensions, Chemins, Kafka)
├── kafka_docker_config/      # Infrastructure Kafka/Zookeeper via Docker
├── models/artifacts/         # Artefacts d'entraînement (scaler, model.pt, etc.)
├── processors/               # Logique métier modulaire
│   ├── base.py               # Classe mère KafkaProcessor
│   ├── preprocessor.py       # Nettoyage et Normalisation
│   ├── detector.py           # Inférence Deep Learning
│   └── explainer.py          # (En cours) Intégration LLM
├── results/                  # Graphiques de performance (Notebook)
├── tests/                    # Scénarios de validation
│   └── static_test.py        # Test bout-en-bout sans Kafka
└── main.py                   # Point d'entrée du pipeline

```

## Guide de Démarrage Rapide

### 1. Prérequis

```bash
# Installer les dépendances du pipeline
pip install -r requirements_pipline.txt

```

### 2. Lancer l'infrastructure Kafka

```bash
cd kafka_docker_config
docker-compose up -d

```

### 3. Exécuter un test de validation (Statique)

Avant de lancer le flux réel, vérifiez que le modèle et le preprocessor communiquent bien :

```bash
export PYTHONPATH=$PYTHONPATH:.
python3 tests/static_test.py

```

## Détails du Modèle

* **Input** : 37 features (sélectionnées par corrélation).
* **Architecture** : Autoencoder (128->64->32->16) + Classifier (Latent + Error).
* **Classes supportées** : `Normal`, `DDoS`, `DoS`, `Bots`, `PortScan`, `WebAttack`, `Infiltration`.

## À Faire (Team Todo)

* **Intégration Explainer** : Finaliser `processors/explainer.py` pour traduire les vecteurs en langage naturel.
* **Optimization** : Gérer les versions de `scikit-learn` pour éviter les `InconsistentVersionWarning`.
* **Dockerisation** : Créer un Dockerfile pour le `DataPreprocessor` et le `IDSDetector`.
