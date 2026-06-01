from unittest.mock import MagicMock, patch, ANY
from codegraph.core.retrieval.pipeline import run_core_retrieval, RawRetrievalResult
from codegraph.core.retrieval.seed_selection import PersonalizationVector

@patch("codegraph.core.retrieval.pipeline.extract_seeds")
@patch("codegraph.core.retrieval.pipeline.ensure_graph_ready")
@patch("codegraph.core.retrieval.pipeline.run_ppr_from_node_ids")
@patch("codegraph.core.retrieval.pipeline.prepare_bm25_index")
def test_run_core_retrieval_returns_expected_structure(
    mock_bm25, mock_ppr, mock_ready, mock_seeds
):
    # Setup mocks
    driver = MagicMock()
    gds = MagicMock()
    task_description = "test task"
    
    mock_bm25.return_value = (None, None)
    
    seeds = PersonalizationVector(seeds={1: 1.0}, metadata={1: {"qname": "test", "source": "entity_match"}})
    mock_seeds.return_value = seeds
    
    ppr_results = [MagicMock(score=1.0, qualified_name="test")]
    mock_ppr.return_value = ppr_results

    result = run_core_retrieval(
        driver=driver,
        gds=gds,
        task_description=task_description
    )
    
    assert isinstance(result, RawRetrievalResult)
    assert result.seeds == seeds
    assert result.ppr_results == ppr_results
    
    # Verify calls
    mock_seeds.assert_called_once()
    mock_ready.assert_called_once()
    mock_ppr.assert_called_once_with(gds, driver, seeds.seeds, ANY)
