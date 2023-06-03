# SQLi Crawler

> WARNING: IN ACTIVE DEVELOPMEMT!!!

Crawling links and forms using headless Chromium and check its to SQLi.

Install from source:

```bash
git clone && cd
pipx install --force .
```

Usage:

```bash
~/workspace/sqli-crawler main
❯ sqli-crawler -h
usage: sqli-crawler [-h] [-i INPUT] [-o OUTPUT] [-d CRAWL_DEPTH] [--crawl-per-host CRAWL_PER_HOST] [--num-crawlers NUM_CRAWLERS] [--num-checkers NUM_CHECKERS]
                    [--req-checks REQ_CHECKS] [--executable-path EXECUTABLE_PATH] [--show-browser | --no-show-browser] [-v]

SQLi Crawler

options:
  -h, --help            show this help message and exit
  -i INPUT, --input INPUT
                        input (default: -)
  -o OUTPUT, --output OUTPUT
                        output (default: -)
  -d CRAWL_DEPTH, --crawl-depth CRAWL_DEPTH, --depth CRAWL_DEPTH
                        max crawling depth (default: 2)
  --crawl-per-host CRAWL_PER_HOST
                        max links to crawl per host (default: 50)
  --num-crawlers NUM_CRAWLERS
                        number of crawlers (default: 25)
  --num-checkers NUM_CHECKERS
                        number of sqli checkers (default: 10)
  --req-checks REQ_CHECKS
                        max checks for request (default: None)
  --executable-path EXECUTABLE_PATH
                        chrome-like browser executable path. use environment variable `CHROME_EXECUTABLE_PATH` instead (default: None)
  --show-browser, --no-show-browser
                        show the browser (default: False)
  -v, --verbosity       be more verbosity (default: 0)
```

```bash
poetry run playwright install chromium
```

```json
{
  "method": "GET",
  "url": "https://<cut>/fsrch_res.php",
  "status_code": 200,
  "params": { "Lang": "it", "SrchText": "test'\"", "SrchInto": "All" },
  "cookies": { "PHPSESSID": "af9v7sp51r5va8hrtqog05auo0" },
  "headers": {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "referer": "https://<cut>/home.php?Lang=it",
    "upgrade-insecure-requests": "1",
    "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
    "sec-ch-ua": "\"Not.A/Brand\";v=\"8\", \"Chromium\";v=\"114\"",
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": "\"Linux\""
  },
  "match": "You have an error in your SQL syntax"
}
```

## Notes

`pyppeteer` падал с загадочными ошибками, поэтому был заменен на `playwright`.

```
[E] Connection closed while reading from the driver
Traceback (most recent call last):
  ...
playwright._impl._api_types.TimeoutError: Timeout 15000ms exceeded.

=========================== logs ===========================
navigating to "https://5elementshostel.de/frankfurt/#reviews", waiting until "networkidle"
============================================================

  File "/home/sergey/.cache/pypoetry/virtualenvs/sqli-crawler-pMyiD5aU-py3.11/lib/python3.11/site-packages/playwright/_impl/_connection.py", line 97, in inner_send
    result = next(iter(done)).result()
             ^^^^^^^^^^^^^^^^^^^^^^^^^
Exception: Connection closed while reading from the driver
```

Initiator пока не реализован.

https://github.com/microsoft/playwright/issues/16326
