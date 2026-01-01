#!/bin/bash

# Script pour démarrer uniquement le service LLM

echo "🤖 Démarrage du Service LLM (Groq)"
echo "=================================="

cd "$(dirname "$0")/.."

# Vérifier la configuration
if [ ! -f ".env" ]; then
    echo "❌ Fichier .env non trouvé!"
    echo "Créez le fichier .env avec votre clé API Groq"
    exit 1
fi

# Activer l'environnement virtuel
if [ -d "/home/ellayli/enset_CCN/s5/IA/venv" ]; then
    source /home/ellayli/enset_CCN/s5/IA/venv/bin/activate
    echo "✅ Environnement virtuel activé"
fi

echo ""
echo "📊 Configuration:"
grep -E "LLM_PROVIDER|LLM_MODEL|KAFKA" .env | sed 's/^/   /'
echo ""

# Créer le dossier logs si nécessaire
mkdir -p logs

echo "🚀 Démarrage du service LLM..."
echo "   Consomme: ids-alerts"
echo "   Produit: ids-explanations"
echo ""

# Lancer le service LLM
/home/ellayli/enset_CCN/s5/IA/venv/bin/python -m llm_service.main
