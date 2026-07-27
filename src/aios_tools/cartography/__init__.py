"""Renderer-neutral Cartography primitives for AIOS."""

from .canonical import canonical_json, canonical_payload, snapshot_digest
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
from .notion_read_adapter import NotionPageChainAdapter, NotionReadClient, NotionReadResult
from .pipeline import build_notion_snapshot, compile_source_backed_view
from .views import (
    NOTION_AUTHORITY_CHAIN_VIEW,
    SYSTEM_OVERVIEW_VIEW,
    WORKFLOW_CONTROL_PLANE_VIEW,
    compile_view,
)

__all__ = [
    "ADAPTER_VERSIONS",
    "AIOS_EDGE_NAMESPACE",
    "AIOS_NODE_NAMESPACE",
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
    "build_notion_snapshot",
    "canonical_json",
    "canonical_payload",
    "compile_source_backed_view",
    "compile_view",
    "edge_id_for",
    "node_id_for",
    "snapshot_digest",
    "validate_graph_ir",
]
