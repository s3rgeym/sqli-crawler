from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
import typing as typ
from collections import Counter
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urldefrag, urlsplit

import aiohttp
import pyppeteer
import pyppeteer.errors
from aiohttp.client import ClientResponse
from pyppeteer.browser import Browser, Page
from pyppeteer.network_manager import Request

from .color_log import AnsiColorHandler
from .utils import normalize_url, parse_payload, parse_query_params

ASSETS_PATH = Path(__file__).resolve().parent / "assets"

SQLI_REGEX: re.Pattern = re.compile(
    "|".join(
        [
            r"You have an error in your SQL syntax",
            r"Unclosed quotation mark after the character string",
            # Иногда при ошибке выводится полный запрос
            r"SELECT \* FROM",
            # Название PHP функций
            r"mysqli?_num_rows",
            r"mysqli?_query",
            r"mysqli?_fetch_(?:array|assoc|field|object|row)",
            r"mysqli?_result",
            # bitrix
            r"<b>DB query error.</b>",
            # pg_query
            r"Query failed",
            # common PHP errors
            r"<b>(?:Fatal error|Warning)</b>:",
        ]
    )
)

QOUTES = "'\""


class RequestInfo(typ.NamedTuple):
    method: str
    url: str
    headers: dict
    cookies: dict
    data: str | None


@dataclass
class SQLiCrawler:
    """SQLi Crawler"""

    input: typ.TextIO
    output: typ.TextIO
    crawl_depth: int
    crawl_per_host: int
    crawlers: int
    sqli_checkers: int
    show_browser: bool
    verbosity: int

    def __post_init__(self) -> None:
        log_level = max(logging.DEBUG, logging.ERROR - self.verbosity * 10)
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)
        self.log.addHandler(AnsiColorHandler())

    async def squeal(self) -> None:
        """say something on ukrainian"""
        cmd = ["mpg123", str(ASSETS_PATH / "Sound_20031.mp3")]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.wait()

    async def send_all_forms(self, page: Page) -> None:
        await page.addScriptTag(path=str(ASSETS_PATH / "send-all-forms.js"))
        await page.waitFor(3000)

    async def extract_links(self, page: Page) -> set[str]:
        return set(
            await page.evaluate(
                """() => [...document.getElementsByTagName('a')]
                    .filter(a => a.host === location.host)
                    .map(a => a.href)"""
            )
        )

    async def handle_request(
        self,
        req: Request,
        check_queue: asyncio.Queue[RequestInfo],
    ) -> None:
        # req.frame.parentFrame is None
        # req.resourceType
        # req.isNavigationRequest()
        # req.method
        # req.url
        # req.headers
        # req.postData
        # Отключаем картинки для ускорения
        # https://stackoverflow.com/questions/43405952/is-there-any-way-to-get-all-mime-type-by-the-resourcetype-of-chrome/47166602#47166602
        if req.resourceType == "image" or req.url.endswith(".ico"):
            await req.abort()
            return

        # Костыль
        cookies = {
            c["name"]: c["value"]
            for c in (
                await req._client.send(
                    "Network.getCookies", {"urls": [req.url]}
                )
            )["cookies"]
        }

        await check_queue.put(
            RequestInfo(
                req.method,
                req.url,
                req.headers.copy(),
                cookies,
                req.postData,
            )
        )

        await req.continue_()

    async def crawl(
        self,
        browser: Browser,
        crawl_queue: asyncio.Queue[tuple[int, str]],
        seen_urls: set[str],
        url_hosts: Counter[str],
        check_queue: asyncio.Queue[RequestInfo],
    ) -> None:
        self.log.info("started crawl task")

        while True:
            # Выносится за try чтобы избежать вывод asyncio.exceptions.CancelledError
            url, depth = await crawl_queue.get()

            try:
                host = urlsplit(url).netloc

                if (
                    (depth < 0)
                    or (url in seen_urls)
                    or (url_hosts[host] >= self.crawl_per_host)
                ):
                    continue

                # Создаем новую страницу
                page = await browser.newPage()
                # Затем перехватываем все запросы
                await page.setRequestInterception(True)
                page.on(
                    "request",
                    lambda req: asyncio.ensure_future(
                        self.handle_request(req, check_queue)
                    ),
                )

                # Это неправильно, но если после await разместить, то лимиты не
                # будут работать
                seen_urls.add(url)
                url_hosts[host] += 1

                self.log.debug(f"crawl: {depth=}, {url=}")

                await page.goto(
                    url,
                    timeout=10000,
                    waitUntil=["domcontentloaded", "networkidle2"],
                )
                await self.send_all_forms(page)
                if depth > 0:
                    links = await self.extract_links(page)
                    for link in links:
                        await crawl_queue.put((link, depth - 1))

                # Future exception was never retrieved
                # future: <Future finished exception=NetworkError('Protocol error (Target.sendMessageToTarget): No session with given id')>
                await page.close()
            except pyppeteer.errors.TimeoutError:
                self.log.warn("timed out")
            except pyppeteer.errors.PyppeteerError as ex:
                self.log.warn(ex)
            except Exception as ex:
                self.log.exception(ex)
            finally:
                crawl_queue.task_done()

    @asynccontextmanager
    async def get_http_client(self) -> typ.AsyncIterator[aiohttp.ClientSession]:
        tim = aiohttp.ClientTimeout(total=15.0)
        async with aiohttp.ClientSession(timeout=tim) as client:
            yield client

    def inject(self, params, data) -> typ.Iterator[tuple[dict, dict]]:
        params = dict(params or {})
        data = dict(data or {})
        for i in params:
            cp = params.copy()
            cp[i] += QOUTES
            yield cp, data
        for i in data:
            cp = data.copy()
            cp[i] += QOUTES
            yield params, cp

    async def check_sqli(self, check_queue: asyncio.Queue[RequestInfo]) -> None:
        self.log.info("started check sqli task")
        async with self.get_http_client() as http_client:
            while True:
                method, url, headers, cookies, data = await check_queue.get()
                try:
                    url, _ = urldefrag(url)
                    params = None
                    if data:
                        try:
                            data, _ = parse_payload(data, headers)
                        except ValueError as ex:
                            self.log.warning(ex)
                            continue
                    else:
                        url, params = parse_query_params(url)
                        if not params:
                            self.log.debug("no data to check")
                            continue
                    # Проверяем каждый переданный параметр
                    for params, data in self.inject(params, data):
                        self.log.debug(
                            f"check sqli: {method=}, {url=}, {params=}, {data=}"
                        )
                        response: ClientResponse = await http_client.request(
                            method,
                            url,
                            params=params,
                            data=data,
                            cookies=cookies,
                            headers=headers,
                        )
                        contents = await response.text()
                        if not (match := SQLI_REGEX.search(contents)):
                            continue
                        self.log.info(
                            f"sqli detected: {method=}, {url=}, {params=}, {data=}, {match[0]=}",
                        )
                        res = {
                            "method": method,
                            "url": url,
                            "params": params,
                            "data": data,
                            "cookies": cookies,
                            "headers": headers,
                            "match": match[0],
                        }
                        js = json.dumps(res, ensure_ascii=False, sort_keys=True)
                        self.output.write(js)
                        self.output.flush()
                        await self.squeal()
                        break
                except asyncio.TimeoutError:
                    self.log.warn("timed out")
                except aiohttp.ClientError as ex:
                    self.log.warn(ex)
                except Exception as ex:
                    self.log.exception(ex)
                finally:
                    check_queue.task_done()

    async def run(self) -> None:
        crawl_queue = asyncio.Queue()

        for x in filter(None, map(str.strip, self.input)):
            crawl_queue.put_nowait((normalize_url(x), self.crawl_depth))

        browser = await pyppeteer.launch(
            headless=not self.show_browser,
            defaultViewport=False,
            args=["--no-sandbox"],
        )

        seen_urls = set()
        seen_urls = set()
        url_hosts = Counter()
        check_queue = asyncio.Queue()

        crawlers = [
            asyncio.create_task(
                self.crawl(
                    browser,
                    crawl_queue,
                    seen_urls,
                    url_hosts,
                    check_queue,
                )
            )
            for _ in range(self.crawlers)
        ]

        sqli_checkers = [
            asyncio.create_task(
                self.check_sqli(
                    check_queue,
                )
            )
            for _ in range(self.sqli_checkers)
        ]

        await crawl_queue.join()

        for t in crawlers:
            t.cancel()

        # await asyncio.gather(*crawl_tasks, return_exceptions=True)
        await browser.close()

        await check_queue.join()

        for t in sqli_checkers:
            t.cancel()

        self.log.info("seen urls: %d", len(seen_urls))

    @classmethod
    def parse_args(cls, argv: typ.Sequence[str] | None) -> argparse.Namespace:
        parser = argparse.ArgumentParser(
            description=cls.__doc__,
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        )
        parser.add_argument(
            "-i", "--input", help="input", type=argparse.FileType(), default="-"
        )
        parser.add_argument(
            "-o",
            "--output",
            help="output",
            type=argparse.FileType("w+"),
            default="-",
        )
        parser.add_argument(
            "-d",
            "--crawl-depth",
            "--depth",
            help="max crawling depth",
            type=int,
            default=2,
        )
        parser.add_argument(
            "--crawl-per-host",
            help="max links to crawl per host",
            type=int,
            default=50,
        )
        parser.add_argument(
            "--crawlers",
            help="number of crawlers",
            type=int,
            default=20,
        )
        parser.add_argument(
            "--sqli-checkers",
            help="number of sqli checkers",
            type=int,
            default=10,
        )
        parser.add_argument(
            "--show-browser",
            help="show the browser",
            default=False,
            action=argparse.BooleanOptionalAction,
        )
        parser.add_argument(
            "-v",
            "--verbosity",
            help="be more verbosity",
            action="count",
            default=0,
        )
        return parser.parse_args(argv)

    @classmethod
    def start(cls, argv: typ.Sequence[str] | None = None) -> None:
        asyncio.run(cls(**vars(cls.parse_args(argv))).run())
