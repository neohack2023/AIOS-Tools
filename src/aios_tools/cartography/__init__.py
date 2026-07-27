"""Cartography adapters, Graph IR, identity, drift, views, and renderers for AIOS."""

from .canonical import canonical_json, canonical_payload, snapshot_digest
from .drift import compare_cross_source_drift
from .drive_read_adapter import DriveAncestorChainAdapter, DriveReadClient, DriveReadResult
from .fixtures import (
    ADAPTER_VERSIONS,
    adapt_capability_registry,
    adapt_drive_tree,
    adapt_notion_page_tree,
    adapt_scope_registry,
)
from .graph_ir import (
    AIOS_EDGE_NAMESPACE,
    AIOS_NODE_NAMESPACE,
    GraphIRError,
    edge_id_for,
    node_id_for,
    validate_graph_ir,
)
from .identity import (
    CROSS_SOURCE_IDENTITY_NAMESPACE,
    ExactIdentityBinding,
    cross_source_entity_id,
    resolve_exact_identities,
)
from .notion_read_adapter import NotionPageChainAdapter, NotionReadClient, NotionReadResult
from .pipeline import build_drive_snapshot, build_notion_snapshot, compile_source_backed_view
from .png import render_png
from .render import compile_render_scene, render_svg
from .views import (
    NOTION_AUTHORITY_CHAIN_VIEW,
    SYSTEM_OVERVIEW_VIEW,
    WORKFLOW_CONTROL_PLANE_VIEW,
    compile_view,
)
from .webgpu import render_webgpu_html

__all__ = [
    "ADAPTER_VERSIONS",
    "AIOS_EDGE_NAMESPACE",
    "AIOS_NODE_NAMESPACE",
    "CROSS_SOURCE_IDENTITY_NAMESPACE",
    "DriveAncestorChainAdapter",
    "DriveReadClient",
    "DriveReadResult",
    "ExactIdentityBinding",
    "GraphIRError",
    "NOTION_AUTHORITY_CHAIN_VIEW",
    "NotionPageChainAdapter",
    "NotionReadClient",
    "NotionReadResult",
    "SYSTEM_OVERVIEW_VIEW",
    "WORKFLOW_CONTROL_PLANE_VIEW",
    "adapt_capability_registry",
    "adapt_drive_tree",
    "adapt_notion_page_tree",
    "adapt_scope_registry",
    "build_drive_snapshot",
    "build_notion_snapshot",
    "canonical_json",
    "canonical_payload",
    "compare_cross_source_drift",
    "compile_render_scene",
    "compile_source_backed_view",
    "compile_view",
    "cross_source_entity_id",
    "edge_id_for",
    "node_id_for",
    "render_png",
    "render_svg",
    "render_webgpu_html",
    "resolve_exact_identities",
    "snapshot_digest",
    "validate_graph_ir",
]
