from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedStorageUri:
    provider: str
    bucket: str
    key: str


def parse_storage_uri(uri: str) -> ParsedStorageUri:
    if "://" not in uri:
        raise ValueError(f"Invalid storage URI: {uri}")

    provider, remainder = uri.split("://", 1)
    parts = remainder.split("/", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError(f"Invalid storage URI: {uri}")

    return ParsedStorageUri(provider=provider, bucket=parts[0], key=parts[1])
