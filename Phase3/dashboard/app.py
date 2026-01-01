"""
Application Streamlit principale - Dashboard IDS
"""
import streamlit as st
import time
import sys
import os
from datetime import datetime

# Ajouter le répertoire parent au path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kafka_consumers import get_background_consumer
from data_manager import DataManager
from components.unified_panel import render_unified_panel
from components.stats_panel import render_stats_panel

# Configuration de la page
st.set_page_config(
    page_title="IDS Alert Monitor",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed"  # Sidebar fermée par défaut
)

# Style CSS personnalisé
st.markdown("""
<style>
    .stAlert {
        padding: 1rem;
        border-radius: 0.5rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    h1 {
        color: #1f77b4;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource(show_spinner=False)
def get_persistent_data_manager() -> DataManager:
    """DataManager persistant tant que le processus Streamlit tourne."""
    return DataManager(max_items=200)


def get_data_manager() -> DataManager:
    """Expose le DataManager persistant et conserve une référence en session."""
    dm = get_persistent_data_manager()
    st.session_state.data_manager = dm
    st.session_state.last_update = st.session_state.get("last_update", datetime.now())
    st.session_state.initialized = True
    return dm


def ingest_new_messages(consumer, data_manager: DataManager) -> None:
    """Ajoute les nouveaux messages Kafka au DataManager persistant."""
    new_messages = consumer.get_new_messages()

    for message in new_messages:
        topic = message.get("topic")
        value = message.get("value")

        if topic == "ids-alerts":
            data_manager.add_alert(value)
        elif topic == "ids-explanations":
            data_manager.add_explanation(value)

    if new_messages:
        st.session_state.last_update = datetime.now()


def render_header():
    """Affiche l'en-tête du dashboard"""
    col1, col2, col3 = st.columns([2, 3, 2])
    
    with col1:
        st.title("🛡️ IDS Monitor")
    
    with col2:
        st.markdown("### Surveillance Temps Réel")
    
    with col3:
        if st.session_state.get('initialized', False):
            st.success("🟢 Connecté")
        else:
            st.error("🔴 Déconnecté")


def get_filters():
    """Retourne les filtres par défaut sans sidebar"""
    return {
        'filter_class': [],
        'filter_level': [],
        'show_attacks_only': False,
        'refresh_rate': 2,
        'max_items': 20
    }


def apply_filters(alerts, filters):
    """Applique les filtres aux alertes"""
    if filters['show_attacks_only']:
        alerts = [a for a in alerts if a.get('is_attack', False)]
    
    if filters['filter_class']:
        alerts = [a for a in alerts if a.get('predicted_class') in filters['filter_class']]
    
    return alerts


def main():
    """Point d'entrée principal"""
    consumer = get_background_consumer()
    data_manager = get_data_manager()

    ingest_new_messages(consumer, data_manager)

    placeholder = st.empty()
    with placeholder.container():
        render_header()

        filters = get_filters()

        st.markdown("---")
        render_stats_panel(data_manager)

        st.markdown("---")
        st.markdown("### 🔗 Alertes & Explications Liées")
        render_unified_panel(data_manager, filters['max_items'])

    time.sleep(filters['refresh_rate'])
    st.rerun()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        st.info("👋 Dashboard arrêté")
        if 'consumer' in st.session_state:
            st.session_state.consumer.stop()
