from erpnext.zra_client.receipt.generate import InvoicePDF
from datetime import datetime

class BuildPdf:
    def build_invoice(self, company_info, customer_info, invoice, items, sdc_data, payload):
        company_name, company_phone, company_email, company_tpin = company_info[0]
        cust_tpin, cust_name = customer_info[0]
        invoice_number, invoice_date, invoice_type, get_qrcode_url = invoice[0]
        current_date, sdc_id = sdc_data[0]
    
        invoice_data = {
            "company": {
                "name": company_name,
                "phone": company_phone,
                "email": company_email,
                "tpin": company_tpin,
            },
            "customer": {
                "name": cust_name,
                "tpin": cust_tpin
            },
            "invoice": {
                "number": invoice_number,
                "date": invoice_date,
                "type": invoice_type,
                "qrcode": get_qrcode_url,
            },
            "items": [
                {
                    "name": item["itemNm"],
                    "qty": item["qty"],
                    "price": item["prc"],
                    "total": item["totAmt"],
                    "tax_type": item.get("vatCatCd", "")
                }
                for item in items
            ],
            "totals": {
                "standard_rated": payload.get("taxblAmtA", 0),
                "zero_rated": payload.get("taxblAmtB", 0),
                "exempt": payload.get("taxblAmtE", 0),
                "reverse_vat": payload.get("taxblAmtRvat", 0),
                "subtotal": payload.get("totTaxblAmt", 0),
                "tax": payload.get("totTaxAmt", 0),
                "grand_total": payload.get("totAmt", 0),
                "currency": payload.get("currencyTyCd", "ZMW"),
                "exchange_rate": f"1 {payload.get('currencyTyCd', 'ZMW')} = {payload.get('exchangeRt', 1)} ZMW",
            },
            "tax_details": {
                "A": {"base": payload.get("taxblAmtA", 0), "rate": payload.get("taxRtA", 0), "tax": payload.get("taxAmtA", 0)},
                "B": {"base": payload.get("taxblAmtB", 0), "rate": payload.get("taxRtB", 0), "tax": payload.get("taxAmtB", 0)},
                "C1": {"base": payload.get("taxblAmtC1", 0), "rate": payload.get("taxRtC1", 0), "tax": payload.get("taxAmtC1", 0)},
                "C2": {"base": payload.get("taxblAmtC2", 0), "rate": payload.get("taxRtC2", 0), "tax": payload.get("taxAmtC2", 0)},
                "C3": {"base": payload.get("taxblAmtC3", 0), "rate": payload.get("taxRtC3", 0), "tax": payload.get("taxAmtC3", 0)},
                "D": {"base": payload.get("taxblAmtD", 0), "rate": payload.get("taxRtD", 0), "tax": payload.get("taxAmtD", 0)},
                "E": {"base": payload.get("taxblAmtE", 0), "rate": payload.get("taxRtE", 0), "tax": payload.get("taxAmtE", 0)},
                "F": {"base": payload.get("taxblAmtF", 0), "rate": payload.get("taxRtF", 0), "tax": payload.get("taxAmtF", 0)},
                "Ipl1": {"base": payload.get("taxblAmtIpl1", 0), "rate": payload.get("taxRtIpl1", 0), "tax": payload.get("taxAmtIpl1", 0)},
                "Ipl2": {"base": payload.get("taxblAmtIpl2", 0), "rate": payload.get("taxRtIpl2", 0), "tax": payload.get("taxAmtIpl2", 0)},
                "Tl": {"base": payload.get("taxblAmtTl", 0), "rate": payload.get("taxRtTl", 0), "tax": payload.get("taxAmtTl", 0)},
                "Ecm": {"base": payload.get("taxblAmtEcm", 0), "rate": payload.get("taxRtEcm", 0), "tax": payload.get("taxAmtEcm", 0)},
                "Exeeg": {"base": payload.get("taxblAmtExeeg", 0), "rate": payload.get("taxRtExeeg", 0), "tax": payload.get("taxAmtExeeg", 0)},
                "Rvat": {"base": payload.get("taxblAmtRvat", 0), "rate": payload.get("taxRtRvat", 0), "tax": payload.get("taxAmtRvat", 0)},
            },
            "sdc_info": {
                "invoice_date": invoice_date,
                "sdc_id": sdc_id,
                "invoice_number": invoice_number,
                "invoice_type": "Normal invoice",
                "current_date": current_date
            },
            "payment": {"type": "Bank transfer"},
            "internal_data": {}
        }

        builder = InvoicePDF(invoice_data)
        result = builder.build_pdf(invoice_number)

        print("PDF saved with file ID:", result)