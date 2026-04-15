from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
import os
import json
from datetime import datetime
# Ensure this utility actually receives and processes the 'data' dictionary
from .utils import generate_monthly_pdf as generate_pdf_report

router = APIRouter()

# Setup paths to your data
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HISTORY_PATH = os.path.join(BASE_DIR, "data", "detections_history.json")

@router.get("/download-summary")
async def download_monthly_report(background_tasks: BackgroundTasks):
    try:
        # 1. Prepare the Data (Feeding the statistics)
        report_data = {
            "brand_name": "BrandGuardian AI Client", 
            "total_scans": 0, 
            "infringements": [],
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Load real data from your history file
        if os.path.exists(HISTORY_PATH):
            with open(HISTORY_PATH, "r") as f:
                try:
                    history = json.load(f)
                    report_data["infringements"] = history
                    report_data["total_scans"] = len(history)
                    # Add summary stats for the PDF
                    report_data["high_risk_count"] = len([i for i in history if i.get("risk") == "High"])
                    report_data["medium_risk_count"] = len([i for i in history if i.get("risk") == "Medium"])
                except json.JSONDecodeError:
                    print("⚠️ History file is empty or corrupted.")

        # 2. Define file path for the temporary PDF
        report_filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        temp_dir = os.path.join(BASE_DIR, "temp_reports")
        os.makedirs(temp_dir, exist_ok=True)
        report_path = os.path.join(temp_dir, report_filename)

        # 3. Trigger PDF Generation
        # IMPORTANT: Check your utils.py to ensure it uses Jinja2 to inject 'report_data' into the HTML
        generate_pdf_report(
            data=report_data,
            template_name="monthly_summary.html", 
            output_path=report_path
        )

        # Safety Check: Verify the file was actually written to disk
        if not os.path.exists(report_path) or os.path.getsize(report_path) < 100:
            raise HTTPException(status_code=500, detail="PDF Generation Failed - File is missing or empty")

        # 4. Return the file and delete it after download
        background_tasks.add_task(os.remove, report_path)
        
        return FileResponse(
            path=report_path, 
            filename=f"BrandGuardian_Report_{datetime.now().strftime('%b_%Y')}.pdf",
            media_type="application/pdf"
        )

    except Exception as e:
        print(f"🚨 Report Route Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"PDF Engine Error: {str(e)}")