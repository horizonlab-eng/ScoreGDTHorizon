import os
from fpdf import FPDF

basedir = os.path.dirname(__file__)

class scorepdf(FPDF):

    def __init__(self, orientation, unit, format, titel:str):
        super().__init__(orientation, unit, format)
        self.titel = titel
        # Praxis: Raender passend zum Briefpapier (Einstellung "PDF und Briefpapier")
        try:
            import praxis_pdf
            self.set_margins(10, praxis_pdf.oberRand(), 10)
            self.set_auto_page_break(True, praxis_pdf.unterRand())
        except Exception:
            pass

    def header(self):
        #self.set_font("helvetica", "B", 20)
        self.add_font("dejavu", "", os.path.join(basedir, "fonts", "DejaVuSans.ttf"))
        self.add_font("dejavu", "I", os.path.join(basedir, "fonts", "DejaVuSans-Oblique.ttf"))
        self.add_font("dejavu", "B", os.path.join(basedir, "fonts", "DejaVuSans-Bold.ttf"))
        self.set_font("dejavu", "B", 18)
        self.cell(0, 10, self.titel, align="C", new_x="LMARGIN", new_y="NEXT")
