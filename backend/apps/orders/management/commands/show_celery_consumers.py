import base64
import glob
import json
import os
import re
from urllib import request, parse, error

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Show RabbitMQ consumers and queue stats for the Celery queue. "
        "Defaults to http://localhost:15672 with guest/guest credentials."
    )

    def add_arguments(self, parser):
        parser.add_argument("--host", default="localhost")
        parser.add_argument("--port", type=int, default=15672)
        parser.add_argument("--user", default="guest")
        parser.add_argument("--password", default="guest")
        parser.add_argument("--vhost", default="/")
        parser.add_argument("--queue", default="celery")
        parser.add_argument(
            "--log-glob",
            default="worker*.log",
            help=(
                "Glob pattern for worker log files used to infer chunk-to-worker mapping "
                "(default: worker*.log)."
            ),
        )
        parser.add_argument(
            "--skip-log-mapping",
            action="store_true",
            help="Skip parsing worker logs for chunk-to-worker mapping.",
        )

    def _extract_chunk_worker_mapping(self, log_glob):
        chunk_start_re = re.compile(
            r"CHUNK\s+(?P<chunk_num>\d+)/(?P<total_chunks>\d+):\s+"
            r"Starting with\s+(?P<orders>\d+)\s+orders\s+"
            r"\(worker=(?P<worker>[^)]+)\)"
        )

        log_files = sorted(glob.glob(log_glob), key=os.path.getmtime)
        if not log_files:
            return {}, []

        mapping = {}
        for log_path in log_files:
            try:
                with open(log_path, "r", encoding="utf-8", errors="ignore") as handle:
                    for line in handle:
                        match = chunk_start_re.search(line)
                        if not match:
                            continue

                        chunk_num = int(match.group("chunk_num"))
                        total_chunks = int(match.group("total_chunks"))
                        mapping[(chunk_num, total_chunks)] = {
                            "worker": match.group("worker"),
                            "orders": int(match.group("orders")),
                            "source": os.path.basename(log_path),
                        }
            except OSError:
                continue

        return mapping, log_files

    def _http_get(self, url, user, password):
        req = request.Request(url)
        auth = f"{user}:{password}".encode("utf-8")
        req.add_header("Authorization", "Basic " + base64.b64encode(auth).decode())
        try:
            with request.urlopen(req, timeout=10) as resp:
                return json.load(resp)
        except error.HTTPError as e:
            self.stderr.write(f"HTTP error {e.code} for {url}: {e.reason}\n")
        except Exception as e:
            self.stderr.write(f"Error connecting to RabbitMQ API: {e}\n")
        return None

    def handle(self, *args, **options):
        host = options["host"]
        port = options["port"]
        user = options["user"]
        password = options["password"]
        vhost = options["vhost"]
        queue = options["queue"]
        log_glob = options["log_glob"]
        skip_log_mapping = options["skip_log_mapping"]

        encoded_vhost = parse.quote(vhost, safe="")
        base = f"http://{host}:{port}/api"

        # Queue info
        queue_url = f"{base}/queues/{encoded_vhost}/{parse.quote(queue, safe='')}"
        qinfo = self._http_get(queue_url, user, password)

        if qinfo is None:
            self.stderr.write("Failed to fetch queue info. Check RabbitMQ management plugin and credentials.\n")
            return

        self.stdout.write(f"Queue: {queue} (vhost={vhost})\n")
        self.stdout.write(f"  messages_ready: {qinfo.get('messages_ready')}\n")
        self.stdout.write(f"  messages_unacknowledged: {qinfo.get('messages_unacknowledged')}\n")
        self.stdout.write(f"  consumers: {qinfo.get('consumers')}\n\n")

        # Consumers list
        consumers_url = f"{base}/consumers"
        consumers = self._http_get(consumers_url, user, password)
        if consumers is None:
            self.stderr.write("Failed to fetch consumers.\n")
            return

        queue_consumers = [c for c in consumers if c.get("queue", {}).get("name") == queue]

        if not queue_consumers:
            self.stdout.write("No consumers found for this queue.\n")
            return

        self.stdout.write("Consumers attached to queue:\n")
        for c in queue_consumers:
            conn = c.get("channel_details", {})
            self.stdout.write(
                f"- consumer_tag={c.get('consumer_tag')} | connection_name={conn.get('connection_name')} | peer={conn.get('peer_host')}:{conn.get('peer_port')} | ack_required={c.get('ack_required')}\n"
            )

        if skip_log_mapping:
            self.stdout.write(
                "\nSkipped chunk-to-worker mapping (requested with --skip-log-mapping).\n"
            )
            return

        mapping, log_files = self._extract_chunk_worker_mapping(log_glob)
        self.stdout.write("\nChunk-to-worker mapping (from worker logs):\n")

        if not log_files:
            self.stdout.write(
                f"- No log files matched pattern '{log_glob}'.\n"
            )
            self.stdout.write(
                "  Start workers with --logfile (for example worker1.log, worker2.log, worker3.log), then run this command again.\n"
            )
            return

        if not mapping:
            self.stdout.write(
                "- Log files were found but no chunk start lines were detected yet.\n"
            )
            self.stdout.write(
                "  Run the async batch and retry this command after chunks start.\n"
            )
            return

        for (chunk_num, total_chunks), details in sorted(mapping.items()):
            self.stdout.write(
                f"- CHUNK {chunk_num}/{total_chunks} -> {details['worker']} "
                f"(orders={details['orders']}, source={details['source']})\n"
            )

        self.stdout.write(
            "\nTip: This mapping is inferred from worker log lines like "
            "'CHUNK X/Y: Starting ... (worker=...)'.\n"
        )
