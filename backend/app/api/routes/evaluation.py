from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.evaluation.metrics import evaluation_runner
from app.evaluation.benchmarks import GROUND_TRUTH_DATASET

router = APIRouter(prefix="/evaluation", tags=["Evaluation"])

@router.post("/run")
def run_evaluation_benchmark(db: Session = Depends(get_db)):
    """
    Executes actual test runs of the ground-truth benchmark suite,
    comparing BM25 baseline against Hybrid RRF retrieval.
    Computes Recall@K, citation validity, abstention accuracy,
    safety escalation compliance, conflict detection, and latencies.
    """
    return evaluation_runner.run_benchmark(db)

@router.get("/dataset")
def get_benchmark_dataset():
    """
    Returns the benchmark test cases and expected ground-truth answers.
    """
    return {
        "dataset_name": "DEMO-CNC-01 Manufacturing Ground Truth Benchmark",
        "description": "Validation dataset covering standard operations, revision conflicts, safety risks, and abstention scenarios.",
        "cases": GROUND_TRUTH_DATASET,
    }
