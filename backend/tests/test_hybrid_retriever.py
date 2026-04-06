"""Tests for BM25 retriever keyword matching behavior."""

import pytest
from llama_index.retrievers.bm25 import BM25Retriever
from llama_index.core.schema import TextNode


@pytest.fixture
def resume_nodes():
    return [
        TextNode(
            text="Developed Python ETL pipelines using pandas and SQLAlchemy at Jet Commerce.",
            metadata={"section": "work_experience", "company": "Jet Commerce"},
        ),
        TextNode(
            text="Built predictive models in Python with scikit-learn for demand forecasting.",
            metadata={"section": "work_experience", "company": "Brainzyme"},
        ),
        TextNode(
            text="Led a team of 5 data engineers and managed stakeholder communication.",
            metadata={"section": "work_experience", "company": "Jet Commerce"},
        ),
        TextNode(
            text="Worked with n8n workflow automation and integrated external APIs.",
            metadata={"section": "work_experience", "company": "Brainzyme"},
        ),
    ]


def test_bm25_retriever_returns_keyword_matches(resume_nodes):
    """BM25 retriever should return multiple chunks containing the queried keyword."""
    retriever = BM25Retriever.from_defaults(nodes=resume_nodes, similarity_top_k=4)
    results = retriever.retrieve("Python experience")
    result_texts = [n.text for n in results]
    assert any("Python ETL" in t for t in result_texts)
    assert any("Python with scikit-learn" in t for t in result_texts)


def test_bm25_retriever_keyword_over_semantic(resume_nodes):
    """BM25 retriever should rank keyword match above unrelated chunks."""
    retriever = BM25Retriever.from_defaults(nodes=resume_nodes, similarity_top_k=2)
    results = retriever.retrieve("n8n automation")
    result_texts = [n.text for n in results]
    assert any("n8n" in t for t in result_texts)
