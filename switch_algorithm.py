import os
import sys
import subprocess

NGINX_CONF_PATH = r'C:\nginx\conf\nginx.conf'

UPSTREAM_SERVERS = """\
      server 127.0.0.1:8001;
      server 127.0.0.1:8002;
      server 127.0.0.1:8003;"""

SERVER_BLOCK = """\
    server {
      listen 80;
      server_name localhost;
      location / {
        proxy_pass http://django_workers;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 30s;
      }
    }"""

CONFIGS = {
    'least_conn': f"""\
events {{ worker_connections 1024; }}
http {{
  upstream django_workers {{
    least_conn;
{UPSTREAM_SERVERS}
  }}
{SERVER_BLOCK}
}}
""",
    'round_robin': f"""\
events {{ worker_connections 1024; }}
http {{
  upstream django_workers {{
{UPSTREAM_SERVERS}
  }}
{SERVER_BLOCK}
}}
""",
    'ip_hash': f"""\
events {{ worker_connections 1024; }}
http {{
  upstream django_workers {{
    ip_hash; # ip_hash — same client always goes to same worker
{UPSTREAM_SERVERS}
  }}
{SERVER_BLOCK}
}}
""",
}

ALIASES = {'round_robin': 'round_robin', 'least_conn': 'least_conn', 'ip_hash': 'ip_hash'}


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in CONFIGS:
        print('Usage: python switch_algorithm.py <least_conn|round_robin|ip_hash>')
        sys.exit(1)

    algo = sys.argv[1]
    config_content = CONFIGS[algo]

    os.makedirs(os.path.dirname(NGINX_CONF_PATH), exist_ok=True)
    with open(NGINX_CONF_PATH, 'w') as f:
        f.write(config_content)

    result = subprocess.run(
        [r'C:\nginx\nginx.exe', '-s', 'reload'],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f'Nginx reload error: {result.stderr}')
        sys.exit(1)

    print(f'Switched to: {algo} — Nginx reloaded')


if __name__ == '__main__':
    main()
