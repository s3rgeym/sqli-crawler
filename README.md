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
usage: sqli-crawler [-h] [-i INPUT] [-o OUTPUT] [-d CRAWL_DEPTH] [--crawl-per-host CRAWL_PER_HOST] [--crawlers CRAWLERS] [--sqli-checkers SQLI_CHECKERS]
                    [--executable-path EXECUTABLE_PATH] [--show-browser | --no-show-browser] [-v]

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
                        max links to crawl per host (default: 120)
  --crawlers CRAWLERS   number of crawlers (default: 30)
  --sqli-checkers SQLI_CHECKERS
                        number of sqli checkers (default: 10)
  --executable-path EXECUTABLE_PATH
                        chrom* executable path. use environment variable `CHROME_EXECUTABLE_PATH` instead (default: None)
  --show-browser, --no-show-browser
                        show the browser (default: False)
  -v, --verbosity       be more verbosity (default: 0)
```
