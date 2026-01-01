"""
Service principal LLM - Orchestration du traitement des alertes
"""
import json
import logging
import time
from datetime import datetime
from typing import Dict, Any
import sys
import os

# Ajouter le répertoire parent au path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm_service.alert_consumer import AlertConsumer
from llm_service.explanation_producer import ExplanationProducer
from llm_service.llm_client import LLMClient

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class LLMService:
    """Service principal - Consomme alertes, génère explications, publie"""
    
    def __init__(self):
        self.consumer = AlertConsumer()
        self.producer = ExplanationProducer()
        self.llm_client = LLMClient()
        
        # Statistiques
        self.stats = {
            'processed': 0,
            'errors': 0,
            'start_time': datetime.now()
        }
        
        logger.info("🚀 LLM Service initialisé")
    
    def build_prompt(self, alert: Dict[str, Any]) -> str:
        """
        Construit le prompt LLM à partir de l'alerte
        Utilise le format de FlowPrediction.to_llm_prompt() du notebook
        
        Args:
            alert: Alerte IDS
            
        Returns:
            Prompt structuré en français
        """
        is_attack = alert.get('is_attack', False)
        confidence = alert.get('confidence', 0.0)
        
        severity = "🔴 CRITIQUE" if is_attack and confidence > 0.9 else \
                   "🟠 ÉLEVÉ" if is_attack else \
                   "🟢 NORMAL"
        
        prompt = f"""
## 🔍 Rapport d'Analyse de Flux Réseau

### Identification
- **Flow ID**: {alert.get('flow_id', 'unknown')}
- **Timestamp**: {alert.get('timestamp', 'N/A')}

### Verdict
- **Classification**: {alert.get('predicted_class', 'Unknown')}
- **Confiance**: {confidence:.2%}
- **Sévérité**: {severity}
- **Est une attaque**: {'OUI ⚠️' if is_attack else 'NON ✅'}

### Scores d'Anomalie
- **Anomaly Score**: {alert.get('anomaly_score', 0.0):.4f}
- **Reconstruction Error**: {alert.get('reconstruction_error', 0.0):.6f}
- **Comportement anormal détecté**: {'OUI' if alert.get('is_anomaly', False) else 'NON'}

### Top Features Contributives
"""
        
        # Ajouter les top features de manière lisible (fallbacks si infos manquantes)
        top_features = alert.get('top_features', []) or []
        if top_features:
            for idx, feature in enumerate(top_features, 1):
                # Supporte les deux clés ('feature' pour dashboard, 'name' pour LLM)
                name = feature.get('name') or feature.get('feature') or f"Feature_{idx}"
                value = feature.get('value', 0.0)
                importance = feature.get('importance', feature.get('error', 0.0))
                prompt += f"\n- **{name}**: {value:.4f} (importance: {importance:.2%})"
        else:
            prompt += "\n- Non disponible"
        
        prompt += f"""

### Probabilités par Type de Trafic
{json.dumps(alert.get('class_probabilities', {}), indent=2, ensure_ascii=False)}


**Instructions pour l'analyse LLM:**
1. Analyser la classification et la confiance
2. Évaluer le score d'anomalie par rapport au seuil
3. Identifier les features qui ont contribué à cette classification
4. Expliquer brièvement l'influence de chaque feature listée ci-dessus dans la section **Analyse** (pas dans Recommandations)
5. Fournir dans **Recommandations** uniquement des actions concrètes pour l'équipe SOC (pas de description de features)
6. Attribuer un niveau de priorité (P1/P2/P3/P4)

**Tâche**: Analyse ce flux réseau et fournir:
1. **Synthèse**: 1-2 phrases résumant l'alerte
2. **Analyse**: Explication technique détaillée du type d'attaque
3. **Impact**: Implications pour la sécurité réseau
4. **Recommandations**: Actions à prendre (avec bullet points, sans ré-expliquer les features)
5. **Priorité**: CRITIQUE / ÉLEVÉ / MOYEN / BAS

Réponds en français.
"""
        return prompt
    
    def determine_alert_level(self, alert: Dict[str, Any]) -> str:
        """Détermine le niveau d'alerte basé sur la confiance et la classe"""
        is_attack = alert.get('is_attack', False)
        confidence = alert.get('confidence', 0.0)
        predicted_class = alert.get('predicted_class', '')
        
        if not is_attack:
            return "INFO"
        
        # DDoS/DoS avec haute confiance = CRITICAL
        if confidence >= 0.95 and predicted_class in ['DDoS', 'DoS']:
            return "CRITICAL"
        
        if confidence >= 0.85:
            return "HIGH"
        
        if confidence >= 0.70:
            return "MEDIUM"
        
        if confidence >= 0.50:
            return "LOW"
        
        return "INFO"
    
    def process_alert(self, alert: Dict[str, Any]) -> None:
        """
        Traite une alerte: génère prompt, appelle LLM, publie explication
        
        Args:
            alert: Alerte IDS depuis Kafka
        """
        flow_id = alert.get('flow_id', 'unknown')
        
        try:
            start_time = time.time()
            
            # 1. Construire le prompt
            prompt = self.build_prompt(alert)
            
            # 2. Appeler le LLM
            logger.info(f"🤖 Génération explication LLM pour {flow_id}...")
            explanation_content = self.llm_client.generate_explanation(prompt)
            
            # 🔧 DEBUG: Afficher la réponse pour la première alerte
            if self.stats['processed'] == 0:
                logger.info("\n" + "="*80)
                logger.info(f"🐛 DEBUG - Réponse LLM pour la première alerte ({flow_id}):")
                logger.info("="*80)
                logger.info(f"Réponse brute:\n{explanation_content}")
                logger.info("="*80 + "\n")
            
            # 3. Déterminer le niveau d'alerte
            alert_level = self.determine_alert_level(alert)
            
            # 4. Construire l'explication complète
            processing_time = (time.time() - start_time) * 1000  # en ms
            
            explanation = {
                "alert_id": flow_id,
                "timestamp": datetime.now().isoformat(),
                "explanation": explanation_content,
                "alert_level": alert_level,
                "llm_model": self.llm_client.model,
                "processing_time_ms": round(processing_time, 2)
            }
            
            # 5. Publier dans Kafka
            self.producer.send_explanation(explanation)
            
            # Stats
            self.stats['processed'] += 1
            
            logger.info(
                f"✅ Alerte traitée | Flow: {flow_id} | "
                f"Niveau: {alert_level} | "
                f"Temps: {processing_time:.0f}ms | "
                f"Total: {self.stats['processed']}"
            )
            
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"❌ Erreur traitement {flow_id}: {e}")
    
    def run(self) -> None:
        """Boucle principale du service"""
        logger.info("=" * 80)
        logger.info("🎯 LLM Service démarré - En attente d'alertes...")
        logger.info("=" * 80)
        
        try:
            for alert in self.consumer.consume():
                self.process_alert(alert)
                
                # Afficher stats toutes les 10 alertes
                if self.stats['processed'] % 10 == 0:
                    self.print_stats()
                    
        except KeyboardInterrupt:
            logger.info("\n⚠️ Interruption utilisateur")
        except Exception as e:
            logger.error(f"❌ Erreur fatale: {e}")
        finally:
            self.shutdown()
    
    def print_stats(self) -> None:
        """Affiche les statistiques du service"""
        elapsed = (datetime.now() - self.stats['start_time']).total_seconds()
        rate = self.stats['processed'] / elapsed if elapsed > 0 else 0
        
        logger.info("=" * 80)
        logger.info("📊 STATISTIQUES")
        logger.info(f"   • Alertes traitées: {self.stats['processed']}")
        logger.info(f"   • Erreurs: {self.stats['errors']}")
        logger.info(f"   • Débit: {rate:.2f} alertes/sec")
        logger.info(f"   • Uptime: {elapsed:.0f}s")
        logger.info("=" * 80)
    
    def shutdown(self) -> None:
        """Arrêt propre du service"""
        logger.info("\n🛑 Arrêt du service...")
        
        self.print_stats()
        
        self.consumer.close()
        self.producer.close()
        
        logger.info("👋 Service arrêté proprement")


def main():
    """Point d'entrée principal"""
    print("""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║          🛡️  LLM SERVICE - IDS ALERT INTERPRETER  🛡️          ║
║                                                              ║
║  Consomme:  ids-alerts (Kafka)                              ║
║  Génère:    Explications LLM                                ║
║  Publie:    ids-explanations (Kafka)                        ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    service = LLMService()
    service.run()


if __name__ == "__main__":
    main()
