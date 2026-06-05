import json
import math
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib import error as urllib_error
from urllib import request as urllib_request

from django.core.management.base import BaseCommand


try:
    import requests
except ImportError:  # pragma: no cover - depends on local environment.
    requests = None


class Command(BaseCommand):
    help = "Measure real getOrders API behavior using ThreadPoolExecutor HTTP GET requests."

    def add_arguments(self, parser):
        parser.add_argument(
            "--api-url",
            default="http://127.0.0.1:8000/api/v1/orders/?page=1&page_size=50",
        )
        parser.add_argument("--requests", type=int, default=200)
        parser.add_argument("--pool-sizes", default="1,5,10,15,20,30,50")
        parser.add_argument("--timeout", type=float, default=3)
        parser.add_argument("--acceptable-max-latency-ms", type=float, default=1200)
        parser.add_argument("--auth-token", default=None)
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print configuration and exit without sending HTTP requests.",
        )

    def handle(self, *args, **options):
        api_url = options["api_url"]
        request_count = options["requests"]
        pool_sizes = self.parse_pool_sizes(options["pool_sizes"])
        timeout = options["timeout"]
        acceptable_max_latency_ms = options["acceptable_max_latency_ms"]
        auth_token = options["auth_token"]
        dry_run = options["dry_run"]

        if request_count < 1:
            raise ValueError("--requests must be greater than 0")
        if timeout <= 0:
            raise ValueError("--timeout must be greater than 0")
        if acceptable_max_latency_ms <= 0:
            raise ValueError("--acceptable-max-latency-ms must be greater than 0")

        self.print_header(
            api_url=api_url,
            request_count=request_count,
            pool_sizes=pool_sizes,
            acceptable_max_latency_ms=acceptable_max_latency_ms,
            timeout=timeout,
            auth_token=auth_token,
        )

        if dry_run:
            self.stdout.write("Dry run enabled. No requests were sent.")
            return

        metrics = []
        for pool_size in pool_sizes:
            metrics.append(
                self.run_pool_experiment(
                    api_url=api_url,
                    request_count=request_count,
                    pool_size=pool_size,
                    timeout=timeout,
                    auth_token=auth_token,
                )
            )

        self.classify_metrics(metrics, acceptable_max_latency_ms)

        for metric in metrics:
            self.print_pool_result(metric)

        self.print_final_comparison(metrics)

    def parse_pool_sizes(self, raw_pool_sizes):
        pool_sizes = []
        for raw_value in raw_pool_sizes.split(","):
            value = raw_value.strip()
            if not value:
                continue
            pool_size = int(value)
            if pool_size < 1:
                raise ValueError("--pool-sizes must contain positive integers")
            pool_sizes.append(pool_size)

        if not pool_sizes:
            raise ValueError("--pool-sizes must contain at least one value")
        return pool_sizes

    def print_header(
        self,
        api_url,
        request_count,
        pool_sizes,
        acceptable_max_latency_ms,
        timeout,
        auth_token,
    ):
        self.stdout.write("WARNING:")
        self.stdout.write("Run this test only on local or staging environments.")
        self.stdout.write("Do not run load tests against production without permission and monitoring.")
        self.stdout.write("")
        self.stdout.write(
            "For serious measurements, run Django using the same server stack used "
            "in staging/production, not only the development runserver."
        )
        self.stdout.write("")
        self.stdout.write("=" * 60)
        self.stdout.write("getOrders API - Thread Pool Capacity Test")
        self.stdout.write("=" * 60)
        self.stdout.write("")
        self.stdout.write("Scenario:")
        self.stdout.write(f"- api_url: {api_url}")
        self.stdout.write(f"- total_requests: {request_count}")
        self.stdout.write(f"- tested_pool_sizes: {','.join(str(size) for size in pool_sizes)}")
        self.stdout.write(f"- acceptable_max_latency_ms: {acceptable_max_latency_ms:g}")
        self.stdout.write(f"- timeout_seconds: {timeout:g}")
        self.stdout.write(f"- auth_header: {'Authorization: Bearer <token>' if auth_token else 'not provided'}")
        self.stdout.write("")

    def run_pool_experiment(self, api_url, request_count, pool_size, timeout, auth_token):
        results = []
        worker_thread_names = set()
        total_started_at = time.perf_counter()

        with ThreadPoolExecutor(max_workers=pool_size) as executor:
            futures = []
            for request_index in range(1, request_count + 1):
                submitted_at = time.perf_counter()
                futures.append(
                    executor.submit(
                        self.fetch_once,
                        api_url,
                        timeout,
                        auth_token,
                        submitted_at,
                        request_index,
                    )
                )

            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                worker_thread_names.add(result["thread_name"])

        total_duration_ms = (time.perf_counter() - total_started_at) * 1000
        return self.build_metric(
            pool_size=pool_size,
            request_count=request_count,
            results=results,
            worker_thread_names=worker_thread_names,
            total_duration_ms=total_duration_ms,
        )

    def fetch_once(self, api_url, timeout, auth_token, submitted_at, request_index):
        worker_started_at = time.perf_counter()
        thread_name = threading.current_thread().name
        queue_delay_ms = (worker_started_at - submitted_at) * 1000

        started_at = time.perf_counter()
        try:
            status_code, body = self.send_get(api_url, timeout, auth_token)
            latency_ms = (time.perf_counter() - started_at) * 1000
            parsed_json = self.parse_json(body)

            return {
                "request_index": request_index,
                "thread_name": thread_name,
                "queue_delay_ms": queue_delay_ms,
                "latency_ms": latency_ms,
                "status_code": status_code,
                "exception": None,
                "row_count": self.count_rows(parsed_json),
                "response_size_bytes": len(body),
            }
        except Exception as exc:
            latency_ms = (time.perf_counter() - started_at) * 1000
            return {
                "request_index": request_index,
                "thread_name": thread_name,
                "queue_delay_ms": queue_delay_ms,
                "latency_ms": latency_ms,
                "status_code": None,
                "exception": exc.__class__.__name__,
                "row_count": 0,
                "response_size_bytes": 0,
            }

    def send_get(self, api_url, timeout, auth_token):
        headers = {}
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"

        if requests is not None:
            response = requests.get(api_url, headers=headers, timeout=timeout)
            return response.status_code, response.content

        request = urllib_request.Request(api_url, headers=headers, method="GET")
        try:
            with urllib_request.urlopen(request, timeout=timeout) as response:
                return response.status, response.read()
        except urllib_error.HTTPError as exc:
            return exc.code, exc.read()

    def parse_json(self, body):
        if not body:
            return None
        try:
            return json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None

    def count_rows(self, parsed_json):
        if isinstance(parsed_json, list):
            return len(parsed_json)
        if isinstance(parsed_json, dict):
            results = parsed_json.get("results")
            if isinstance(results, list):
                return len(results)
        return 0

    def build_metric(
        self,
        pool_size,
        request_count,
        results,
        worker_thread_names,
        total_duration_ms,
    ):
        latencies = [result["latency_ms"] for result in results]
        queue_delays = [result["queue_delay_ms"] for result in results]
        response_sizes = [result["response_size_bytes"] for result in results]
        exceptions = sum(1 for result in results if result["exception"])
        http_2xx = sum(1 for result in results if self.is_status_between(result["status_code"], 200, 299))
        http_4xx = sum(1 for result in results if self.is_status_between(result["status_code"], 400, 499))
        http_429 = sum(1 for result in results if result["status_code"] == 429)
        http_5xx = sum(1 for result in results if self.is_status_between(result["status_code"], 500, 599))
        successful_responses = http_2xx
        failed_responses = request_count - successful_responses
        total_duration_seconds = max(total_duration_ms / 1000, 0.000001)

        return {
            "pool_size": pool_size,
            "submitted_requests": request_count,
            "successful_responses": successful_responses,
            "failed_responses": failed_responses,
            "http_2xx": http_2xx,
            "http_4xx": http_4xx,
            "http_429": http_429,
            "http_5xx": http_5xx,
            "exceptions": exceptions,
            "total_rows_returned": sum(result["row_count"] for result in results),
            "duration_ms": total_duration_ms,
            "throughput": successful_responses / total_duration_seconds,
            "created_threads": len(worker_thread_names),
            "max_queue_ms": max(queue_delays) if queue_delays else 0,
            "avg_latency_ms": self.average(latencies),
            "max_latency_ms": max(latencies) if latencies else 0,
            "p95_latency_ms": self.percentile(latencies, 95),
            "avg_response_size_bytes": self.average(response_sizes),
            "max_response_size_bytes": max(response_sizes) if response_sizes else 0,
            "status": None,
        }

    def is_status_between(self, status_code, lower, upper):
        return status_code is not None and lower <= status_code <= upper

    def average(self, values):
        return sum(values) / len(values) if values else 0

    def percentile(self, values, percentile):
        if not values:
            return 0
        sorted_values = sorted(values)
        index = math.ceil((percentile / 100) * len(sorted_values)) - 1
        return sorted_values[max(0, min(index, len(sorted_values) - 1))]

    def classify_metrics(self, metrics, acceptable_max_latency_ms):
        eligible_metrics = []
        for metric in metrics:
            is_risky = (
                metric["failed_responses"] > 0
                or metric["http_429"] > 0
                or metric["http_5xx"] > 0
                or metric["exceptions"] > 0
                or metric["max_latency_ms"] > acceptable_max_latency_ms
            )
            if is_risky:
                metric["status"] = "TOO_HIGH_RISKY"
            else:
                eligible_metrics.append(metric)

        if not eligible_metrics:
            return

        best_throughput = max(metric["throughput"] for metric in eligible_metrics)
        too_slow_threshold = best_throughput * 0.75
        for metric in eligible_metrics:
            if metric["throughput"] < too_slow_threshold:
                metric["status"] = "TOO_SLOW"
            else:
                metric["status"] = "BALANCED_CANDIDATE"

    def print_pool_result(self, metric):
        self.stdout.write("-" * 60)
        self.stdout.write(f"Pool size: {metric['pool_size']}")
        self.stdout.write("-" * 60)
        self.stdout.write("Result:")
        self.stdout.write(f"- submitted_requests: {metric['submitted_requests']}")
        self.stdout.write(f"- successful_responses: {metric['successful_responses']}")
        self.stdout.write(f"- failed_responses: {metric['failed_responses']}")
        self.stdout.write(f"- duration_ms: {metric['duration_ms']:.2f}")
        self.stdout.write(
            f"- throughput: {metric['throughput']:.2f} successful responses/sec"
        )
        self.stdout.write(f"- created_threads: {metric['created_threads']}")
        self.stdout.write(f"- max_queue_ms: {metric['max_queue_ms']:.2f}")
        self.stdout.write(f"- avg_latency_ms: {metric['avg_latency_ms']:.2f}")
        self.stdout.write(f"- max_latency_ms: {metric['max_latency_ms']:.2f}")
        self.stdout.write(f"- p95_latency_ms: {metric['p95_latency_ms']:.2f}")
        self.stdout.write(
            "- http_counts: "
            f"2xx={metric['http_2xx']}, "
            f"4xx={metric['http_4xx']}, "
            f"429={metric['http_429']}, "
            f"5xx={metric['http_5xx']}, "
            f"exceptions={metric['exceptions']}"
        )
        self.stdout.write(f"- total_rows_returned: {metric['total_rows_returned']}")
        self.stdout.write(f"- avg_response_size_bytes: {metric['avg_response_size_bytes']:.2f}")
        self.stdout.write(f"- max_response_size_bytes: {metric['max_response_size_bytes']}")
        self.stdout.write(f"- status: {metric['status']}")
        self.stdout.write("")

    def print_final_comparison(self, metrics):
        self.stdout.write("=" * 60)
        self.stdout.write("FINAL COMPARISON")
        self.stdout.write("=" * 60)
        self.stdout.write("")
        self.stdout.write(
            "pool_size | success | failed | 2xx | 429 | 5xx | duration_ms | "
            "throughput | avg_latency | p95_latency | max_latency | max_queue | status"
        )

        for metric in metrics:
            self.stdout.write(
                f"{metric['pool_size']} | "
                f"{metric['successful_responses']} | "
                f"{metric['failed_responses']} | "
                f"{metric['http_2xx']} | "
                f"{metric['http_429']} | "
                f"{metric['http_5xx']} | "
                f"{metric['duration_ms']:.2f} | "
                f"{metric['throughput']:.2f} | "
                f"{metric['avg_latency_ms']:.2f} | "
                f"{metric['p95_latency_ms']:.2f} | "
                f"{metric['max_latency_ms']:.2f} | "
                f"{metric['max_queue_ms']:.2f} | "
                f"{metric['status']}"
            )

        recommended = self.recommended_pool_size(metrics)
        self.stdout.write("")
        self.stdout.write("Decision:")
        self.stdout.write(
            f"Recommended pool size: {recommended if recommended is not None else 'none'}"
        )
        self.stdout.write("")
        self.stdout.write("Selection rule:")
        self.stdout.write(
            "Choose the pool size with the best throughput among BALANCED_CANDIDATE results."
        )
        self.stdout.write(
            "If multiple candidates are close, prefer the smaller pool size to reduce resource usage."
        )
        self.stdout.write("")
        self.stdout.write("Final explanation:")
        self.stdout.write("- Very small pool sizes are safe but slow.")
        self.stdout.write(
            "- Very large pool sizes can increase latency, errors, database pressure, "
            "or server resource usage."
        )
        self.stdout.write(
            "- The recommended pool size is based on measured API behavior, not guessing."
        )

    def recommended_pool_size(self, metrics):
        candidates = [
            metric for metric in metrics if metric["status"] == "BALANCED_CANDIDATE"
        ]
        if not candidates:
            return None

        best_throughput = max(metric["throughput"] for metric in candidates)
        close_threshold = best_throughput * 0.95
        close_candidates = [
            metric for metric in candidates if metric["throughput"] >= close_threshold
        ]
        return min(close_candidates, key=lambda metric: metric["pool_size"])["pool_size"]
