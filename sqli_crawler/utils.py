from __future__ import annotations

import base64
import json
from email.message import EmailMessage
from functools import partial
from io import IOBase
from types import MappingProxyType
from typing import Any, NamedTuple


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


class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, IOBase):
            obj.seek(0)
            return {
                "filename": obj.name,
                "data": base64.b64encode(obj.read()).decode(),
            }
        return json.JSONEncoder.default(self, obj)


json_dumps = partial(json.dumps, ensure_ascii=False, cls=CustomJSONEncoder)
