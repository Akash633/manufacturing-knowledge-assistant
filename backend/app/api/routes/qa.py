from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.query import QuestionRequest, GroundedAnswerResponse
from app.services.qa_service import qa_service

router = APIRouter(prefix="/qa", tags=["Shop Floor Q&A"])

@router.post("/ask", response_model=GroundedAnswerResponse)
def ask_assistant(
    request: QuestionRequest,
    db: Session = Depends(get_db),
):
    """
    Answers shop-floor questions using approved documentation, retrieves supporting evidence,
    validates citations, flags safety-critical instructions, and abstains when evidence is missing or conflicting.
    """
    return qa_service.answer_question(db, request, actor="operator")
