import asyncio
import random
from email.message import EmailMessage
from urllib.parse import parse_qsl, urlsplit


class ShuffleQueue(asyncio.Queue):
    def shuffle(self) -> None:
        random.shuffle(self._queue)


def str2bool(v: str) -> bool:
    return v.lower() in ("yes", "true", "t", "1")


def parse_header(ct: str) -> tuple[str, dict[str, str]]:
    msg = EmailMessage()
    msg["content-type"] = ct
    return msg.get_content_type(), msg["content-type"].params


def normalize_url(url: str) -> str:
    return ["https://", ""]["://" in url] + url.rstrip("/") + "/"


def parse_query_params(url: str) -> tuple[str, dict]:
    sp = urlsplit(url)
    return sp._replace(query="").geturl(), dict(parse_qsl(sp.query))


def parse_payload(data: str, headers: dict) -> tuple[dict, str]:
    mime, _ = parse_header(headers.pop("content-type", ""))
    if mime == "application/x-www-form-urlencoded":
        return dict(parse_qsl(data)), mime
    raise ValueError(f"unexpected or unknown mime type: {mime!r}")
