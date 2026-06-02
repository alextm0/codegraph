"""Unit tests for GraphBuilder class (no Neo4j required)."""

from unittest.mock import MagicMock, patch

from codegraph.core.graph.graph_builder import GraphBuilder, build_graph
from codegraph.core.parser.models import FileEntities, FunctionEntity


def _minimal_entities() -> list[FileEntities]:
    fe = FileEntities(file_path="main.py")
    fe.functions.append(
        FunctionEntity(
            name="main",
            file_path="main.py",
            line_number=1,
            end_line=3,
            signature="def main()",
        )
    )
    return [fe]


def test_graph_builder_initializes_lookup_and_paths() -> None:
    entities = _minimal_entities()
    driver = MagicMock()

    builder = GraphBuilder(driver, entities)

    assert builder.all_entities is entities
    assert "main.py" in builder.all_file_paths
    assert "main" in builder.lookup
    assert builder.counts["File"] == 0


@patch("codegraph.core.graph.graph_builder.ensure_constraints")
def test_graph_builder_build_empty_entities(mock_constraints: MagicMock) -> None:
    driver = MagicMock()
    session = MagicMock()
    driver.session.return_value.__enter__.return_value = session
    session.execute_write.return_value = 0

    builder = GraphBuilder(driver, [])
    counts = builder.build()

    mock_constraints.assert_called_once_with(driver)
    assert counts["File"] == 0
    assert counts["Function"] == 0
    assert counts["CONTAINS"] == 0


@patch("codegraph.core.graph.graph_builder.ensure_constraints")
def test_graph_builder_progress_callback(mock_constraints: MagicMock) -> None:
    driver = MagicMock()
    session = MagicMock()
    driver.session.return_value.__enter__.return_value = session
    session.execute_write.return_value = 1

    stages: list[tuple[str, int]] = []

    def on_progress(stage: str, count: int) -> None:
        stages.append((stage, count))

    GraphBuilder(driver, _minimal_entities(), progress_callback=on_progress).build()

    assert ("File nodes", 1) in stages
    assert ("CALLS edges", 1) in stages
    assert len(stages) == 8


@patch("codegraph.core.graph.graph_builder.ensure_constraints")
def test_graph_builder_write_nodes_order(mock_constraints: MagicMock) -> None:
    driver = MagicMock()
    session = MagicMock()
    driver.session.return_value.__enter__.return_value = session
    session.execute_write.return_value = 2

    builder = GraphBuilder(driver, _minimal_entities())
    builder._write_nodes(session)

    calls = [call.args[0].__name__ for call in session.execute_write.call_args_list]
    assert calls == [
        "_create_file_nodes",
        "_create_function_nodes",
        "_create_class_nodes",
        "_create_method_nodes",
    ]


@patch("codegraph.core.graph.graph_builder.GraphBuilder.build")
def test_build_graph_delegates_to_graph_builder(mock_build: MagicMock) -> None:
    driver = MagicMock()
    mock_build.return_value = {"File": 3}

    counts = build_graph(driver, _minimal_entities())

    mock_build.assert_called_once()
    assert counts == {"File": 3}


@patch("codegraph.core.graph.graph_builder.ensure_constraints")
def test_build_graph_wrapper_returns_same_as_class(mock_constraints: MagicMock) -> None:
    driver = MagicMock()
    session = MagicMock()
    driver.session.return_value.__enter__.return_value = session
    session.execute_write.return_value = 0

    via_wrapper = build_graph(driver, [])
    via_class = GraphBuilder(driver, []).build()

    assert via_wrapper == via_class
