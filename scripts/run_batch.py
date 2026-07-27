import asyncio
from pathlib import Path
from invoice_pipeline.workflow import graph


def tally_extractions(results: list) -> dict:
    counts = {
        "error": 0,
        "specialist_only": 0,
        "frontier_fallback": 0,
        "human_review": 0,
    }
    for result in results:
        if isinstance(result, Exception):
            counts["error"] += 1
            print(result)
        elif result["attempt"] == "specialist" and not result["reconciliation_issues"]:
            counts["specialist_only"] += 1
        elif result["attempt"] == "frontier" and not result["reconciliation_issues"]:
            counts["frontier_fallback"] += 1
        else:
            counts["human_review"] += 1
    print(counts)


async def run_agent_batch(img_dir: str) -> list:
    img_paths = sorted(Path(img_dir).glob("*.png"))
    inputs = [{"image": str(p), "invoice": None} for p in img_paths]

    results = await graph.abatch(inputs, return_exceptions=True)
    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Tally agent fallback rate and failure cases"
    )
    parser.add_argument("img_dir", type=str, help="Image directory to run agent on")
    args = parser.parse_args()

    results = asyncio.run(run_agent_batch(args.img_dir))
    tally_extractions(results)
