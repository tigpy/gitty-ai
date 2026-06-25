import pika
from typing import Any
from ..interfaces.event_bus import IEventBus
from ..serializers.event_serializer import EventSerializer
from .exchange import RabbitMQExchange

class RabbitMQPublisher(IEventBus):
    def __init__(self, host: str = "localhost", port: int = 5672):
        self.host = host
        self.port = port
        self._connection = None
        self._channel = None

    def _connect(self):
        if not self._connection or self._connection.is_closed:
            self._connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host=self.host,
                    port=self.port,
                    heartbeat=600,
                    blocked_connection_timeout=300
                )
            )
            self._channel = self._connection.channel()
            RabbitMQExchange.declare(self._channel)

    def publish(self, topic: str, event: Any) -> None:
        payload = EventSerializer.serialize(event)
        try:
            self._connect()
            self._channel.basic_publish(
                exchange=RabbitMQExchange.GITTY_EVENTS,
                routing_key=topic,
                body=payload,
                properties=pika.BasicProperties(
                    delivery_mode=2, # make message persistent
                    content_type="application/json"
                )
            )
        except Exception:
            # Reconnect and retry exactly once
            try:
                if self._connection and not self._connection.is_closed:
                    self._connection.close()
            except Exception:
                pass
            self._connection = None
            self._channel = None
            
            # Retry
            self._connect()
            self._channel.basic_publish(
                exchange=RabbitMQExchange.GITTY_EVENTS,
                routing_key=topic,
                body=payload,
                properties=pika.BasicProperties(
                    delivery_mode=2, # make message persistent
                    content_type="application/json"
                )
            )

    def subscribe(self, queue_name: str, topic: str, handler: Any) -> None:
        raise NotImplementedError("Use RabbitMQConsumer for subscriptions.")

    def start_consuming(self) -> None:
        raise NotImplementedError("Use RabbitMQConsumer for subscription loops.")

    def close(self):
        if self._connection and self._connection.is_open:
            self._connection.close()
Class = RabbitMQPublisher
