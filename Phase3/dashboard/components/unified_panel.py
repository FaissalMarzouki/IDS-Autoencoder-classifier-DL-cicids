"""
Panneau unifié - Alerte + Explication liées ensemble
"""
import streamlit as st
from datetime import datetime


def get_severity_emoji(is_attack, confidence):
    """Retourne l'emoji de sévérité"""
    if is_attack and confidence > 0.9:
        return "🔴"
    elif is_attack:
        return "🟠"
    else:
        return "🟢"


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


def render_unified_panel(data_manager, max_items=20):
    """
    Affiche les alertes avec leurs explications liées
    
    Args:
        data_manager: Instance de DataManager
        max_items: Nombre max d'éléments à afficher
    """
    alerts = data_manager.get_recent_alerts(max_items)
    
    if not alerts:
        st.info("🔍 Aucune alerte pour le moment... En attente de détections.")
        return
    
    st.caption(f"**{len(alerts)}** alertes affichées")
    
    # Afficher chaque alerte avec son explication
    for idx, alert in enumerate(alerts):
        flow_id = alert.get('flow_id', 'unknown')
        predicted_class = alert.get('predicted_class', 'Unknown')
        confidence = alert.get('confidence', 0.0)
        is_attack = alert.get('is_attack', False)
        anomaly_score = alert.get('anomaly_score', 0.0)
        timestamp = alert.get('timestamp', 'N/A')
        
        # Récupérer l'explication correspondante
        explanation = data_manager.get_explanation_for_alert(flow_id)
        
        # Déterminer le niveau d'alerte
        if explanation:
            alert_level = explanation.get('alert_level', 'INFO')
            level_emoji = get_level_emoji(alert_level)
            has_explanation = True
        else:
            alert_level = 'INFO'
            level_emoji = '⏳'
            has_explanation = False
        
        # Emoji de sévérité
        severity_emoji = get_severity_emoji(is_attack, confidence)
        
        # Titre de l'expander avec statut explication
        status_icon = "✅" if has_explanation else "⏳"
        title = f"{severity_emoji} {predicted_class} - {confidence:.1%} | {level_emoji} {alert_level} {status_icon}"
        
        # Container pour chaque alerte+explication
        with st.expander(title, expanded=(idx == 0)):
            
            # === SECTION ALERTE ===
            st.markdown("### 🚨 Détails de l'Alerte")
            
            # Métriques de l'alerte
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Confiance", f"{confidence:.1%}")
            
            with col2:
                st.metric("Anomaly Score", f"{anomaly_score:.3f}")
            
            with col3:
                status = "⚠️ ATTAQUE" if is_attack else "✅ Normal"
                st.metric("Statut", status)
            
            with col4:
                st.metric("Niveau", f"{level_emoji} {alert_level}")
            
            # Informations détaillées
            info_col1, info_col2 = st.columns(2)
            
            with info_col1:
                st.markdown("**📊 Informations Techniques**")
                st.markdown(f"- **Flow ID**: `{flow_id}`")
                st.markdown(f"- **Timestamp**: {timestamp}")
                st.markdown(f"- **Classe**: {predicted_class}")
                st.markdown(f"- **Reconstruction Error**: {alert.get('reconstruction_error', 0.0):.6f}")
            
            with info_col2:
                st.markdown("**⚙️ Modèle**")
                st.markdown(f"- **Version**: {alert.get('model_version', 'N/A')}")
                st.markdown(f"- **Temps inférence**: {alert.get('inference_time_ms', 0.0):.1f} ms")
                st.markdown(f"- **Est anomalie**: {'Oui' if alert.get('is_anomaly', False) else 'Non'}")
                st.markdown(f"- **Est attaque**: {'Oui' if is_attack else 'Non'}")
            
            # Probabilités par classe
            if 'class_probabilities' in alert:
                st.markdown("**📈 Probabilités par Classe**")
                probs = alert['class_probabilities']
                sorted_probs = sorted(probs.items(), key=lambda x: x[1], reverse=True)
                
                prob_cols = st.columns(min(len(sorted_probs), 4))
                for i, (class_name, prob) in enumerate(sorted_probs[:4]):
                    with prob_cols[i]:
                        st.progress(prob, text=f"{class_name}: {prob:.1%}")
            
            # Top features
            if 'top_features' in alert and alert['top_features']:
                st.markdown("**🔍 Top Features Contributeurs**")
                features_cols = st.columns(2)
                for i, feature in enumerate(alert['top_features'][:6]):
                    feat_name = feature.get('feature', 'N/A')
                    feat_value = feature.get('value', 0)
                    feat_importance = feature.get('importance', 0)
                    with features_cols[i % 2]:
                        st.markdown(f"- **{feat_name}**: {feat_value:.2f} (importance: {feat_importance:.2f})")
            
            st.markdown("---")
            
            # === SECTION EXPLICATION ===
            if has_explanation:
                st.markdown("### 🤖 Explication Intelligence Artificielle")
                
                exp_content = explanation.get('explanation', {})
                llm_model = explanation.get('llm_model', 'N/A')
                processing_time = explanation.get('processing_time_ms', 0.0)
                
                # Métadonnées LLM
                meta_col1, meta_col2, meta_col3 = st.columns(3)
                with meta_col1:
                    st.metric("Modèle LLM", llm_model.split('-')[0].upper())
                with meta_col2:
                    st.metric("Temps traitement", f"{processing_time:.0f} ms")
                with meta_col3:
                    priority = exp_content.get('priority', 'N/A')
                    st.metric("Priorité", priority)
                
                # Synthèse
                if 'summary' in exp_content:
                    st.markdown("#### 📝 Synthèse")
                    st.info(exp_content['summary'])
                
                # Analyse et Impact en deux colonnes
                analysis_col1, analysis_col2 = st.columns(2)
                
                with analysis_col1:
                    if 'analysis' in exp_content:
                        st.markdown("#### 🔍 Analyse Technique")
                        st.markdown(exp_content['analysis'])
                
                with analysis_col2:
                    if 'impact' in exp_content:
                        st.markdown("#### ⚠️ Impact")
                        st.warning(exp_content['impact'])
                
                # Recommandations
                if 'recommendations' in exp_content and exp_content['recommendations']:
                    st.markdown("#### 🛡️ Actions Recommandées")
                    for i, reco in enumerate(exp_content['recommendations'], 1):
                        st.markdown(f"{i}. {reco}")
                
            else:
                # Pas encore d'explication
                st.markdown("### ⏳ Explication en cours de génération...")
                st.info("🤖 L'Intelligence Artificielle analyse cette alerte. L'explication sera disponible dans quelques secondes.")
            
            # JSON brut (caché par défaut)
            with st.expander("📋 Données brutes (JSON)", expanded=False):
                col_json1, col_json2 = st.columns(2)
                with col_json1:
                    st.markdown("**Alerte**")
                    st.json(alert)
                with col_json2:
                    if has_explanation:
                        st.markdown("**Explication**")
                        st.json(explanation)
                    else:
                        st.markdown("**Explication**: En attente...")


if __name__ == "__main__":
    # Test du composant
    from data_manager import DataManager
    
    dm = DataManager()
    
    # Ajouter une alerte de test
    dm.add_alert({
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
            'Normal Traffic': 0.02
        },
        'top_features': [
            {'feature': 'Flow Duration', 'value': 234567, 'importance': 0.85}
        ]
    })
    
    # Ajouter l'explication correspondante
    dm.add_explanation({
        'alert_id': 'test_001',
        'flow_id': 'test_001',
        'alert_level': 'CRITICAL',
        'llm_model': 'llama-3.3-70b',
        'processing_time_ms': 1250.5,
        'explanation': {
            'summary': 'Attaque DDoS détectée avec haute confiance.',
            'analysis': 'Les patterns de trafic montrent une augmentation anormale...',
            'impact': 'Risque élevé de saturation du service.',
            'recommendations': [
                'Bloquer immédiatement l\'IP source',
                'Activer rate limiting'
            ],
            'priority': 'P1'
        }
    })
    
    render_unified_panel(dm)
