# Phase 3 – IDS LLM Dashboard & Pipelines

Cette phase ajoute un service LLM, un dashboard temps réel et un streamer de données basés sur Kafka pour expliquer les alertes IDS.

## Contenu
- `llm_service/` : consomme `ids-alerts`, génère les explications LLM, publie sur `ids-explanations`.
- `dashboard/` : Streamlit affichant alertes + explications en temps réel.
- `dataset_streamer/` : rejoue le dataset CICIDS2017 vers Kafka avec le modèle autoencoder.
- `scripts/` : démarrage/arrêt rapides (LLM, dashboard, tests de setup).
- `config.py` : configuration centralisée (Kafka, LLM, chemins modèles).

## Prérequis
- Docker + Docker Compose (pour Kafka).
- Python 3.10+ avec `venv` activé.
- Modèle et artefacts déjà présents dans `models/artifacts` (autoencoder, scaler, label encoder…).
- Variables `.env` pour le LLM (GROQ_API_KEYS ou équivalent, LLM_MODEL, etc.).

## Installation des dépendances
Dans `Phase3/` :
```bash
pip install -r requirements.txt
```

## Démarrage (4 terminaux)
1) **Kafka**
```bash
cd kafka_docker_config && docker-compose up
```
2) **Service LLM**
```bash
cd Phase3
bash scripts/start_llm_only.sh
```
3) **Dashboard Streamlit**
```bash
cd Phase3
bash scripts/start_dashboard_only.sh
```
4) **Générateur d'alertes (pipeline IDS)**
```bash
cd app
python automated_ids_pipeline.py --count 20 --kafka-server localhost:9093 --delay 2.0
```

## Notes
- Ajuste `LLM_MAX_TOKENS` dans `.env` (ex: 2000) si les réponses sont tronquées.
- Les topics utilisés : `ids-alerts` (entrées) et `ids-explanations` (sorties).
- En cas de blocage réseau, vérifie que Kafka écoute sur `localhost:9093` (configurable dans `.env`).
