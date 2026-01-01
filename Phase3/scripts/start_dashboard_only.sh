#!/bin/bash

# Script simplifié pour démarrer juste le dashboard (sans LLM pour l'instant)

echo "🎨 Démarrage du Dashboard Streamlit"
echo "===================================="

cd "$(dirname "$0")/.."

# Activer l'environnement virtuel
if [ -d "/home/ellayli/enset_CCN/s5/IA/project/venv" ]; then
    source /home/ellayli/enset_CCN/s5/IA/project/venv/bin/activate
    echo "✅ Environnement virtuel activé"
fi

echo ""
echo "🌐 Dashboard accessible sur: http://localhost:8501"
echo ""

# Lancer streamlit avec python3.10
/home/ellayli/enset_CCN/s5/IA/project/venv/bin/python3.10 -m streamlit run dashboard/app.py --server.port 8501 --server.address localhost
