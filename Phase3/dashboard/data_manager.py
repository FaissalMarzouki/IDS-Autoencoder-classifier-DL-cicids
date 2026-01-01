"""
Data Manager - Gestion de l'état et synchronisation alertes/explications
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataManager:
    """Gestionnaire de données pour le dashboard"""
    
    def __init__(self, max_items: int = 100):
        self.max_items = max_items
        
        # Stockage des alertes et explications
        self.alerts: List[Dict[str, Any]] = []
        self.explanations: List[Dict[str, Any]] = []
        
        # Index pour accès rapide
        self.alerts_index: Dict[str, Dict[str, Any]] = {}
        self.explanations_index: Dict[str, Dict[str, Any]] = {}
        
        # Statistiques
        self.stats = {
            'total_alerts': 0,
            'total_explanations': 0,
            'by_class': {},
            'by_level': {},
            'attacks_count': 0,
            'normal_count': 0
        }
        
        logger.info("✅ DataManager initialisé")
    
    def add_alert(self, alert: Dict[str, Any]) -> None:
        """Ajoute une alerte"""
        flow_id = alert.get('flow_id', 'unknown')
        
        # Ajouter à la liste
        self.alerts.insert(0, alert)
        
        # Limiter la taille
        if len(self.alerts) > self.max_items:
            removed = self.alerts.pop()
            removed_id = removed.get('flow_id')
            if removed_id in self.alerts_index:
                del self.alerts_index[removed_id]
        
        # Indexer
        self.alerts_index[flow_id] = alert
        
        # Mettre à jour les stats
        self._update_alert_stats(alert)
        
        logger.debug(f"➕ Alerte ajoutée: {flow_id}")
    
    def add_explanation(self, explanation: Dict[str, Any]) -> None:
        """Ajoute une explication"""
        alert_id = explanation.get('alert_id', 'unknown')
        flow_id = explanation.get('flow_id', alert_id)  # Utiliser flow_id pour l'indexation
        
        # Ajouter à la liste
        self.explanations.insert(0, explanation)
        
        # Limiter la taille
        if len(self.explanations) > self.max_items:
            removed = self.explanations.pop()
            removed_flow_id = removed.get('flow_id', removed.get('alert_id'))
            if removed_flow_id in self.explanations_index:
                del self.explanations_index[removed_flow_id]
        
        # Indexer par flow_id pour correspondance avec les alertes
        self.explanations_index[flow_id] = explanation
        
        # Mettre à jour les stats
        self._update_explanation_stats(explanation)
        
        logger.debug(f"➕ Explication ajoutée: {alert_id} (flow: {flow_id})")
    
    def _update_alert_stats(self, alert: Dict[str, Any]) -> None:
        """Met à jour les statistiques des alertes"""
        self.stats['total_alerts'] += 1
        
        # Par classe
        predicted_class = alert.get('predicted_class', 'Unknown')
        self.stats['by_class'][predicted_class] = self.stats['by_class'].get(predicted_class, 0) + 1
        
        # Attaques vs Normal
        if alert.get('is_attack', False):
            self.stats['attacks_count'] += 1
        else:
            self.stats['normal_count'] += 1
    
    def _update_explanation_stats(self, explanation: Dict[str, Any]) -> None:
        """Met à jour les statistiques des explications"""
        self.stats['total_explanations'] += 1
        
        # Par niveau
        alert_level = explanation.get('alert_level', 'INFO')
        self.stats['by_level'][alert_level] = self.stats['by_level'].get(alert_level, 0) + 1
    
    def get_recent_alerts(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Récupère les alertes récentes"""
        return self.alerts[:limit]
    
    def get_recent_explanations(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Récupère les explications récentes"""
        return self.explanations[:limit]
    
    def get_alert_with_explanation(self, flow_id: str) -> Optional[Dict[str, Any]]:
        """
        Récupère une alerte avec son explication associée
        
        Returns:
            Dict avec 'alert' et 'explanation' (ou None si pas d'explication)
        """
        alert = self.alerts_index.get(flow_id)
        if not alert:
            return None
        
        explanation = self.explanations_index.get(flow_id)
        
        return {
            'alert': alert,
            'explanation': explanation
        }
    
    def get_explanation_for_alert(self, flow_id: str) -> Optional[Dict[str, Any]]:
        """
        Récupère l'explication pour une alerte donnée
        
        Args:
            flow_id: Identifiant du flux
            
        Returns:
            Explication ou None si pas encore disponible
        """
        return self.explanations_index.get(flow_id)
    
    def get_alerts_by_class(self, predicted_class: str) -> List[Dict[str, Any]]:
        """Filtre les alertes par classe"""
        return [a for a in self.alerts if a.get('predicted_class') == predicted_class]
    
    def get_alerts_by_level(self, alert_level: str) -> List[Dict[str, Any]]:
        """Filtre les alertes par niveau (via explications)"""
        alert_ids = [
            e.get('alert_id') 
            for e in self.explanations 
            if e.get('alert_level') == alert_level
        ]
        return [a for a in self.alerts if a.get('flow_id') in alert_ids]
    
    def get_attacks_only(self) -> List[Dict[str, Any]]:
        """Récupère uniquement les attaques"""
        return [a for a in self.alerts if a.get('is_attack', False)]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Retourne les statistiques pour le dashboard"""
        total = self.stats['total_alerts']
        
        return {
            'total_alerts': total,
            'total_explanations': self.stats['total_explanations'],
            'attacks_count': self.stats['attacks_count'],
            'attack_ratio': (self.stats['attacks_count'] / total) if total > 0 else 0,
            'by_class': self.stats['by_class'],
            'by_level': self.stats['by_level']
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques brutes"""
        return self.stats.copy()
    
    def get_stats_summary(self) -> Dict[str, Any]:
        """Retourne un résumé des statistiques"""
        total = self.stats['total_alerts']
        
        return {
            'total_alerts': total,
            'total_explanations': self.stats['total_explanations'],
            'attacks_count': self.stats['attacks_count'],
            'normal_count': self.stats['normal_count'],
            'attack_rate': (self.stats['attacks_count'] / total * 100) if total > 0 else 0,
            'most_common_class': max(self.stats['by_class'].items(), key=lambda x: x[1])[0] if self.stats['by_class'] else 'N/A',
            'most_common_level': max(self.stats['by_level'].items(), key=lambda x: x[1])[0] if self.stats['by_level'] else 'N/A',
            'by_class': self.stats['by_class'],
            'by_level': self.stats['by_level']
        }
    
    def clear(self) -> None:
        """Réinitialise toutes les données"""
        self.alerts.clear()
        self.explanations.clear()
        self.alerts_index.clear()
        self.explanations_index.clear()
        
        self.stats = {
            'total_alerts': 0,
            'total_explanations': 0,
            'by_class': {},
            'by_level': {},
            'attacks_count': 0,
            'normal_count': 0
        }
        
        logger.info("🗑️ DataManager réinitialisé")


if __name__ == "__main__":
    # Test du DataManager
    dm = DataManager()
    
    # Ajouter des alertes de test
    for i in range(5):
        dm.add_alert({
            'flow_id': f'flow_{i}',
            'predicted_class': 'DDoS' if i % 2 == 0 else 'Normal Traffic',
            'confidence': 0.9,
            'is_attack': i % 2 == 0
        })
    
    # Ajouter des explications
    for i in range(3):
        dm.add_explanation({
            'alert_id': f'flow_{i}',
            'alert_level': 'HIGH' if i == 0 else 'MEDIUM'
        })
    
    # Afficher stats
    stats = dm.get_stats_summary()
    print("📊 Statistiques:")
    print(f"  Total alertes: {stats['total_alerts']}")
    print(f"  Attaques: {stats['attacks_count']}")
    print(f"  Taux attaques: {stats['attack_rate']:.1f}%")
    print(f"  Par classe: {stats['by_class']}")
    print(f"  Par niveau: {stats['by_level']}")
