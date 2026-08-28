from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import time
import tracemalloc
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .task_execution_runtime import (
    _append_event,
    _connect,
    _insert_run,
    claim_task_run,
    recoverable_task_runs,
    runtime_queue_snapshot,
    update_task_run,
)


NON_AMAZON_PLATFORMS = ("tiktok_shop", "shein", "shopee", "shopify")
DEFAULT_RECORD_COUNT = 100_000
DEFAULT_TENANT_COUNT = 100
DEFAULT_SELECTION_LIMIT = 100
DEFAULT_BATCH_SIZE = 5_000


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _synthetic_run(index: int, tenant_count: int, created_at: str) -> dict[str, Any]:
    tenant_index = index % tenant_count
    tenant_id = f"synthetic-tenant-{tenant_index:04d}"
    store_binding_id = f"synthetic-store-{index:08d}"
    platform = NON_AMAZON_PLATFORMS[index % len(NON_AMAZON_PLATFORMS)]
    run_id = f"run-synth-{index:08d}"
    store_scope_key = (
        f"tenant:{tenant_id}|project:synthetic-g08|platform:{platform}|"
        f"country:synthetic|mode:local_store|ownership:synthetic|store:{store_binding_id}"
    )
    return {
        "id": run_id,
        "task_id": "synthetic-non-amazon-capacity",
        "task_name": "G08 isolated synthetic capacity probe",
        "platform": platform,
        "country": "synthetic",
        "store_id": "",
        "tenant_id": tenant_id,
        "workspace_id": "synthetic-workspace",
        "project_id": "synthetic-g08",
        "store_binding_id": store_binding_id,
        "execution_identity_id": "synthetic-read-only",
        "execution_domain": "runtime_probe",
        "store_model": "local_store",
        "ownership": "synthetic",
        "route_key": f"{platform}:synthetic:local_store:synthetic",
        "product_id": "",
        "instruction": f"synthetic read-only capacity event {index}",
        "mode": "tool",
        "action": "synthetic_capacity_probe",
        "surface": "",
        "label": "isolated synthetic capacity event",
        "reason": "",
        "status": "queued",
        "actor": "synthetic-capacity-probe",
        "created_at": created_at,
        "updated_at": created_at,
        "result_message": "",
        "error": "",
        "evidence_paths": [],
        "execution_payload": {
            "tenant_id": tenant_id,
            "project_id": "synthetic-g08",
            "platform": platform,
            "country": "synthetic",
            "store_model": "local_store",
            "ownership": "synthetic",
            "store_binding_id": store_binding_id,
            "execution_identity_id": "synthetic-read-only",
            "execution_domain": "runtime_probe",
        },
        "store_scope_key": store_scope_key,
        "active_fingerprint": hashlib.sha256(run_id.encode("utf-8")).hexdigest(),
        "idempotency_key": f"synthetic-g08-{index:08d}",
        "fencing_token": 0,
        "attempt_count": 0,
        "max_attempts": 3,
        "recovery_count": 0,
        "next_retry_at": "",
        "dead_lettered_at": "",
        "last_error_code": "",
        "retry_backoff_seconds": 0,
        "queue_class": "research_read",
        "queue_priority": 10,
        "lease_owner": "",
        "lease_expires_at": "",
        "heartbeat_at": "",
        "synthetic_probe": True,
    }


def _restart_snapshot(root: Path) -> dict[str, Any]:
    source_root = Path(__file__).resolve().parents[1]
    code = (
        "import json,sys; from pathlib import Path; "
        "from ai_ecommerce_director.task_execution_runtime import runtime_queue_snapshot; "
        "s=runtime_queue_snapshot(Path(sys.argv[1])); "
        "print(json.dumps({'ready_count':s['ready_count'],"
        "'running_count':s['running_count'],'dead_letter_count':s['dead_letter_count']}))"
    )
    completed = subprocess.run(
        [sys.executable, "-c", code, str(root)],
        cwd=str(source_root),
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return dict(json.loads(completed.stdout.strip()))


def run_synthetic_capacity_probe(
    root: Path,
    *,
    record_count: int = DEFAULT_RECORD_COUNT,
    tenant_count: int = DEFAULT_TENANT_COUNT,
    selection_limit: int = DEFAULT_SELECTION_LIMIT,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> dict[str, Any]:
    """Exercise the real SQLite scheduler in an isolated root.

    This verifies a synthetic queue depth. It deliberately does not validate
    production store integrations, distributed workers, or a 100k-store SLA.
    """

    root = Path(root).resolve()
    record_count = max(100, min(int(record_count), 1_000_000))
    tenant_count = max(1, min(int(tenant_count), record_count, 10_000))
    selection_limit = max(1, min(int(selection_limit), 100, record_count))
    batch_size = max(100, min(int(batch_size), 50_000, record_count))
    database_path = root / "data" / "task_execution_runtime.sqlite3"
    if database_path.exists() and database_path.stat().st_size:
        raise ValueError("容量探针只能写入空的隔离根目录，已拒绝覆盖现有运行账本。")

    root.mkdir(parents=True, exist_ok=True)
    created_at = _iso(datetime(2026, 7, 19, tzinfo=timezone.utc))
    insertion_started = time.perf_counter()
    connection = _connect(root)
    try:
        connection.execute("BEGIN IMMEDIATE")
        for index in range(record_count):
            run = _synthetic_run(index, tenant_count, created_at)
            _insert_run(connection, run)
            _append_event(
                connection,
                run,
                "created",
                {"mode": "tool", "action": "synthetic_capacity_probe"},
            )
            if (index + 1) % batch_size == 0 and index + 1 < record_count:
                connection.commit()
                connection.execute("BEGIN IMMEDIATE")
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    insertion_seconds = time.perf_counter() - insertion_started

    snapshot_started = time.perf_counter()
    initial_snapshot = runtime_queue_snapshot(root)
    snapshot_seconds = time.perf_counter() - snapshot_started

    tracemalloc.start()
    selection_started = time.perf_counter()
    selected = recoverable_task_runs(root, limit=selection_limit)
    selection_seconds = time.perf_counter() - selection_started
    _, selection_peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    selected_tenants = {str(item.get("tenant_id") or "") for item in selected}
    selected_stores = {str(item.get("store_scope_key") or "") for item in selected}
    expected_tenants = min(tenant_count, selection_limit)
    first_id = str(selected[0]["id"])
    started_at = datetime(2026, 7, 19, 1, 0, tzinfo=timezone.utc)
    first_claim = claim_task_run(root, first_id, "synthetic-worker-a", now=started_at)
    second_claim = claim_task_run(
        root,
        first_id,
        "synthetic-worker-b",
        recovered=True,
        now=started_at + timedelta(seconds=60),
    )
    stale_worker_blocked = False
    try:
        update_task_run(
            root,
            first_id,
            {"status": "completed", "result_message": "stale worker result"},
            worker_id="synthetic-worker-a",
            fencing_token=int(first_claim["fencing_token"]),
        )
    except RuntimeError:
        stale_worker_blocked = True
    recovered_completion = update_task_run(
        root,
        first_id,
        {"status": "completed", "result_message": "synthetic recovery verified"},
        worker_id="synthetic-worker-b",
        fencing_token=int(second_claim["fencing_token"]),
    )

    restart_snapshot = _restart_snapshot(root)
    final_snapshot = runtime_queue_snapshot(root)
    verification = _connect(root)
    try:
        integrity = str(verification.execute("PRAGMA integrity_check").fetchone()[0])
        task_count = int(verification.execute("SELECT COUNT(*) FROM task_runs").fetchone()[0])
        event_count = int(verification.execute("SELECT COUNT(*) FROM task_run_events").fetchone()[0])
        verification.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        verification.close()

    checks = {
        "task_rows_match": task_count == record_count,
        "created_events_present": event_count >= record_count,
        "initial_ready_depth_match": int(initial_snapshot["ready_count"]) == record_count,
        "selection_is_bounded": len(selected) == selection_limit,
        "unique_store_selection": len(selected_stores) == selection_limit,
        "tenant_round_robin_visible": len(selected_tenants) == expected_tenants,
        "expired_lease_recovered": (
            second_claim is not None
            and int(second_claim.get("fencing_token") or 0)
            > int(first_claim.get("fencing_token") or 0)
            and int(second_claim.get("recovery_count") or 0) == 1
        ),
        "stale_worker_blocked": stale_worker_blocked,
        "recovered_worker_completed": recovered_completion.get("status") == "completed",
        "process_restart_restored_depth": int(restart_snapshot["ready_count"]) == record_count - 1,
        "final_ready_depth_match": int(final_snapshot["ready_count"]) == record_count - 1,
        "sqlite_integrity_ok": integrity.lower() == "ok",
        "non_amazon_only": all(
            str(item.get("platform") or "") in NON_AMAZON_PLATFORMS for item in selected
        ),
    }
    ok = all(checks.values())
    result = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "probe_kind": "isolated_non_amazon_synthetic_task_runtime_capacity",
        "ok": ok,
        "record_count": record_count,
        "synthetic_store_scope_count": record_count,
        "tenant_count": tenant_count,
        "platforms": list(NON_AMAZON_PLATFORMS),
        "queue_class": "research_read",
        "selection_limit": selection_limit,
        "selected_count": len(selected),
        "selected_unique_tenant_count": len(selected_tenants),
        "selected_unique_store_count": len(selected_stores),
        "task_row_count": task_count,
        "event_row_count": event_count,
        "database_bytes": database_path.stat().st_size,
        "insertion_seconds": round(insertion_seconds, 6),
        "insertion_rows_per_second": round(record_count / max(insertion_seconds, 0.000001), 2),
        "snapshot_seconds": round(snapshot_seconds, 6),
        "selection_seconds": round(selection_seconds, 6),
        "selection_peak_bytes": selection_peak_bytes,
        "initial_ready_count": int(initial_snapshot["ready_count"]),
        "final_ready_count": int(final_snapshot["ready_count"]),
        "restart_ready_count": int(restart_snapshot["ready_count"]),
        "first_fencing_token": int(first_claim["fencing_token"]),
        "recovered_fencing_token": int(second_claim["fencing_token"]),
        "recovery_count": int(second_claim["recovery_count"]),
        "integrity_check": integrity,
        "checks": checks,
        "synthetic_100k_queue_depth_validated": ok and record_count >= 100_000,
        "production_capacity_validated": False,
        "production_100k_store_sla_validated": False,
        "distributed_multi_host_validated": False,
        "long_soak_validated": False,
        "external_action_count": 0,
        "real_store_connection_count": 0,
        "boundary": "synthetic_queue_depth_only_not_production_100k_store_capacity",
        "database_persisted": True,
    }
    return result


def run_bounded_local_soak_probe(
    root: Path,
    *,
    record_count: int = 5_000,
    tenant_count: int = DEFAULT_TENANT_COUNT,
    duration_seconds: float = 30.0,
    cycle_limit: int = 1_000,
    cycle_interval_seconds: float = 0.02,
    restart_every_cycles: int = 100,
) -> dict[str, Any]:
    """Exercise bounded worker churn and independent-process reads locally.

    This is intentionally a short, isolated soak. It can strengthen evidence for
    local SQLite stability, but it must never be reported as a production SLA or
    as long-duration / distributed / real-store validation.
    """

    root = Path(root).resolve()
    record_count = max(100, min(int(record_count), 100_000))
    tenant_count = max(1, min(int(tenant_count), record_count, 10_000))
    duration_seconds = max(0.0, min(float(duration_seconds), 3_600.0))
    cycle_limit = max(1, min(int(cycle_limit), record_count - 1))
    cycle_interval_seconds = max(0.0, min(float(cycle_interval_seconds), 5.0))
    restart_every_cycles = max(1, min(int(restart_every_cycles), cycle_limit))

    baseline = run_synthetic_capacity_probe(
        root,
        record_count=record_count,
        tenant_count=tenant_count,
        selection_limit=min(DEFAULT_SELECTION_LIMIT, record_count),
        batch_size=min(DEFAULT_BATCH_SIZE, record_count),
    )
    baseline_ready = int(baseline["final_ready_count"])
    completed_cycles = 0
    restart_samples: list[dict[str, int]] = []
    consistency_failures: list[dict[str, int]] = []
    started = time.perf_counter()
    deadline = started + duration_seconds

    tracemalloc.start()
    while completed_cycles < cycle_limit:
        if duration_seconds > 0 and time.perf_counter() >= deadline:
            break
        candidates = recoverable_task_runs(root, limit=1)
        if not candidates:
            break
        run_id = str(candidates[0]["id"])
        worker_id = f"synthetic-soak-worker-{completed_cycles % 4}"
        claimed = claim_task_run(root, run_id, worker_id)
        if not claimed:
            consistency_failures.append({"cycle": completed_cycles, "ready_count": -1})
            break
        update_task_run(
            root,
            run_id,
            {"status": "completed", "result_message": "bounded local soak cycle completed"},
            worker_id=worker_id,
            fencing_token=int(claimed["fencing_token"]),
        )
        completed_cycles += 1
        expected_ready = baseline_ready - completed_cycles
        if completed_cycles % restart_every_cycles == 0:
            restarted = _restart_snapshot(root)
            observed_ready = int(restarted["ready_count"])
            restart_samples.append({"cycle": completed_cycles, "ready_count": observed_ready})
            if observed_ready != expected_ready:
                consistency_failures.append({"cycle": completed_cycles, "ready_count": observed_ready})
        if cycle_interval_seconds:
            time.sleep(cycle_interval_seconds)

    observed_seconds = time.perf_counter() - started
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    final_snapshot = runtime_queue_snapshot(root)
    verification = _connect(root)
    try:
        integrity = str(verification.execute("PRAGMA integrity_check").fetchone()[0])
        task_count = int(verification.execute("SELECT COUNT(*) FROM task_runs").fetchone()[0])
        event_count = int(verification.execute("SELECT COUNT(*) FROM task_run_events").fetchone()[0])
    finally:
        verification.close()

    expected_final_ready = baseline_ready - completed_cycles
    checks = {
        "baseline_capacity_probe_ok": bool(baseline.get("ok")),
        "completed_at_least_one_cycle": completed_cycles > 0,
        "completed_within_cycle_limit": completed_cycles <= cycle_limit,
        "final_ready_depth_match": int(final_snapshot["ready_count"]) == expected_final_ready,
        "restart_samples_consistent": not consistency_failures,
        "no_dead_letters": int(final_snapshot["dead_letter_count"]) == 0,
        "task_rows_preserved": task_count == record_count,
        "events_advanced": event_count >= int(baseline["event_row_count"]) + (completed_cycles * 2),
        "sqlite_integrity_ok": integrity.lower() == "ok",
    }
    ok = all(checks.values())
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "probe_kind": "isolated_non_amazon_bounded_local_worker_soak",
        "ok": ok,
        "record_count": record_count,
        "tenant_count": tenant_count,
        "platforms": list(NON_AMAZON_PLATFORMS),
        "duration_seconds_requested": duration_seconds,
        "duration_seconds_observed": round(observed_seconds, 6),
        "cycle_limit": cycle_limit,
        "completed_cycles": completed_cycles,
        "cycles_per_second": round(completed_cycles / max(observed_seconds, 0.000001), 2),
        "restart_every_cycles": restart_every_cycles,
        "restart_sample_count": len(restart_samples),
        "restart_samples": restart_samples,
        "consistency_failures": consistency_failures,
        "selection_peak_bytes": peak_bytes,
        "baseline_ready_count": baseline_ready,
        "expected_final_ready_count": expected_final_ready,
        "final_ready_count": int(final_snapshot["ready_count"]),
        "task_row_count": task_count,
        "event_row_count": event_count,
        "integrity_check": integrity,
        "checks": checks,
        "bounded_local_soak_validated": ok,
        "long_soak_validated": False,
        "production_capacity_validated": False,
        "production_100k_store_sla_validated": False,
        "distributed_multi_host_validated": False,
        "external_action_count": 0,
        "real_store_connection_count": 0,
        "boundary": "bounded_local_sqlite_worker_churn_not_long_soak_or_production_sla",
        "database_persisted": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the isolated T-one G08 capacity probe.")
    parser.add_argument("--records", type=int, default=DEFAULT_RECORD_COUNT)
    parser.add_argument("--tenants", type=int, default=DEFAULT_TENANT_COUNT)
    parser.add_argument("--selection-limit", type=int, default=DEFAULT_SELECTION_LIMIT)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--soak-seconds", type=float, default=0.0)
    parser.add_argument("--soak-cycle-limit", type=int, default=1_000)
    parser.add_argument("--restart-every-cycles", type=int, default=100)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="t-one-g08-capacity-") as temp_dir:
        if args.soak_seconds > 0:
            result = run_bounded_local_soak_probe(
                Path(temp_dir),
                record_count=args.records,
                tenant_count=args.tenants,
                duration_seconds=args.soak_seconds,
                cycle_limit=args.soak_cycle_limit,
                restart_every_cycles=args.restart_every_cycles,
            )
        else:
            result = run_synthetic_capacity_probe(
                Path(temp_dir),
                record_count=args.records,
                tenant_count=args.tenants,
                selection_limit=args.selection_limit,
                batch_size=args.batch_size,
            )
        result["database_persisted"] = False
        if args.output:
            output = args.output.resolve()
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
