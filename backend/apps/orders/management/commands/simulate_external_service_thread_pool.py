from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock, Thread, current_thread
from time import perf_counter, sleep

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Demonstrate external service capacity control with ThreadPoolExecutor."

    order_count = 40
    safe_external_service_capacity = 8
    balanced_pool_size = 8
    too_high_pool_size = 20
    external_call_ms = 200
    overload_penalty_ms = 250
    severe_overload_threshold = safe_external_service_capacity * 2

    def add_arguments(self, parser):
        parser.add_argument(
            "--verbose-orders",
            action="store_true",
            help="Print every order result instead of a compact sample.",
        )

    def handle(self, *args, **options):
        self.verbose_orders = options["verbose_orders"]
        self.print_scenario_header()

        metrics = [
            self.run_sequential_too_slow(),
            self.run_thread_per_call_risky(),
            self.run_thread_pool_balanced(),
            self.run_thread_pool_too_high(),
        ]

        self.print_final_comparison(metrics)

    def run_sequential_too_slow(self):
        strategy = "SEQUENTIAL_TOO_SLOW"
        state = self.create_state()
        results = []
        strategy_started_at = perf_counter()

        for order_id in range(1, self.order_count + 1):
            submitted_at = strategy_started_at
            try:
                result = self.simulate_external_delivery_check(
                    strategy=strategy,
                    order_id=order_id,
                    state=state,
                    submitted_at=submitted_at,
                    strategy_started_at=strategy_started_at,
                )
            except Exception as exc:
                result = self.build_failed_result(
                    strategy=strategy,
                    order_id=order_id,
                    submitted_at=submitted_at,
                    started_at=perf_counter(),
                    exc=exc,
                )
            results.append(result)

        total_duration_ms = self.elapsed_ms(strategy_started_at)
        metric = self.build_metrics(strategy, total_duration_ms, results, state, created_threads=1)
        self.print_strategy_report(metric)
        return metric

    def run_thread_per_call_risky(self):
        strategy = "THREAD_PER_CALL_RISKY"
        state = self.create_state()
        results = []
        results_lock = Lock()
        strategy_started_at = perf_counter()
        threads = []

        def worker(order_id, submitted_at):
            try:
                result = self.simulate_external_delivery_check(
                    strategy=strategy,
                    order_id=order_id,
                    state=state,
                    submitted_at=submitted_at,
                    strategy_started_at=strategy_started_at,
                )
            except Exception as exc:
                result = self.build_failed_result(
                    strategy=strategy,
                    order_id=order_id,
                    submitted_at=submitted_at,
                    started_at=perf_counter(),
                    exc=exc,
                )
            with results_lock:
                results.append(result)

        for order_id in range(1, self.order_count + 1):
            submitted_at = perf_counter()
            thread = Thread(
                target=worker,
                args=(order_id, submitted_at),
                name=f"raw-delivery-check-{order_id}",
            )
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        total_duration_ms = self.elapsed_ms(strategy_started_at)
        results.sort(key=lambda item: item["order_id"])

        metric = self.build_metrics(
            strategy,
            total_duration_ms,
            results,
            state,
            created_threads=self.order_count,
        )
        self.print_strategy_report(metric)
        return metric

    def run_thread_pool_balanced(self):
        return self.run_thread_pool_strategy(
            strategy="THREAD_POOL_BALANCED",
            max_workers=self.balanced_pool_size,
        )

    def run_thread_pool_too_high(self):
        return self.run_thread_pool_strategy(
            strategy="THREAD_POOL_TOO_HIGH",
            max_workers=self.too_high_pool_size,
        )

    def run_thread_pool_strategy(self, strategy, max_workers):
        state = self.create_state()
        results = []
        strategy_started_at = perf_counter()

        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix=strategy.lower()) as executor:
            future_to_order = {}
            for order_id in range(1, self.order_count + 1):
                submitted_at = perf_counter()
                future = executor.submit(
                    self.simulate_external_delivery_check,
                    strategy,
                    order_id,
                    state,
                    submitted_at,
                    strategy_started_at,
                )
                future_to_order[future] = (order_id, submitted_at)

            for future in as_completed(future_to_order):
                order_id, submitted_at = future_to_order[future]
                try:
                    result = future.result()
                except Exception as exc:
                    result = self.build_failed_result(
                        strategy=strategy,
                        order_id=order_id,
                        submitted_at=submitted_at,
                        started_at=perf_counter(),
                        exc=exc,
                    )
                results.append(result)

        total_duration_ms = self.elapsed_ms(strategy_started_at)
        results.sort(key=lambda item: item["order_id"])

        distinct_worker_count = len(state["worker_thread_names"])
        metric = self.build_metrics(
            strategy,
            total_duration_ms,
            results,
            state,
            created_threads=min(max_workers, distinct_worker_count or max_workers),
        )
        self.print_strategy_report(metric)
        return metric

    def simulate_external_delivery_check(
        self,
        strategy,
        order_id,
        state,
        submitted_at,
        strategy_started_at,
    ):
        worker_started_at = perf_counter()
        queue_delay_ms = (worker_started_at - submitted_at) * 1000
        active_calls = 0
        overloaded = False
        should_fail = False
        latency_ms = self.external_call_ms
        thread_name = current_thread().name

        with state["lock"]:
            state["worker_thread_names"].add(thread_name)
            state["active_calls"] += 1
            active_calls = state["active_calls"]
            state["max_active_calls"] = max(state["max_active_calls"], active_calls)

            if active_calls > self.safe_external_service_capacity:
                state["overload_events"] += 1
                overloaded = True
                latency_ms += self.overload_penalty_ms

            if active_calls > self.severe_overload_threshold:
                should_fail = True

        try:
            sleep(latency_ms / 1000)
            if should_fail:
                raise TimeoutError(
                    f"delivery service timeout: active_calls={active_calls} "
                    f"exceeded severe_threshold={self.severe_overload_threshold}"
                )
            status = "OVERLOADED" if overloaded else "OK"
            return {
                "strategy": strategy,
                "order_id": order_id,
                "status": status,
                "success": True,
                "error": "",
                "thread_name": thread_name,
                "active_calls_at_start": active_calls,
                "queue_delay_ms": queue_delay_ms,
                "latency_ms": self.elapsed_ms(worker_started_at),
                "started_offset_ms": (worker_started_at - strategy_started_at) * 1000,
            }
        except Exception as exc:
            return {
                "strategy": strategy,
                "order_id": order_id,
                "status": "FAILED",
                "success": False,
                "error": str(exc),
                "thread_name": thread_name,
                "active_calls_at_start": active_calls,
                "queue_delay_ms": queue_delay_ms,
                "latency_ms": self.elapsed_ms(worker_started_at),
                "started_offset_ms": (worker_started_at - strategy_started_at) * 1000,
            }
        finally:
            with state["lock"]:
                state["active_calls"] -= 1

    def create_state(self):
        return {
            "lock": Lock(),
            "active_calls": 0,
            "max_active_calls": 0,
            "overload_events": 0,
            "worker_thread_names": set(),
        }

    def build_failed_result(self, strategy, order_id, submitted_at, started_at, exc):
        return {
            "strategy": strategy,
            "order_id": order_id,
            "status": "FAILED",
            "success": False,
            "error": str(exc),
            "thread_name": current_thread().name,
            "active_calls_at_start": 0,
            "queue_delay_ms": (started_at - submitted_at) * 1000,
            "latency_ms": self.elapsed_ms(started_at),
            "started_offset_ms": 0,
        }

    def build_metrics(self, strategy, total_duration_ms, results, state, created_threads):
        successful_results = [result for result in results if result["success"]]
        ok_results = [result for result in results if result["status"] == "OK"]
        overloaded_results = [result for result in results if result["status"] == "OVERLOADED"]
        failed_results = [result for result in results if result["status"] == "FAILED"]
        latencies = [result["latency_ms"] for result in results]
        queue_delays = [result["queue_delay_ms"] for result in results]
        total_duration_seconds = total_duration_ms / 1000
        successful_count = len(successful_results)

        return {
            "strategy": strategy,
            "total_duration_ms": total_duration_ms,
            "successful_count": successful_count,
            "ok_count": len(ok_results),
            "overloaded_count": len(overloaded_results),
            "failed_count": len(failed_results),
            "failure_rate": len(failed_results) / len(results) if results else 0,
            "throughput": successful_count / total_duration_seconds if total_duration_seconds else 0,
            "avg_latency_ms": sum(latencies) / len(latencies) if latencies else 0,
            "max_latency_ms": max(latencies) if latencies else 0,
            "avg_queue_delay_ms": sum(queue_delays) / len(queue_delays) if queue_delays else 0,
            "max_queue_delay_ms": max(queue_delays) if queue_delays else 0,
            "created_threads": created_threads,
            "max_active_calls": state["max_active_calls"],
            "overload_events": state["overload_events"],
            "results": results,
        }

    def print_scenario_header(self):
        self.stdout.write("\n============================================================")
        self.stdout.write("External Delivery Service Capacity Control using Thread Pool")
        self.stdout.write("============================================================")
        self.stdout.write("\nScenario:")
        self.stdout.write(f"- pending_orders: {self.order_count}")
        self.stdout.write(f"- safe_external_service_capacity: {self.safe_external_service_capacity}")
        self.stdout.write(f"- external_call_ms: {self.external_call_ms}")
        self.stdout.write(f"- balanced_pool_size: {self.balanced_pool_size}")
        self.stdout.write(f"- too_high_pool_size: {self.too_high_pool_size}")

    def print_strategy_report(self, metric):
        strategy = metric["strategy"]
        self.stdout.write("\n------------------------------------------------------------")
        self.stdout.write(f"{self.strategy_number(strategy)}. {strategy}")
        self.stdout.write("------------------------------------------------------------")
        self.stdout.write("Meaning:")
        self.stdout.write(self.strategy_meaning(strategy))
        self.stdout.write("\nResult:")
        self.stdout.write(f"- status: {self.strategy_status(metric)}")
        self.stdout.write(f"- submitted_orders: {len(metric['results'])}")
        self.stdout.write(f"- successful_orders: {metric['successful_count']}")
        self.stdout.write(f"- failed_orders: {metric['failed_count']}")
        self.stdout.write(f"- duration_ms: {metric['total_duration_ms']:.2f}")
        self.stdout.write(f"- created_threads: {metric['created_threads']}")
        self.stdout.write(f"- max_active_calls: {metric['max_active_calls']}")
        self.stdout.write(f"- overload_events: {metric['overload_events']}")
        self.stdout.write(f"- max_queue_ms: {metric['max_queue_delay_ms']:.2f}")
        self.stdout.write(f"- max_latency_ms: {metric['max_latency_ms']:.2f}")
        self.print_sample_results(metric["results"])

    def print_sample_results(self, results, limit=5):
        sample_limit = len(results) if self.verbose_orders else limit
        sample = results[:sample_limit]
        self.stdout.write("\nSample results:")
        for result in sample:
            error_suffix = f", error={result['error']}" if result["error"] else ""
            self.stdout.write(
                f"- order={result['order_id']:02d}, status={result['status']}, "
                f"active={result['active_calls_at_start']}, "
                f"queue_ms={result['queue_delay_ms']:.2f}, "
                f"latency_ms={result['latency_ms']:.2f}"
                f"{error_suffix}"
            )

        omitted_count = len(results) - len(sample)
        if omitted_count > 0:
            self.stdout.write(f"... {omitted_count} more orders omitted")

    def strategy_meaning(self, strategy_name):
        meanings = {
            "SEQUENTIAL_TOO_SLOW": (
                "Processes delivery checks one by one. Safe, but underuses available capacity "
                "and becomes slow."
            ),
            "THREAD_PER_CALL_RISKY": (
                "Creates one raw thread per delivery check. Fast-looking, but causes unbounded "
                "thread creation and overload risk."
            ),
            "THREAD_POOL_BALANCED": (
                "Uses a bounded ThreadPoolExecutor tuned to the external service capacity. "
                "This is the recommended solution."
            ),
            "THREAD_POOL_TOO_HIGH": (
                "Uses a ThreadPoolExecutor with too many workers. Faster-looking, but can "
                "overload the external service."
            ),
        }
        return meanings[strategy_name]

    def strategy_status(self, metric):
        statuses = {
            "SEQUENTIAL_TOO_SLOW": "SAFE_BUT_SLOW",
            "THREAD_PER_CALL_RISKY": "FAST_BUT_RISKY",
            "THREAD_POOL_BALANCED": "BALANCED_RECOMMENDED",
            "THREAD_POOL_TOO_HIGH": "TOO_HIGH_RISKY",
        }
        return statuses[metric["strategy"]]

    def strategy_number(self, strategy_name):
        numbers = {
            "SEQUENTIAL_TOO_SLOW": 1,
            "THREAD_PER_CALL_RISKY": 2,
            "THREAD_POOL_BALANCED": 3,
            "THREAD_POOL_TOO_HIGH": 4,
        }
        return numbers[strategy_name]

    def print_final_comparison(self, metrics):
        self.stdout.write("\n============================================================")
        self.stdout.write("FINAL COMPARISON")
        self.stdout.write("============================================================")

        self.stdout.write("Safety:")
        for metric in metrics:
            self.stdout.write(
                f"- {metric['strategy']}: overload_events={metric['overload_events']}, "
                f"failed={metric['failed_count']}"
            )

        self.stdout.write("\nResource Usage:")
        for metric in metrics:
            self.stdout.write(
                f"- {metric['strategy']}: created_threads={metric['created_threads']}, "
                f"max_active_calls={metric['max_active_calls']}"
            )

        self.stdout.write("\nQueue Delay:")
        for metric in metrics:
            self.stdout.write(
                f"- {metric['strategy']}: avg_queue_ms={metric['avg_queue_delay_ms']:.2f}, "
                f"max_queue_ms={metric['max_queue_delay_ms']:.2f}"
            )

        self.stdout.write("\nPerformance:")
        for metric in metrics:
            self.stdout.write(
                f"- {metric['strategy']}: duration_ms={metric['total_duration_ms']:.2f}, "
                f"throughput={metric['throughput']:.2f} orders/sec"
            )


    def elapsed_ms(self, started_at):
        return (perf_counter() - started_at) * 1000
