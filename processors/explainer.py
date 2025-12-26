from .base import KafkaProcessor

class LLMExplainer(KafkaProcessor):
    def process(self, alert):
        # Exemple avec un prompt pour LLM (type Ollama ou OpenAI)
        prompt = f"""
        ANALYSE DE SÉCURITÉ :
        Une menace de type {alert['prediction']} a été détectée avec une confiance de {alert['confidence']:.2%}.
        Flux : de {alert['src_ip']} vers {alert['dst_ip']}.
        Expliquez brièvement les risques et la recommandation immédiate.
        """
        
        # Simulation de réponse LLM pour le test -- Kansayno lmawhiba dyal SAAD!
        explanation = f"Détection de {alert['prediction']}. Action recommandée : Isoler l'IP source {alert['src_ip']}."
        
        self.send_message({
            "alert_id": alert['flow_id'],
            "explanation": explanation,
            "severity": "High" if alert['confidence'] > 0.8 else "Medium"
        })
