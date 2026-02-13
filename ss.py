import customtkinter as ctk
import sqlite3
import math
from tkinter import messagebox
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ==============================
# DATABASE SETUP
# ==============================

conn = sqlite3.connect("clients.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    basic REAL,
    hra REAL,
    rent REAL,
    other REAL,
    capital REAL,
    other_income REAL,
    sec80c REAL,
    sec80ccd REAL
)
""")
conn.commit()

# ==============================
# TAX ENGINE
# ==============================

class TaxEngine:

    OLD_SLABS = [
        (250000, 0.0),
        (500000, 0.05),
        (1000000, 0.20),
        (float('inf'), 0.30),
    ]

    NEW_SLABS = [
        (300000, 0.0),
        (600000, 0.05),
        (900000, 0.10),
        (1200000, 0.15),
        (1500000, 0.20),
        (float('inf'), 0.30),
    ]

    CESS = 0.04

    def slab_tax(self, income, slabs):
        tax = 0
        prev = 0
        for limit, rate in slabs:
            if income > prev:
                tax += (min(income, limit) - prev) * rate
                prev = limit
            else:
                break
        return tax

    def hra_exemption(self, hra, rent, basic, metro):
        percent = 0.50 if metro else 0.40
        return min(hra, max(0, rent - 0.1 * basic), percent * basic)

    def rebate_87a(self, income, tax):
        if income <= 500000:
            return tax
        return 0

    def surcharge(self, income, tax):
        if income > 50000000:
            return tax * 0.37
        elif income > 20000000:
            return tax * 0.25
        elif income > 10000000:
            return tax * 0.15
        elif income > 5000000:
            return tax * 0.10
        return 0

    def compute(self, gross, deductions, regime):
        taxable = max(0, gross - deductions)
        slabs = self.OLD_SLABS if regime == "Old" else self.NEW_SLABS

        tax = self.slab_tax(taxable, slabs)

        rebate = self.rebate_87a(taxable, tax)
        tax -= rebate

        surcharge_amt = self.surcharge(taxable, tax)
        tax += surcharge_amt

        cess_amt = tax * self.CESS
        tax += cess_amt

        return taxable, math.ceil(tax)

# ==============================
# PDF EXPORT
# ==============================

def generate_pdf(name, taxable, tax_old, tax_new):
    filename = f"{name}_Tax_Report.pdf"
    c = canvas.Canvas(filename, pagesize=A4)

    c.drawString(50, 800, f"Income Tax Report - {name}")
    c.drawString(50, 760, f"Taxable Income: ₹{taxable:,.2f}")
    c.drawString(50, 730, f"Tax (Old Regime): ₹{tax_old:,.2f}")
    c.drawString(50, 700, f"Tax (New Regime): ₹{tax_new:,.2f}")

    better = "Old Regime" if tax_old < tax_new else "New Regime"
    c.drawString(50, 670, f"Better Option: {better}")

    c.save()

# ==============================
# GUI APPLICATION
# ==============================

class TaxApp(ctk.CTk):

    def __init__(self):
        super().__init__()

        self.title("Commercial Indian Tax Software")
        self.geometry("900x800")

        self.engine = TaxEngine()
        self.create_widgets()

    def create_widgets(self):

        title = ctk.CTkLabel(self, text="Indian Income Tax Software",
                             font=("Arial", 26, "bold"))
        title.pack(pady=20)

        self.frame = ctk.CTkScrollableFrame(self, width=800, height=500)
        self.frame.pack(pady=10)

        self.entries = {}

        fields = [
            "Client Name",
            "Basic Salary",
            "HRA Received",
            "Rent Paid",
            "Other Allowances",
            "Capital Gains",
            "Other Income",
            "80C Investment",
            "80CCD(1B)"
        ]

        for field in fields:
            label = ctk.CTkLabel(self.frame, text=field)
            label.pack(pady=5)
            entry = ctk.CTkEntry(self.frame, width=400)
            entry.pack(pady=5)
            self.entries[field] = entry

        self.metro_var = ctk.BooleanVar()
        metro = ctk.CTkCheckBox(self.frame, text="Metro City",
                                variable=self.metro_var)
        metro.pack(pady=5)

        btn_frame = ctk.CTkFrame(self)
        btn_frame.pack(pady=20)

        ctk.CTkButton(btn_frame, text="Calculate Tax",
                      command=self.calculate).grid(row=0, column=0, padx=10)

        ctk.CTkButton(btn_frame, text="Save Client",
                      command=self.save_client).grid(row=0, column=1, padx=10)

        ctk.CTkButton(btn_frame, text="Export PDF",
                      command=self.export_pdf).grid(row=0, column=2, padx=10)

        self.result = ctk.CTkLabel(self, text="", font=("Arial", 18))
        self.result.pack(pady=20)

    def calculate(self):
        try:
            basic = float(self.entries["Basic Salary"].get() or 0)
            hra = float(self.entries["HRA Received"].get() or 0)
            rent = float(self.entries["Rent Paid"].get() or 0)
            other = float(self.entries["Other Allowances"].get() or 0)
            capital = float(self.entries["Capital Gains"].get() or 0)
            other_income = float(self.entries["Other Income"].get() or 0)
            sec80c = min(float(self.entries["80C Investment"].get() or 0), 150000)
            sec80ccd = min(float(self.entries["80CCD(1B)"].get() or 0), 50000)

            std = 50000
            hra_ex = self.engine.hra_exemption(
                hra, rent, basic, self.metro_var.get()
            )

            gross = basic + hra + other + capital + other_income
            deductions = std + hra_ex + sec80c + sec80ccd

            taxable_old, tax_old = self.engine.compute(
                gross, deductions, "Old"
            )
            taxable_new, tax_new = self.engine.compute(
                gross, std, "New"
            )

            better = "Old Regime" if tax_old < tax_new else "New Regime"

            self.taxable = taxable_old
            self.tax_old = tax_old
            self.tax_new = tax_new

            self.result.configure(
                text=f"""
Taxable Income: ₹{taxable_old:,.0f}

Tax (Old): ₹{tax_old:,.0f}
Tax (New): ₹{tax_new:,.0f}

Better Option: {better}
"""
            )

        except:
            messagebox.showerror("Error", "Invalid Input")

    def save_client(self):
        name = self.entries["Client Name"].get()

        cursor.execute("""
        INSERT INTO clients
        (name, basic, hra, rent, other, capital, other_income, sec80c, sec80ccd)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            name,
            self.entries["Basic Salary"].get(),
            self.entries["HRA Received"].get(),
            self.entries["Rent Paid"].get(),
            self.entries["Other Allowances"].get(),
            self.entries["Capital Gains"].get(),
            self.entries["Other Income"].get(),
            self.entries["80C Investment"].get(),
            self.entries["80CCD(1B)"].get(),
        ))

        conn.commit()
        messagebox.showinfo("Success", "Client Saved")

    def export_pdf(self):
        name = self.entries["Client Name"].get()
        generate_pdf(name, self.taxable, self.tax_old, self.tax_new)
        messagebox.showinfo("Success", "PDF Exported")

# ==============================
# RUN APP
# ==============================

if __name__ == "__main__":
    app = TaxApp()
    app.mainloop()
