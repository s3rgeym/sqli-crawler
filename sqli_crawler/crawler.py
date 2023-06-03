from __future__ import annotations

import argparse
import asyncio
import itertools
import json as jsonlib
import logging
import os
import re
import typing as typ
from collections import Counter
from contextlib import asynccontextmanager
from dataclasses import dataclass
from http.cookies import SimpleCookie
from os import getenv
from pathlib import Path
from urllib.parse import parse_qsl, urldefrag, urlsplit

import aiohttp
from aiohttp.client import ClientResponse
from playwright.async_api import Browser, BrowserContext
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page, Request, Route
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from .color_log import ColorHandler
from .utils import MimeType, normalize_url

ASSETS_PATH = Path(__file__).resolve().parent / "assets"

SQLI_REGEX: re.Pattern = re.compile(
    "|".join(
        [
            r"You have an error in your SQL syntax",
            r"Unclosed quotation mark after the character string",
            # Иногда при ошибке выводится полный запрос
            r"SELECT \* FROM",
            # Название PHP функций для работы с БД (eq, mysql_query или pg_select)
            r"\bmysqli?_\w+",
            r"\bpg_(query|select|insert|update|fetch)",
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


# immutable
class CheckRequest(typ.NamedTuple):
    method: str
    url: str
    headers: dict
    body: dict | None


@dataclass
class SQLiCrawler:
    """SQLi Crawler"""

    input: typ.TextIO
    output: typ.TextIO
    req_checks: int | None
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

    async def submit_forms(self, page: Page) -> None:
        await page.add_script_tag(path=ASSETS_PATH / "submit-forms.js")

    async def extract_links(self, page: Page) -> set[str]:
        return set(
            await page.evaluate(
                """[...document.getElementsByTagName('a')]
                    .filter(a => a.host === location.host)
                    .map(a => a.href)"""
            )
        )

    async def handle_route(
        self,
        route: Route,
        request: Request,
        page: Page,
        check_queue: asyncio.Queue[CheckRequest],
    ) -> None:
        if request.resource_type == "image":
            await route.abort()
            return

        if (
            request.resource_type in ("document", "xhr", "fetch", "other")
            and urlsplit(request.url).netloc == urlsplit(page.url).netloc
        ):
            headers = await request.all_headers()
            await check_queue.put(
                CheckRequest(
                    method=request.method,
                    url=request.url,
                    headers=headers,
                    body=request.post_data,
                )
            )

        # Каждую страницу мы открываем в новой вкладке, так легко отменить переход на новую страницу при отправке всех форм
        if request.is_navigation_request() and page.url != "about:blank":
            self.log.debug("aborted: [%s] %s", request.method, request.url)
            # Без aborted падает с ошибкой
            await route.abort("aborted")
            return

        await route.continue_()

    async def crawl(
        self,
        context: BrowserContext,
        crawl_queue: asyncio.Queue[tuple[int, str]],
        seen_urls: set[str],
        seen_hosts: Counter[str],
        check_queue: asyncio.Queue[CheckRequest],
    ) -> None:
        while True:
            # Выносится за try чтобы избежать вывод asyncio.exceptions.CancelledError
            url, depth = await crawl_queue.get()
            self.log.debug(f"crawl: {depth=}, {url=}")

            try:
                host = urlsplit(url).netloc

                if (
                    (depth < 0)
                    or (url in seen_urls)
                    or (seen_hosts[host] >= self.crawl_per_host)
                ):
                    self.log.debug("skip alredy seen")
                    continue

                # Это неправильно, но если после await разместить, то лимиты не
                # будут работать
                seen_urls.add(url)
                seen_hosts[host] += 1

                # вкладки иногда зависают и остаются открытыми, что может уронить браузер...
                # закрываем лишние вкладки
                # run_before_unload=True нужно чтобы закрыть вкладку без подтверждения Leave
                # >>> list(range(15))[:-10]
                # [0, 1, 2, 3, 4]
                await asyncio.gather(
                    *(
                        p.close(run_before_unload=True)
                        for p in context.pages[: -self.num_crawlers]
                    ),
                    return_exceptions=True,
                )

                # открываем новую страницу
                page = await context.new_page()

                await page.route(
                    "**/*",
                    lambda route, request: asyncio.create_task(
                        self.handle_route(route, request, page, check_queue)
                    ),
                )

                await page.goto(url)
                if depth > 0:
                    links = await self.extract_links(page)
                    for link in links:
                        await crawl_queue.put((link, depth - 1))
                # Отправляем все формы
                await self.submit_forms(page)
                # Ждем пока запросы отправтся
                # await page.wait_for_load_state("networkidle")
                await page.wait_for_timeout(3000)
            except PlaywrightTimeoutError:
                self.log.warn("crawl timed out")
            except PlaywrightError as ex:
                self.log.warn(ex)
            except Exception as ex:
                self.log.exception(ex)
            finally:
                crawl_queue.task_done()

    @asynccontextmanager
    async def get_session(self) -> typ.AsyncIterator[aiohttp.ClientSession]:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=15.0)
        ) as session:
            yield session

    def hash_request(
        self,
        method: str,
        url: str,
        params: dict | None,
        data: dict | None,
        json: dict | None,
    ) -> str:
        return "|".join(
            ",".join(set(v)) if isinstance(v, dict) else [v, ""][v is None]
            for k, v in locals().items()
            if k != "self"
        )

    # def get_form_data(self, data: dict | None) -> aiohttp.FormData | None:
    #     if not data:
    #         return
    #     fd = aiohttp.FormData()
    #     for name, value in data.items():
    #         fd.add_field(name, value)
    #     return fd

    def inject(self, *args: dict | None) -> typ.Iterator[tuple[dict, ...]]:
        for index, data in enumerate(args):
            if not data:
                continue
            for k, v in data.items():
                if v is None:
                    v = "null"
                elif isinstance(v, (int, float, bool)):
                    v = str(v).lower()
                elif not isinstance(v, str):
                    continue
                copy = data.copy()
                copy[k] = v + QUOTES
                yield *args[:index], copy, *args[index + 1 :]

    async def check_sqli(
        self,
        check_queue: asyncio.Queue[CheckRequest],
        seen_requests: set[str],
    ) -> None:
        async with self.get_session() as session:
            while True:
                req = await check_queue.get()

                try:
                    method, url, headers, body = req
                    method = method.upper()
                    url, _ = urldefrag(url)
                    sp = urlsplit(url)
                    url = sp._replace(query="").geturl()
                    params = dict(parse_qsl(sp.query))
                    data = json = None

                    if body:
                        mime = MimeType.parse(headers.pop("content-type", 0))
                        if mime.type == "application/x-www-form-urlencoded":
                            data = dict(parse_qsl(body))
                        elif mime.type == "application/json":
                            json = jsonlib.loads(body)
                        else:
                            self.log.warn(
                                "unknown or unexpected mime type: %s", mime.type
                            )
                            continue

                    if not params and not data and not json:
                        self.log.warn("nothing to check")

                    # Уменьшаем количество запросов
                    req_hash = self.hash_request(
                        method,
                        url,
                        params,
                        data,
                        json,
                    )

                    if req_hash in seen_requests:
                        self.log.debug("already checked: %s", req_hash)
                        continue

                    seen_requests.add(req_hash)

                    cookies = None

                    if cookie := headers.pop("cookie", 0):
                        d = SimpleCookie()
                        d.load(cookie)
                        cookies = {k: v.value for k, v in d.items()}

                    for params, data, json in itertools.islice(
                        self.inject(params, data, json), 0, self.req_checks
                    ):
                        self.log.debug(
                            f"check sqli: {method=}, {url=}, {params=}, {data=}, {cookies=}"
                        )

                        response = await session.request(
                            method,
                            url,
                            params=params,
                            data=data,
                            json=json,
                            cookies=cookies,
                            headers=headers,
                        )

                        # >>> open('/dev/urandom', 'rb').read(10).decode(errors='ignore')
                        # 'cF\x13Y:'
                        # >>> open('/dev/urandom', 'rb').read(10).decode(errors='replace')
                        # '^�/�\x07[w��['
                        contents = await response.text(errors="ignore")

                        if not (match := SQLI_REGEX.search(contents)):
                            continue

                        self.log.info(
                            "sqli detected: [%s] %s; see output", method, url
                        )

                        res = {
                            "method": method,
                            "url": url,
                            "params": params,
                            "headers": req.headers,
                            "cookies": cookies,
                            "data": data,
                            "json": json,
                            "match": match[0],
                            "status": response.status,
                        }

                        js = jsonlib.dumps(
                            {k: v for k, v in res.items() if v},
                            ensure_ascii=False,
                        )

                        self.output.write(js + os.linesep)
                        self.output.flush()
                        await self.squeal()
                        break
                except asyncio.TimeoutError:
                    self.log.warn("check sqli timed out")
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

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(
                headless=not self.show_browser,
                executable_path=self.executable_path
                if self.executable_path
                else getenv("CHROME_EXECUTABLE_PATH"),
            )

            context = await browser.new_context()
            context.set_default_navigation_timeout(15_000)

            seen_urls = set()
            seen_hosts = Counter()
            check_queue = asyncio.Queue()

            crawlers = [
                asyncio.ensure_future(
                    self.crawl(
                        context,
                        crawl_queue,
                        seen_urls,
                        seen_hosts,
                        check_queue,
                    )
                )
                for _ in range(self.num_crawlers)
            ]

            seen_requests = set()

            checkers = [
                asyncio.ensure_future(
                    self.check_sqli(
                        check_queue,
                        seen_requests,
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

        self.log.info("crawled: %d", len(seen_urls))
        self.log.info("checked: %d", len(seen_requests))

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
            default=25,
        )
        parser.add_argument(
            "--num-checkers",
            help="number of sqli checkers",
            type=int,
            default=10,
        )
        parser.add_argument(
            "--req-checks", help="max checks for request", type=int
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
