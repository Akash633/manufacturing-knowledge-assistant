from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.retrieval import RetrievalQuery, RetrievalResponse
from app.retrieval.hybrid import hybrid_retriever

router = APIRouter(prefix="/retrieval", tags=["Retrieval"])

@router.post("/search", response_model=RetrievalResponse)
def execute_retrieval(
    query_param: RetrievalQuery,
    db: Session = Depends(get_db),
):
    """
    Execute BM25, Vector, or Hybrid retrieval with Reciprocal Rank Fusion.
    Returns source snippets, document IDs, page numbers, and rank details.
    """
    return hybrid_retriever.search(db, query_param)
