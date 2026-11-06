# Инструкция по настройке Cloudflare WAF и предотвращению блокировки Googlebot

## Проблема
Googlebot индексирует сайты с IP-адресов в США (Google LLC, автономная система AS15169).
Если в Cloudflare включен режим **Under Attack Mode** или правило WAF блокирует весь зарубежный трафик (geoblock «только РФ»), Googlebot сталкивается с JavaScript Challenge или Cloudflare Turnstile Captcha. Так как бот не может интерактивно пройти капчу, он получает HTTP-код 403 Forbidden или 503 Service Unavailable, и сайт полностью исключается из индекса Google.

---

## 1. Режим безопасности Cloudflare (Security Level)
1. Откройте панель Cloudflare: `focus-photocompany.ru` -> **Security** -> **Settings**.
2. Убедитесь, что **Security Level** установлен в **Medium** или **Low**.
3. **КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО** оставлять постоянно включенным режим **"I'm Under Attack!"**. Включайте его исключительно на время активной тяжелой DDoS-атаки.

---

## 2. Настройка правила обхода для поисковых ботов (Verified Bots Bypass)
Создайте приоритетное правило в **Security** -> **WAF** -> **Custom Rules**:

* **Rule Name:** `Allow Verified Bots & Search Crawlers`
* **If incoming requests match:**
  ```text
  (cf.client.bot) or (ip.geoip.asnum in {15169 13238 8075})
  ```
  *(15169 = Google LLC, 13238 = Yandex, 8075 = Microsoft/Bing)*
* **Then choose an action:** `Skip`
* **WAF components to skip:**
  - All remaining custom rules
  - Rate limiting rules
  - Browser Integrity Check
  - Managed Challenge

---

## 3. Если требуется геоблокировка (только РФ)
Если на сервере необходимо ограничить доступ пользователям только из России, условие WAF-правила **обязано** исключать верифицированных ботов:

* **Rule Name:** `Block Non-RU Traffic Except Search Bots`
* **Expression:**
  ```text
  (not ip.geoip.country in {"RU"} and not cf.client.bot and not ip.geoip.asnum in {15169 13238 8075})
  ```
* **Action:** `Managed Challenge` или `Block`.

---

## 4. Настройки SSL/TLS и HTTPS
* **SSL/TLS Mode:** `Full (Strict)`
* **Always Use HTTPS:** `ON` (автоматический 301 редирект с http на https)
* **Automatic HTTPS Rewrites:** `ON`
* **Minimum TLS Version:** `1.2`
* **HTTP/2 & HTTP/3 (QUIC):** `ON` (ускоряет Core Web Vitals).
