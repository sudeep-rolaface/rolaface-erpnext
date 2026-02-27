from frappe import _
import frappe
from frappe.utils import flt
from frappe.utils.data import getdate
from erpnext.zra_client.generic_api import send_response  

@frappe.whitelist(allow_guest=False, methods=["GET"])
def summary():
    try:

        total_proforma_invoices = frappe.db.count("Proforma")
        total_normal = frappe.db.count(
            "Sales Invoice",
            {"docstatus": 1, "is_return": 0, "is_debit_note": 0}
        )

        total_credit = frappe.db.count(
            "Sales Invoice",
            {"docstatus": 1, "is_return": 1, "return_against": ["!=", ""]}
        )
        
        total_debit = frappe.db.count(
            "Sales Invoice",
            {"docstatus": 1, "is_debit_note": 1}
        )
        
        total_quotation = frappe.db.count(
            "Quotation"
        )


        recent_sales = frappe.get_all(
            "Sales Invoice",
            fields=["name", "customer", "posting_date", "grand_total"],
            order_by="posting_date desc",
            limit=5
        )

        monthly_sales = frappe.db.sql("""
            SELECT
                MONTH(posting_date) AS month,
                SUM(grand_total) AS total
            FROM `tabSales Invoice`
            WHERE docstatus = 1
            AND is_return = 0
            AND YEAR(posting_date) = YEAR(CURDATE())
            GROUP BY MONTH(posting_date)
            ORDER BY MONTH(posting_date)
        """, as_dict=True)

        monthly_sales_data = [0] * 12
        for row in monthly_sales:
            month_index = row["month"] - 1
            monthly_sales_data[month_index] = flt(row["total"])

        months_labels = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

        data = {
            "totalProformaInvoices": total_proforma_invoices,
            "totalQuotations": total_quotation,
            "totalSalesInvoices": total_normal,
            "totalSalesCreditNotes": total_credit,
            "totalSalesDebitNotes": total_debit,
            "recentSales": recent_sales,
            "monthlySalesGraph": {
                "labels": months_labels,
                "data": monthly_sales_data
            }
        }

        return send_response(
            status="success",
            message="Dashboard summary retrieved successfully",
            data=data,
            status_code=200,
            http_status=200
        )

    except Exception as e:
        return send_response(
            status="error",
            message=f"Error retrieving dashboard summary: {str(e)}",
            data=None,
            status_code=500,
            http_status=500
        )