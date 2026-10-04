"""The small, explicit manifest of operationIds the generator covers.

The worker-side (WorkerBearer) operations of the OpenAPI document: heartbeat,
claim, evidence upload, events and reconcile. The SystemBearer operations
(createBatch, controlJob, getJob, getBatch, getWorkerStatus) are ARGUS-internal
and deliberately left out. Extend this list (and rerun
scripts/gen_api_client.ps1) when another operation is needed -- nothing else
in the generator needs to change for that to work.
"""

from __future__ import annotations

from pathlib import Path

MANIFEST: tuple[str, ...] = (
    "heartbeat",
    "claimJobs",
    "uploadEvidence",
    "postEvents",
    "reconcileJob",
)
SPEC_RELATIVE_PATH = Path("docs") / "ARGUS20_COLLECTOR_OPENAPI.json"
