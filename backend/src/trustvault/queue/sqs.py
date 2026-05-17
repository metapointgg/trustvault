import json
import uuid

from trustvault.queue.base import QueueMessage, QueueProvider


class SQSQueue(QueueProvider):
    def __init__(self, queue_url: str, region_name: str | None = None):
        if not queue_url:
            raise ValueError("sqs_queue_url must be configured for SQS queue provider")
        import boto3

        self.queue_url = queue_url
        self.client = boto3.client("sqs", region_name=region_name)

    def enqueue(self, message: dict) -> str:
        message_id = str(uuid.uuid4())
        body = {"id": message_id, **message}
        response = self.client.send_message(QueueUrl=self.queue_url, MessageBody=json.dumps(body, default=str))
        return response.get("MessageId", message_id)

    def receive(self, max_messages: int = 1) -> list[QueueMessage]:
        response = self.client.receive_message(
            QueueUrl=self.queue_url,
            MaxNumberOfMessages=max_messages,
            WaitTimeSeconds=10,
        )
        messages: list[QueueMessage] = []
        for item in response.get("Messages", []):
            body = json.loads(item["Body"])
            messages.append(QueueMessage(id=body.get("id", item["MessageId"]), body=body, receipt_handle=item["ReceiptHandle"]))
        return messages

    def acknowledge(self, message: QueueMessage) -> None:
        if message.receipt_handle:
            self.client.delete_message(QueueUrl=self.queue_url, ReceiptHandle=message.receipt_handle)

    def fail(self, message: QueueMessage, reason: str) -> None:
        # Let SQS visibility timeout/dead-letter policy handle retries/failures.
        return None
