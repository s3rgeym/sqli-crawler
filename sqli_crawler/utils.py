from __future__ import annotations

from email.message import EmailMessage
from types import MappingProxyType
from typing import NamedTuple


def normalize_url(url: str) -> str:
    return ["https://", ""]["://" in url] + url.rstrip("/") + "/"


class MimeType(NamedTuple):
    type: str
    params: MappingProxyType

    @classmethod
    def parse(cls, ct: str) -> MimeType:
        msg = EmailMessage()
        msg["content-type"] = ct
        return cls(msg.get_content_type(), msg["content-type"].params)
