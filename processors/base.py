import json
import logging

# On essaie d'importer Kafka, mais on ne bloque pas si c'est absent 
# (utile pour les tests statiques)
try:
    from kafka import KafkaConsumer, KafkaProducer
    KAFKA_AVAILABLE = True
except ImportError:
    KAFKA_AVAILABLE = False

class KafkaProcessor:
    def __init__(self, input_topic, output_topic=None):
        self.input_topic = input_topic
        self.output_topic = output_topic
        self.bootstrap_servers = 'localhost:9092' # Port interne docker
        
        if KAFKA_AVAILABLE:
            self.consumer = KafkaConsumer(
                self.input_topic,
                bootstrap_servers=self.bootstrap_servers,
                value_deserializer=lambda x: json.loads(x.decode('utf-8')),
                auto_offset_reset='earliest',
                group_id=f'group-{input_topic}'
            )
            if output_topic:
                self.producer = KafkaProducer(
                    bootstrap_servers=self.bootstrap_servers,
                    value_serializer=lambda x: json.dumps(x).encode('utf-8')
                )

    def send_message(self, data):
        if KAFKA_AVAILABLE and self.output_topic:
            self.producer.send(self.output_topic, value=data)
            self.producer.flush()

    def start(self):
        print(f"[*] Démarrage du processing sur le topic : {self.input_topic}")
        if not KAFKA_AVAILABLE:
            print("❌ Erreur: Bibliothèque Kafka non trouvée.")
            return

        for message in self.consumer:
            self.process(message.value)

    def process(self, data):
        """À implémenter dans les classes filles"""
        raise NotImplementedError("La méthode process doit être implémentée.")
