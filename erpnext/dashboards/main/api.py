from frappe import _
import frappe
from frappe.utils import flt
from frappe.utils.data import getdate
from erpnext.zra_client.generic_api import send_response  

@frappe.whitelist(allow_guest=False, methods=["GET"])
def summary():
    try:
        total_customers = frappe.db.count("Customer", {"disabled": 0})
        total_suppliers = frappe.db.count("Supplier", {"disabled": 0})
        total_sales_invoices = frappe.db.count("Sales Invoice", {"docstatus": 1})
        total_purchase_invoices = frappe.db.count("Purchase Invoice", {"docstatus": 1})
        total_sales_amount = frappe.db.get_all(
            "Sales Invoice",
            filters={"docstatus": 1},
            fields=["SUM(grand_total) as total"]
        )[0].total or 0


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
            "totalCustomers": total_customers,
            "totalSuppliers": total_suppliers,
            "totalSalesInvoices": total_sales_invoices,
            "totalPurchaseInvoices": total_purchase_invoices,
            "totalSalesAmount": flt(total_sales_amount),
            "recentSales": recent_sales,
            "monthlySalesGraph": {
                "labels": months_labels,
                "data": monthly_sales_data
            }
        }

        return send_response(
            status="success",
            message="Summary retrieved successfully",
            data=data,
            status_code=200,
            http_status=200
        )

    except Exception as e:
        return send_response(
            status="error",
            message=f"Error retrieving summary: {str(e)}",
            data=None,
            status_code=500,
            http_status=500
        )