"""Compatibility surface for the disposable ETB-01…ETB-10 harness.

The evaluator is production code as of the bounded system.health activation;
the matrix runner and this import path remain available for replay evidence.
"""

from ..execution_trust import (  # noqa: F401
    CONTRACT_ID,
    EVALUATOR_VERSION,
    MATRIX_PATH,
    SCHEMA_ID,
    SCHEMA_PATH,
    admit_and_invoke_read_only,
    build_runtime_system_health_binding,
    build_system_health_binding,
    evaluate_trust_binding,
    load_synthetic_matrix,
    run_synthetic_matrix,
)

__all__ = [
    "CONTRACT_ID",
    "EVALUATOR_VERSION",
    "MATRIX_PATH",
    "SCHEMA_ID",
    "SCHEMA_PATH",
    "admit_and_invoke_read_only",
    "build_runtime_system_health_binding",
    "build_system_health_binding",
    "evaluate_trust_binding",
    "load_synthetic_matrix",
    "run_synthetic_matrix",
]
