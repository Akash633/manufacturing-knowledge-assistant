from fastapi import APIRouter
from .documents import router as documents_router
from .retrieval import router as retrieval_router
from .qa import router as qa_router
from .governance import router as governance_router
from .review import router as review_router
from .instruction import router as instruction_router
from .evaluation import router as evaluation_router
from .auth import router as auth_router

api_router = APIRouter(prefix="/api")

api_router.include_router(documents_router)
api_router.include_router(retrieval_router)
api_router.include_router(qa_router)
api_router.include_router(governance_router)
api_router.include_router(review_router)
api_router.include_router(instruction_router)
api_router.include_router(evaluation_router)
api_router.include_router(auth_router)
