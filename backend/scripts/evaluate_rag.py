import os
import sys
import json
import time
from pathlib import Path
from typing import Dict, Any, List

# Ensure backend directory is in python path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.database import SessionLocal, init_db
from app.models.user import User
from app.models.repository import Repository
from app.services.repository.repo_service import RepositoryService
from app.services.ingestion.ingestion_pipeline import IngestionPipeline
from app.services.retrieval.retriever import HybridRetriever
from app.services.rag.rag_service import RAGService


def run_evaluation(mock_mode: bool = False, provider: str = None):
    print("=" * 70)
    print(" REPOSAGE RAG BENCHMARK & EVALUATION SUITE")
    print("=" * 70)

    if mock_mode:
        os.environ["LLM_PROVIDER"] = "mock"
        from app.core.config import settings
        settings.LLM_PROVIDER = "mock"
    elif provider:
        os.environ["LLM_PROVIDER"] = provider
        from app.core.config import settings
        settings.LLM_PROVIDER = provider

    init_db()
    db = SessionLocal()

    # Create evaluation benchmark repo indexing backend source code
    eval_user = db.query(User).filter(User.email == "eval@reposage.dev").first()
    if not eval_user:
        eval_user = User(email="eval@reposage.dev", password_hash="dummyhash", is_active=True)
        db.add(eval_user)
        db.commit()
        db.refresh(eval_user)

    eval_repo = db.query(Repository).filter(Repository.name == "RepoSage-Self-Benchmark").first()
    if not eval_repo:
        eval_repo = Repository(
            user_id=eval_user.id,
            name="RepoSage-Self-Benchmark",
            source_type="local",
            default_branch="main",
            status="pending",
            local_path=str(backend_dir)
        )
        db.add(eval_repo)
        db.commit()
        db.refresh(eval_repo)

    print(f"Indexing benchmark codebase from {backend_dir}...")
    pipeline = IngestionPipeline(db, eval_repo)
    total_files, total_chunks = pipeline.run()
    print(f"Index complete: {total_files} files, {total_chunks} code chunks.")

    # Load dataset
    dataset_path = Path(__file__).resolve().parent.parent.parent / "evaluation" / "datasets" / "eval_questions.json"
    with open(dataset_path, "r", encoding="utf-8") as f:
        questions = json.load(f)

    retriever = HybridRetriever(db, eval_repo.id)
    rag_service = RAGService(db, eval_repo.id)

    results: List[Dict[str, Any]] = []
    reciprocal_ranks = []
    recall_at_3 = []
    retrieval_latencies = []
    citation_correct_rates = []

    print("\nRunning Evaluation Questions:")
    print("-" * 70)

    for q in questions:
        q_id = q["id"]
        q_text = q["question"]
        target_files = q.get("target_files", [q.get("target_file")])
        target_sym = q.get("target_symbol")

        # Measure retrieval
        t0 = time.time()
        retrieved = retriever.search(query=q_text, search_type="hybrid", top_k=5)
        retrieval_lat = round((time.time() - t0) * 1000, 2)  # ms
        retrieval_latencies.append(retrieval_lat)

        # Calculate MRR
        rr = 0.0
        r3 = 0
        hit_rank = -1
        for rank, item in enumerate(retrieved, start=1):
            norm_item_fp = item.file_path.replace("\\", "/")
            if any(tf in norm_item_fp or norm_item_fp.endswith(tf) for tf in target_files):
                if rr == 0.0:
                    rr = 1.0 / rank
                    hit_rank = rank
                if rank <= 3:
                    r3 = 1
                break

        reciprocal_ranks.append(rr)
        recall_at_3.append(r3)

        # Run RAG generation & citation checking
        t1 = time.time()
        assistant_msg, _ = rag_service.answer_question(question=q_text, user=eval_user, top_k=5)
        rag_lat = round((time.time() - t1) * 1000, 2)

        # Citation correctness
        citations = assistant_msg.citations or []
        cited_targets = 0
        for c in citations:
            norm_c_fp = c.get("file_path", "").replace("\\", "/")
            if any(tf in norm_c_fp for tf in target_files):
                cited_targets += 1
        cit_rate = (cited_targets / len(citations)) if citations else 1.0
        citation_correct_rates.append(cit_rate)

        print(f"[{q_id}] Hit Rank: {hit_rank if hit_rank > 0 else 'Miss'} | RR: {rr:.2f} | Latency: {retrieval_lat}ms")

        results.append({
            "id": q_id,
            "question": q_text,
            "target_files": target_files,
            "target_symbol": target_sym,
            "hit_rank": hit_rank,
            "reciprocal_rank": rr,
            "recall@3": r3,
            "retrieval_latency_ms": retrieval_lat,
            "rag_latency_ms": rag_lat,
            "citation_accuracy": cit_rate
        })

    # Summary
    mean_mrr = sum(reciprocal_ranks) / max(1, len(reciprocal_ranks))
    mean_recall_3 = sum(recall_at_3) / max(1, len(recall_at_3))
    avg_latency = sum(retrieval_latencies) / max(1, len(retrieval_latencies))
    mean_cit_acc = sum(citation_correct_rates) / max(1, len(citation_correct_rates))

    summary = {
        "benchmark_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_questions": len(questions),
        "mean_reciprocal_rank_mrr": round(mean_mrr, 4),
        "recall_at_3": round(mean_recall_3, 4),
        "average_retrieval_latency_ms": round(avg_latency, 2),
        "citation_accuracy_rate": round(mean_cit_acc, 4),
        "question_details": results
    }

    # Save to evaluation/results
    results_dir = Path(__file__).resolve().parent.parent.parent / "evaluation" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    report_file = results_dir / "eval_report.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("\n" + "=" * 70)
    print(" BENCHMARK RESULTS SUMMARY")
    print("=" * 70)
    print(f" Mean Reciprocal Rank (MRR) : {summary['mean_reciprocal_rank_mrr']:.4f}")
    print(f" Recall@3                   : {summary['recall_at_3'] * 100:.1f}%")
    print(f" Average Retrieval Latency  : {summary['average_retrieval_latency_ms']} ms")
    print(f" Citation Accuracy Rate     : {summary['citation_accuracy_rate'] * 100:.1f}%")
    print(f" Full Report Saved To       : {report_file}")
    print("=" * 70)

    db.close()
    return summary


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="RepoSage RAG Benchmark")
    parser.add_argument("--mock", action="store_true", help="Force mock LLM provider for benchmark")
    parser.add_argument("--provider", type=str, default=None, help="LLM provider override")
    args = parser.parse_args()
    run_evaluation(mock_mode=args.mock, provider=args.provider)
