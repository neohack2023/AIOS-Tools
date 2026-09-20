"""Portable tool-package clean-room evaluation support."""

from .context import PackageContextProjection, compile_package_context
from .product_surface import (
    advance_product_surface_receipt,
    initialize_product_surface_receipt,
    validate_product_surface_receipt,
)
from .provider import (
    build_responses_payload,
    execute_openai_pair,
    extract_output_text,
)
from .runtime import (
    PortablePackageEvalCapsule,
    PortablePackageEvalError,
    build_eval_capsule,
    compare_grade_results,
    grade_output_text,
    load_fixture,
)

__all__ = [
    "PackageContextProjection",
    "PortablePackageEvalCapsule",
    "PortablePackageEvalError",
    "advance_product_surface_receipt",
    "build_eval_capsule",
    "build_responses_payload",
    "compare_grade_results",
    "compile_package_context",
    "execute_openai_pair",
    "extract_output_text",
    "grade_output_text",
    "initialize_product_surface_receipt",
    "load_fixture",
    "validate_product_surface_receipt",
]
