from trustvault.queue.base import QueueProvider
from trustvault.settings import Settings, get_settings


def get_queue_provider(settings: Settings | None = None) -> QueueProvider | None:
    settings = settings or get_settings()
    provider = settings.queue_provider.lower()
    if provider in {"database", "local", "none"}:
        return None
    if provider == "sqs":
        from trustvault.queue.sqs import SQSQueue

        return SQSQueue(settings.sqs_queue_url or "", region_name=settings.aws_region)
    if provider in {"azure", "azure_service_bus", "service_bus"}:
        from trustvault.queue.azure_service_bus import AzureServiceBusQueue

        return AzureServiceBusQueue(
            fully_qualified_namespace=settings.azure_service_bus_fully_qualified_namespace,
            queue_name=settings.azure_service_bus_queue_name,
        )
    raise ValueError(f"Unsupported queue provider: {settings.queue_provider}")
