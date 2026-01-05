import asyncio
from datetime import datetime
from app.core.database import SessionLocal
from app.models import Paper, PaperSummary
from app.services.llm_service import llm_service

async def main():
    db = SessionLocal()
    try:
        # Get one recent paper
        paper = db.query(Paper).order_by(Paper.published_date.desc()).first()
        if not paper:
            print("No papers found")
            return

        print(f"Generating insights for: {paper.title}")
        summary_data = await llm_service.generate_paper_summary(paper.title, paper.abstract)
        
        if summary_data:
            print("\n--- Insights Generated ---")
            print(f"ELI5: {summary_data.get('eli5')}")
            print(f"Methodology: {summary_data.get('methodology')}")
            
            # Save to DB
            summary = PaperSummary(
                paper_id=paper.id,
                one_line_summary=summary_data["one_line_summary"],
                eli5=summary_data.get("eli5"),
                key_innovation=summary_data.get("key_innovation"),
                problem_statement=summary_data.get("problem_statement"),
                methodology=summary_data.get("methodology"),
                real_world_use_cases=summary_data.get("real_world_use_cases"),
                limitations=summary_data.get("limitations"),
                results_summary=summary_data.get("results_summary"),
                generated_by="test-script",
                generated_at=datetime.utcnow()
            )
            try:
                db.add(summary)
                db.commit()
                print("\nSaved to DB successfully!")
                print(f"Paper ID: {paper.id}")
            except Exception as e:
                print(f"\nError saving: {e}")
        else:
            print("Failed to generate summary")
            
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
