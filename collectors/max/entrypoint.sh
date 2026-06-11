#!/bin/sh
# Заворачивает любой запуск (collector.py / login.py) через RU mobile SOCKS5
# с помощью proxychains-ng. Конфиг генерится из MAX_PROXY на старте.
#   MAX_PROXY=socks5://user:pass@host:port
set -e

if [ -n "$MAX_PROXY" ]; then
  python3 - "$MAX_PROXY" > /etc/proxychains.conf <<'PY'
import sys, urllib.parse as u
p = u.urlparse(sys.argv[1])
lines = ["strict_chain", "proxy_dns",
         "tcp_read_time_out 15000", "tcp_connect_time_out 8000",
         "[ProxyList]"]
auth = f" {p.username} {p.password}" if p.username else ""
lines.append(f"socks5 {p.hostname} {p.port}{auth}")
print("\n".join(lines))
PY
  echo "[entrypoint] proxychains -> $(python3 -c "import urllib.parse,os;print(urllib.parse.urlparse(os.environ['MAX_PROXY']).hostname)")"
  exec proxychains4 -q -f /etc/proxychains.conf "$@"
else
  echo "[entrypoint] MAX_PROXY не задан — без прокси (НЕ для боевого аккаунта!)" >&2
  exec "$@"
fi