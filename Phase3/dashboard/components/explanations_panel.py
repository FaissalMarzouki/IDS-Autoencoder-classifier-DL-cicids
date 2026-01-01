"""
Panneau d'affichage des explications LLM
"""
import streamlit as st
from datetime import datetime


def get_level_color(alert_level):
    """Retourne la couleur selon le niveau d'alerte"""
    colors = {
        'CRITICAL': 'red',
        'HIGH': 'orange',
        'MEDIUM': 'yellow',
        'LOW': 'blue',
        'INFO': 'green'
    }
    return colors.get(alert_level, 'gray')


def get_level_emoji(alert_level):
    """Retourne l'emoji selon le niveau d'alerte"""
    emojis = {
        'CRITICAL': '🔴',
        'HIGH': '🟠',
        'MEDIUM': '🟡',
        'LOW': '🔵',
        'INFO': '🟢'
    }
    return emojis.get(alert_level, '⚪')


def render_explanations_panel(explanations, max_items=20):
    """
    Affiche le panneau des explications LLM
    
    Args:
        explanations: Liste des explications
        max_items: Nombre max d'explications à afficher
    """
    if not explanations:
        st.info("Aucune explication pour le moment...")
        return
    
    st.caption(f"**{len(explanations)}** explications affichées")
    
    # Afficher les explications
    for idx, explanation in enumerate(explanations[:max_items]):
        alert_id = explanation.get('alert_id', 'unknown')
        alert_level = explanation.get('alert_level', 'INFO')
        llm_model = explanation.get('llm_model', 'N/A')
        processing_time = explanation.get('processing_time_ms', 0.0)
        
        explanation_content = explanation.get('explanation', {})
        
        # Emoji de niveau
        level_emoji = get_level_emoji(alert_level)
        
        # Expander pour chaque explication
        with st.expander(
            f"{level_emoji} {alert_level} | {alert_id}",
            expanded=(idx == 0)  # Première explication ouverte par défaut
        ):
            # Métadonnées
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Niveau", alert_level)
            
            with col2:
                st.metric("Modèle", llm_model)
            
            with col3:
                st.metric("Temps", f"{processing_time:.0f} ms")
            
            st.markdown("---")
            
            # Synthèse
            if 'summary' in explanation_content:
                st.markdown("### 📝 Synthèse")
                st.info(explanation_content['summary'])
            
            # Analyse technique
            if 'analysis' in explanation_content:
                st.markdown("### 🔍 Analyse Technique")
                st.markdown(explanation_content['analysis'])
            
            # Impact
            if 'impact' in explanation_content:
                st.markdown("### ⚠️ Impact")
                st.warning(explanation_content['impact'])
            
            # Recommandations
            if 'recommendations' in explanation_content:
                recommendations = explanation_content['recommendations']
                if recommendations:
                    st.markdown("### 🛡️ Recommandations")
                    for i, reco in enumerate(recommendations, 1):
                        st.markdown(f"{i}. {reco}")
            
            # Priorité
            if 'priority' in explanation_content:
                priority = explanation_content['priority']
                st.markdown(f"### 📊 Priorité: **{priority}**")
            
            st.markdown("---")
            
            # Informations supplémentaires
            st.caption(f"Alert ID: `{alert_id}` | Timestamp: {explanation.get('timestamp', 'N/A')}")
            
            # JSON brut
            with st.expander("📋 JSON brut"):
                st.json(explanation)


if __name__ == "__main__":
    # Test du composant
    test_explanations = [
        {
            'alert_id': 'test_001',
            'timestamp': datetime.now().isoformat(),
            'alert_level': 'CRITICAL',
            'llm_model': 'gpt-4',
            'processing_time_ms': 1250.5,
            'explanation': {
                'summary': 'Attaque DDoS détectée avec haute confiance (93%). Cible: port 80.',
                'analysis': 'Les patterns de trafic montrent une augmentation anormale du nombre de paquets...',
                'impact': 'Risque élevé de saturation du service web sur le port 80.',
                'recommendations': [
                    'Bloquer immédiatement l\'IP source',
                    'Activer rate limiting sur port 80',
                    'Alerter l\'équipe SOC niveau P1',
                    'Analyser les logs pour identifier d\'autres sources'
                ],
                'priority': 'P1'
            }
        }
    ]
    
    render_explanations_panel(test_explanations)
