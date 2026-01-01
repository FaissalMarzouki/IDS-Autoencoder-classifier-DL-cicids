"""
Panneau d'affichage des statistiques
"""
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import pandas as pd


def render_stats_panel(data_manager):
    """
    Affiche le panneau des statistiques
    
    Args:
        data_manager: Instance de DataManager
    """
    stats = data_manager.get_statistics()
    
    # Métriques globales
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Total Alertes",
            stats['total_alerts'],
            delta=None
        )
    
    with col2:
        st.metric(
            "Attaques",
            stats['attacks_count'],
            delta=f"{stats['attack_ratio']:.1%}" if stats['total_alerts'] > 0 else "0%"
        )
    
    with col3:
        st.metric(
            "Explications",
            stats['total_explanations']
        )
    
    with col4:
        coverage = (stats['total_explanations'] / stats['total_alerts'] * 100) if stats['total_alerts'] > 0 else 0
        st.metric(
            "Couverture LLM",
            f"{coverage:.0f}%"
        )
    
    st.markdown("---")
    
    # Graphiques
    chart_col1, chart_col2 = st.columns(2)
    
    with chart_col1:
        # Distribution par classe
        if stats['by_class']:
            st.markdown("#### 📊 Distribution par Classe")
            
            df_class = pd.DataFrame(
                list(stats['by_class'].items()),
                columns=['Classe', 'Nombre']
            )
            df_class = df_class.sort_values('Nombre', ascending=False)
            
            fig_class = px.bar(
                df_class,
                x='Classe',
                y='Nombre',
                color='Nombre',
                color_continuous_scale='Reds',
                title=None
            )
            fig_class.update_layout(
                showlegend=False,
                height=300,
                margin=dict(l=0, r=0, t=0, b=0)
            )
            st.plotly_chart(fig_class, use_container_width=True)
        else:
            st.info("Pas encore de données...")
    
    with chart_col2:
        # Distribution par niveau d'alerte
        if stats['by_level']:
            st.markdown("#### 🎯 Niveaux d'Alerte")
            
            df_level = pd.DataFrame(
                list(stats['by_level'].items()),
                columns=['Niveau', 'Nombre']
            )
            
            # Ordre des niveaux
            level_order = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO']
            df_level['Niveau'] = pd.Categorical(
                df_level['Niveau'],
                categories=level_order,
                ordered=True
            )
            df_level = df_level.sort_values('Niveau')
            
            # Couleurs
            colors = {
                'CRITICAL': '#ff0000',
                'HIGH': '#ff6600',
                'MEDIUM': '#ffcc00',
                'LOW': '#3399ff',
                'INFO': '#00cc66'
            }
            df_level['Color'] = df_level['Niveau'].map(colors)
            
            fig_level = go.Figure(data=[
                go.Bar(
                    x=df_level['Niveau'],
                    y=df_level['Nombre'],
                    marker_color=df_level['Color']
                )
            ])
            fig_level.update_layout(
                showlegend=False,
                height=300,
                margin=dict(l=0, r=0, t=0, b=0)
            )
            st.plotly_chart(fig_level, use_container_width=True)
        else:
            st.info("Pas encore d'explications...")
    
    # Ratio attaques/normal
    if stats['total_alerts'] > 0:
        st.markdown("---")
        st.markdown("#### 🎯 Ratio Attaques / Trafic Normal")
        
        normal_count = stats['total_alerts'] - stats['attacks_count']
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Pie chart
            fig_pie = go.Figure(data=[
                go.Pie(
                    labels=['Attaques', 'Normal'],
                    values=[stats['attacks_count'], normal_count],
                    marker=dict(colors=['#ff4444', '#44ff44']),
                    hole=0.4
                )
            ])
            fig_pie.update_layout(
                height=250,
                margin=dict(l=0, r=0, t=0, b=0),
                showlegend=True
            )
            st.plotly_chart(fig_pie, use_container_width=True)
        
        with col2:
            # Métriques détaillées
            st.metric("Attaques", stats['attacks_count'])
            st.metric("Normal", normal_count)
            st.metric("Taux d'attaque", f"{stats['attack_ratio']:.1%}")


if __name__ == "__main__":
    # Test du composant
    from data_manager import DataManager
    
    dm = DataManager()
    
    # Ajouter des données de test
    for i in range(10):
        dm.add_alert({
            'flow_id': f'test_{i}',
            'predicted_class': ['DDoS', 'DoS', 'Normal Traffic'][i % 3],
            'is_attack': i % 3 != 2
        })
    
    for i in range(7):
        dm.add_explanation({
            'alert_id': f'test_{i}',
            'alert_level': ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'][i % 4]
        })
    
    render_stats_panel(dm)
