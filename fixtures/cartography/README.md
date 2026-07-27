# Cartography deterministic fixture package

The executable fixture builders live in `src/aios_tools/cartography/fixtures.py` and are verified by `tests/test_cartography_slice2.py`.

Registered fixture adapter families:

1. `notion.page_tree`
2. `drive.file_tree`
3. `registry.project_scope`
4. `registry.capability`

These are frozen test surfaces, not live connectors. Missing targets remain unresolved references and never create phantom nodes.
