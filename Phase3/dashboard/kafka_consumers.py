"""
Consommateur Kafka persistant pour le Dashboard IDS.
Utilise st.cache_resource pour survivre aux refresh Streamlit et stocke
les messages dans un buffer thread-safe accessible via get_new_messages().
"""
import json
import threading
from typing import Any, Dict, List
from uuid import uuid4

import streamlit as st
from kafka import KafkaConsumer
from kafka.errors import KafkaError


class BackgroundConsumer:
    """Consommateur Kafka tournant en tâche de fond et mis en cache."""

    def __init__(
        self,
        bootstrap_servers: str = "localhost:9093",
        topics: List[str] | None = None,
        group_id: str | None = None,
    ) -> None:
        self.bootstrap_servers = bootstrap_servers
        self.topics = topics or ["ids-alerts", "ids-explanations"]
        self.group_id = group_id or f"dashboard-{uuid4()}"

        self._consumer: KafkaConsumer | None = None
        self._buffer: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
        self._running = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        try:
            self._consumer = KafkaConsumer(
                *self.topics,
                bootstrap_servers=self.bootstrap_servers,
                group_id=self.group_id,
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
                auto_offset_reset="latest",
                enable_auto_commit=True,
                session_timeout_ms=30000,
                consumer_timeout_ms=1000,
            )
        except KafkaError as exc:
            print(f"[BackgroundConsumer] ✗ Erreur Kafka lors de la connexion: {exc}")
            return

        self._running.set()
        self._thread = threading.Thread(target=self._consume_loop, daemon=True)
        self._thread.start()
        print(f"[BackgroundConsumer] ✓ Connecté (group_id={self.group_id})")

    def _consume_loop(self) -> None:
        if not self._consumer:
            return

        while self._running.is_set():
            try:
                for message in self._consumer:
                    if not self._running.is_set():
                        break

                    payload = message.value
                    record = {
                        "topic": message.topic,
                        "value": payload,
                        "partition": message.partition,
                        "offset": message.offset,
                    }

                    with self._lock:
                        self._buffer.append(record)
            except Exception as exc:  # noqa: BLE001
                if self._running.is_set():
                    print(f"[BackgroundConsumer] Erreur boucle consommation: {exc}")

    def get_new_messages(self) -> List[Dict[str, Any]]:
        """Retourne les messages reçus depuis le dernier appel et vide le buffer."""
        with self._lock:
            messages = list(self._buffer)
            self._buffer.clear()
        return messages

    def stop(self) -> None:
        self._running.clear()
        if self._consumer:
            try:
                self._consumer.close()
            except Exception:
                pass
        print("[BackgroundConsumer] ✓ Arrêté")


@st.cache_resource(show_spinner=False)
def get_background_consumer(bootstrap_servers: str = "localhost:9093") -> BackgroundConsumer:
    """Retourne un consommateur persistant partagé entre les reruns Streamlit."""
    consumer = BackgroundConsumer(bootstrap_servers=bootstrap_servers)
    consumer.start()
    return consumer
