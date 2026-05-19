import json
import uuid

from trustvault.queue.base import QueueMessage, QueueProvider


class AzureServiceBusQueue(QueueProvider):
    def __init__(self, fully_qualified_namespace: str | None, queue_name: str):
        if not fully_qualified_namespace:
            raise ValueError("azure_service_bus_fully_qualified_namespace must be configured")
        from azure.identity import DefaultAzureCredential
        from azure.servicebus import ServiceBusClient

        self.queue_name = queue_name
        self.client = ServiceBusClient(fully_qualified_namespace, credential=DefaultAzureCredential())

    def enqueue(self, message: dict) -> str:
        from azure.servicebus import ServiceBusMessage

        message_id = str(uuid.uuid4())
        body = {"id": message_id, **message}
        with self.client.get_queue_sender(self.queue_name) as sender:
            sender.send_messages(ServiceBusMessage(json.dumps(body, default=str), message_id=message_id))
        return message_id

    def receive(self, max_messages: int = 1) -> list[QueueMessage]:
        messages: list[QueueMessage] = []
        with self.client.get_queue_receiver(self.queue_name, max_wait_time=10) as receiver:
            for item in receiver.receive_messages(max_message_count=max_messages, max_wait_time=10):
                body = json.loads(str(item))
                messages.append(QueueMessage(id=body.get("id", item.message_id), body=body, receipt_handle=item.lock_token))
        return messages

    def acknowledge(self, message: QueueMessage) -> None:
        # Completion requires the original ServiceBusReceivedMessage, so production
        # workers should keep receiver scope open. This adapter documents the shape
        # and is used as the cloud-ready interface boundary.
        return None

    def fail(self, message: QueueMessage, reason: str) -> None:
        return None
