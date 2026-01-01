"""
Panneau d'affichage des alertes IDS
"""
import streamlit as st
import json
from datetime import datetime


def get_severity_emoji(is_attack, confidence):
    """Retourne l'emoji de sévérité"""
    if is_attack and confidence > 0.9:
        return "🔴"
    elif is_attack:
        return "🟠"
    else:
        return "🟢"


def get_class_color(predicted_class):
    """Retourne la couleur selon la classe"""
    colors = {
        'DDoS': 'red',
        'DoS': 'red',
        'Bots': 'orange',
        'Brute Force': 'orange',
        'Port Scanning': 'yellow',
        'Web Attacks': 'orange',
        'Normal Traffic': 'green'
    }
    return colors.get(predicted_class, 'gray')


def render_alerts_panel(alerts, max_items=20):
    """
    Affiche le panneau des alertes
    
    Args:
        alerts: Liste des alertes
        max_items: Nombre max d'alertes à afficher
    """
    if not alerts:
        st.info("Aucune alerte pour le moment...")
        return
    
    st.caption(f"**{len(alerts)}** alertes affichées")
    
    # Afficher les alertes
    for idx, alert in enumerate(alerts[:max_items]):
        flow_id = alert.get('flow_id', 'unknown')
        predicted_class = alert.get('predicted_class', 'Unknown')
        confidence = alert.get('confidence', 0.0)
        is_attack = alert.get('is_attack', False)
        anomaly_score = alert.get('anomaly_score', 0.0)
        timestamp = alert.get('timestamp', 'N/A')
        
        # Emoji de sévérité
        severity_emoji = get_severity_emoji(is_attack, confidence)
        
        # Expander pour chaque alerte
        with st.expander(
            f"{severity_emoji} {predicted_class} - {confidence:.1%} | {flow_id}",
            expanded=(idx == 0)  # Première alerte ouverte par défaut
        ):
            # Métriques
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Confiance", f"{confidence:.1%}")
            
            with col2:
                st.metric("Anomaly Score", f"{anomaly_score:.3f}")
            
            with col3:
                status = "⚠️ ATTAQUE" if is_attack else "✅ Normal"
                st.metric("Statut", status)
            
            # Détails
            st.markdown("**Détails:**")
            
            detail_col1, detail_col2 = st.columns(2)
            
            with detail_col1:
                st.markdown(f"- **Flow ID:** `{flow_id}`")
                st.markdown(f"- **Timestamp:** {timestamp}")
                st.markdown(f"- **Classe:** {predicted_class}")
                st.markdown(f"- **Confiance:** {confidence:.2%}")
            
            with detail_col2:
                st.markdown(f"- **Anomalie:** {anomaly_score:.4f}")
                st.markdown(f"- **Reconstruction Error:** {alert.get('reconstruction_error', 0.0):.6f}")
                st.markdown(f"- **Est une attaque:** {'Oui' if is_attack else 'Non'}")
                st.markdown(f"- **Temps inférence:** {alert.get('inference_time_ms', 0.0):.1f} ms")
            
            # Probabilités par classe
            if 'class_probabilities' in alert:
                st.markdown("**Probabilités par classe:**")
                probs = alert['class_probabilities']
                # Trier par probabilité décroissante
                sorted_probs = sorted(probs.items(), key=lambda x: x[1], reverse=True)
                
                for class_name, prob in sorted_probs[:5]:  # Top 5
                    st.progress(prob, text=f"{class_name}: {prob:.1%}")
            
            # Top features
            if 'top_features' in alert and alert['top_features']:
                st.markdown("**Top Features:**")
                for feature in alert['top_features'][:5]:
                    feat_name = feature.get('feature', 'N/A')
                    feat_value = feature.get('value', 0)
                    feat_importance = feature.get('importance', 0)
                    st.markdown(f"- **{feat_name}:** {feat_value} (importance: {feat_importance:.2f})")
            
            # JSON brut
            with st.expander("📋 JSON brut"):
                st.json(alert)


if __name__ == "__main__":
    # Test du composant
    test_alerts = [
        {
            'flow_id': 'test_001',
            'timestamp': datetime.now().isoformat(),
            'predicted_class': 'DDoS',
            'confidence': 0.93,
            'is_attack': True,
            'anomaly_score': 0.82,
            'reconstruction_error': 0.024,
            'inference_time_ms': 12.5,
            'class_probabilities': {
                'DDoS': 0.93,
                'DoS': 0.03,
                'Normal Traffic': 0.02,
                'Web Attacks': 0.01
            },
            'top_features': [
                {'feature': 'Flow Duration', 'value': 234567, 'importance': 0.85},
                {'feature': 'Total Fwd Packets', 'value': 5678, 'importance': 0.72}
            ]
        }
    ]
    
    render_alerts_panel(test_alerts)
