import os
from fpdf import FPDF
from datetime import datetime

# Setup paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class BrandGuardianPDF(FPDF):
    def header(self):
        # Add a professional header
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'BrandGuardian AI - Infringement Summary Report', 0, 1, 'C')
        self.set_font('Arial', 'I', 10)
        self.cell(0, 10, f'Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', 0, 1, 'C')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

def generate_monthly_pdf(data: dict, **kwargs):
    """
    Takes a dictionary of monthly stats and returns a PDF.
    Does NOT require WeasyPrint or external system libraries.
    """
    output_path = kwargs.get("output_path", None)
    
    pdf = BrandGuardianPDF()
    pdf.add_page()
    
    # --- 1. OVERVIEW SECTION ---
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, f"Brand: {data.get('brand_name', 'Global Protection')}", 0, 1)
    
    pdf.set_font('Arial', '', 12)
    pdf.cell(0, 10, f"Total Scans Performed: {data.get('total_scans', 0)}", 0, 1)
    pdf.cell(0, 10, f"High Risk Detections: {data.get('high_risk_count', 0)}", 0, 1)
    pdf.cell(0, 10, f"Medium Risk Detections: {data.get('medium_risk_count', 0)}", 0, 1)
    pdf.ln(10)

    # --- 2. DETAILED INFRINGEMENTS TABLE ---
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, "Detection Details:", 0, 1)
    
    # Table Header
    pdf.set_fill_color(200, 220, 255)
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(100, 8, 'Target URL', 1, 0, 'C', 1)
    pdf.cell(40, 8, 'Confidence', 1, 0, 'C', 1)
    pdf.cell(40, 8, 'Risk Level', 1, 1, 'C', 1)

    # Table Rows
    pdf.set_font('Arial', '', 9)
    infringements = data.get('infringements', [])
    
    if not infringements:
        pdf.cell(180, 10, "No infringements detected in this period.", 1, 1, 'C')
    else:
        for item in infringements:
            # Shorten URL if too long
            url = item.get('url', 'N/A')
            display_url = (url[:50] + '..') if len(url) > 50 else url
            
            pdf.cell(100, 8, display_url, 1)
            pdf.cell(40, 8, str(item.get('confidence', 'N/A')), 1, 0, 'C')
            pdf.cell(40, 8, str(item.get('risk', 'N/A')), 1, 1, 'C')

    # --- 3. SAVE LOGIC ---
    if output_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        pdf.output(output_path)
        print(f"✅ PDF saved locally to: {output_path}")

    return pdf.output(dest='S') # Returns bytes