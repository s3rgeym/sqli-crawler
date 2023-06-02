from __future__ import annotations

import argparse
import asyncio
import base64
import itertools
import json as jsonlib
import logging
import re
import typing as typ
from collections import Counter
from contextlib import asynccontextmanager
from dataclasses import dataclass
from os import getenv
from pathlib import Path
from urllib.parse import urldefrag, urlsplit

import aiohttp
from aiohttp.client import ClientResponse
from playwright.async_api import Browser, BrowserContext
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page, Request, Route
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from .color_log import ColorHandler
from .utils import normalize_url, parse_query_params

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

QUOTES = "'\""


class InterceptedRequest(typ.NamedTuple):
    method: str
    url: str
    cookies: dict
    headers: dict
    data: dict

    @property
    def content_type(self) -> str:
        return self.headers.get("content-type", "")

    @property
    def mime_type(self) -> str:
        return self.content_type.split(";")[0].lower()

    @property
    def is_urlencoded(self) -> None:
        return self.mime_type == "application/x-www-form-urlencoded"

    @property
    def is_json(self) -> bool:
        return self.mime_type == "application/json"


@dataclass
class SQLiCrawler:
    """SQLi Crawler"""

    input: typ.TextIO
    output: typ.TextIO
    checks_per_resource: int
    crawl_depth: int
    crawl_per_host: int
    executable_path: str | Path | None
    num_checkers: int
    num_crawlers: int
    show_browser: bool
    verbosity: int

    def __post_init__(self) -> None:
        log_level = max(logging.DEBUG, logging.ERROR - self.verbosity * 10)
        self.log = logging.getLogger(__name__)
        self.log.setLevel(log_level)
        self.log.addHandler(ColorHandler())

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
        await page.add_script_tag(path=ASSETS_PATH / "send-all-forms.js")

    async def extract_links(self, page: Page) -> set[str]:
        return set(
            await page.evaluate(
                """[...document.getElementsByTagName('a')]
                    .filter(a => a.host === location.host)
                    .map(a => a.href)"""
            )
        )

    async def crawl(
        self,
        context: BrowserContext,
        crawl_queue: asyncio.Queue[tuple[int, str]],
        crawled_urls: set[str],
        crawled_hosts: Counter[str],
        check_queue: asyncio.Queue[InterceptedRequest],
    ) -> None:
        while True:
            # Выносится за try чтобы избежать вывод asyncio.exceptions.CancelledError
            url, depth = await crawl_queue.get()

            try:
                host = urlsplit(url).netloc

                if (
                    (depth < 0)
                    or (url in crawled_urls)
                    or (crawled_hosts[host] >= self.crawl_per_host)
                ):
                    continue

                # Это неправильно, но если после await разместить, то лимиты не
                # будут работать
                crawled_urls.add(url)
                crawled_hosts[host] += 1

                # Создаем новую страницу
                page: Page = await context.new_page()

                async def handle(route: Route, request: Request) -> None:
                    if request.resource_type == "image":
                        await route.abort()
                        return

                    if (
                        request.resource_type
                        in ("document", "xhr", "fetch", "other")
                        and (request.post_data_json or "?" in request.url)
                        and urlsplit(page.url).netloc
                        == urlsplit(request.url).netloc
                    ):
                        url, _ = urldefrag(request.url)
                        cookies = {
                            c["name"]: c["value"]
                            for c in await context.cookies(url)
                        }
                        headers = await request.all_headers()
                        await check_queue.put(
                            InterceptedRequest(
                                method=request.method.upper(),
                                url=url,
                                headers=headers,
                                cookies=cookies,
                                data=dict(request.post_data_json or {}),
                            )
                        )

                    # Каждую страницу мы открываем в новой вкладке, так легко отменить переход на новую страницу при отправке всех форм
                    if (
                        request.is_navigation_request()
                        and page.url != "about:blank"
                    ):
                        self.log.debug(
                            "aborted: [%s] %s", request.method, request.url
                        )
                        # Без aborted падает с ошибкой
                        await route.abort("aborted")
                        return

                    await route.continue_()

                # TypeError: Passing coroutines is forbidden, use tasks explicitly.
                await page.route(
                    "**/*",
                    handle
                    # lambda route, request: asyncio.create_task(
                    #     handle(route, request)
                    # ),
                )

                self.log.debug("crawl: %s", url)

                await page.goto(url, timeout=10_000, wait_until="networkidle")
                # Leave site?
                # Changes you made may not be saved.
                # https://stackoverflow.com/questions/64569446/can-i-ignore-the-leave-site-dialog-when-browsing-headless-using-puppeteer
                await page.evaluate("window.onbeforeunload = null")
                await self.send_all_forms(page)
                if depth > 0:
                    links = await self.extract_links(page)
                    for link in links:
                        await crawl_queue.put((link, depth - 1))
                await page.close()
            except PlaywrightTimeoutError:
                self.log.warn("crawl timed out")
            except Exception as ex:
                self.log.exception(ex)
            finally:
                crawl_queue.task_done()

    @asynccontextmanager
    async def get_http_client(self) -> typ.AsyncIterator[aiohttp.ClientSession]:
        tim = aiohttp.ClientTimeout(total=15.0)
        async with aiohttp.ClientSession(timeout=tim) as client:
            yield client

    def add_quotes(
        self,
        params: dict | None,
        data: dict | None,
        cookies: dict | None,
    ) -> typ.Iterator[
        tuple[dict | None, dict | None, dict | None, dict | None]
    ]:
        for i in params or ():
            cp = params.copy()
            cp[i] += QUOTES
            yield cp, data, cookies
        for k, v in (data or {}).items():
            if isinstance(v, (int, float, bool)):
                v = str(v).lower()
            elif not isinstance(v, str):
                continue
            cp = data.copy()
            cp[k] = v + QUOTES
            yield params, cp, cookies
        for i in cookies or "":
            cp = cookies.copy()
            cp[i] += QUOTES
            yield params, data, cp

    def hash_request(
        self,
        method: str,
        url: str,
        params: dict | None,
        cookies: dict,
        data: dict | None,
        data_type: str,
    ) -> str:
        # POST|https://www.linux.org.ru/ajax_login_process||JSESSIONID,tz,CSRF_TOKEN|nick,passwd,csrf|application/x-www-form-urlencoded
        d = locals()
        d.pop("self")
        return "|".join(
            ",".join(set(v))
            if isinstance(v, dict)
            else ("" if v is None else v)
            for v in d.values()
        )

    # def get_form_data(self, data: dict | None) -> aiohttp.FormData | None:
    #     if not data:
    #         return
    #     fd = aiohttp.FormData()
    #     for name, value in data.items():
    #         fd.add_field(name, value)
    #     return fd

    async def check_sqli(
        self,
        check_queue: asyncio.Queue[InterceptedRequest],
        request_hashes: set[str],
    ) -> None:
        async with self.get_http_client() as http_client:
            while True:
                req = await check_queue.get()
                try:
                    method, url, cookies, headers, data = req
                    params = None
                    if not data:
                        url, params = parse_query_params(url)

                        if not params:
                            self.log.debug("no parameters")
                            continue

                    # Уменьшаем количество запросов
                    req_hash = self.hash_request(
                        method,
                        url,
                        params,
                        cookies,
                        data,
                        req.mime_type,
                    )

                    if req_hash in request_hashes:
                        self.log.debug("already checked: %s", req_hash)
                        continue

                    request_hashes.add(req_hash)

                    quoted = self.add_quotes(params, data, cookies)

                    for params, data, cookies in (
                        itertools.islice(quoted, 0, self.checks_per_resource)
                        if self.checks_per_resource > 0
                        else quoted
                    ):
                        self.log.debug(
                            f"check sqli: {method=}, {url=}, {params=}, {data=}, {cookies=}"
                        )

                        response = await http_client.request(
                            method,
                            url,
                            params=params,
                            data=data if data and req.is_urlencoded else None,
                            json=[None, data][data and req.is_json],
                            cookies=cookies,
                            headers=headers,
                        )

                        contents = await response.text()

                        if not (match := SQLI_REGEX.search(contents)):
                            continue
                        self.log.info(
                            "sqli detected: [%s] %s; see output", method, url
                        )
                        res = {
                            "method": method,
                            "url": url,
                            "status_code": response.status,
                            "params": params,
                            "cookies": cookies,
                            "headers": req.headers,
                            "data": data,
                            "data_type": req.mime_type,
                            "match": match[0],
                        }
                        js = jsonlib.dumps(
                            {k: v for k, v in res.items() if v},
                            ensure_ascii=False,
                        )
                        self.output.write(js)
                        self.output.flush()
                        await self.squeal()
                        break
                except asyncio.TimeoutError:
                    self.log.warn("check sqli timed out")
                except Exception as ex:
                    self.log.exception(ex)
                finally:
                    check_queue.task_done()

    async def run(self) -> None:
        crawl_queue = asyncio.Queue()

        for x in filter(None, map(str.strip, self.input)):
            crawl_queue.put_nowait((normalize_url(x), self.crawl_depth))

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(
                headless=not self.show_browser,
                executable_path=self.executable_path
                if self.executable_path
                else getenv("CHROME_EXECUTABLE_PATH"),
            )

            context = await browser.new_context()

            crawled_urls = set()
            crawled_hosts = Counter()
            check_queue = asyncio.Queue()

            crawlers = [
                asyncio.ensure_future(
                    self.crawl(
                        context,
                        crawl_queue,
                        crawled_urls,
                        crawled_hosts,
                        check_queue,
                    )
                )
                for _ in range(self.num_crawlers)
            ]

            request_hashes: set[str] = set()

            checkers = [
                asyncio.ensure_future(
                    self.check_sqli(
                        check_queue,
                        request_hashes,
                    )
                )
                for _ in range(self.num_checkers)
            ]

            await crawl_queue.join()

            for t in crawlers:
                t.cancel()

            await browser.close()

        await check_queue.join()

        for t in checkers:
            t.cancel()

        self.log.info("seen urls: %d", len(crawled_urls))
        self.log.info("checked urls: %d", len(request_hashes))

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
            "--num-crawlers",
            help="number of crawlers",
            type=int,
            default=20,
        )
        parser.add_argument(
            "--num-checkers",
            help="number of sqli checkers",
            type=int,
            default=10,
        )
        parser.add_argument(
            "--checks-per-resource",
            help="max number of sqli checks per resource (no limit = -1)",
            type=int,
            default=-1,
        )
        parser.add_argument(
            "--executable-path",
            help="chrome-like browser executable path. use environment variable `CHROME_EXECUTABLE_PATH` instead",
            type=Path,
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
