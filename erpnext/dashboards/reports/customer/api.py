from erpnext.zra_client.generic_api import send_response, send_response_list
from frappe import _
import random
import frappe
import re

@frappe.whitelist(allow_guest=False)
def customer_summary_chart_data():
    try:
        # Fetch all customers
        customers = frappe.get_all(
            "Customer",
            fields=["name", "customer_name"]
        )

        summary_metrics = {
            "most_sales": None,
            "most_sales_amount": 0,
            "most_proformas": None,
            "most_proformas_count": 0,
            "most_quotations": None,
            "most_quotations_count": 0,
            "least_active": None,
            "least_active_orders": None
        }

        for cust in customers:
            customer_name = cust["name"]

            # Total sales and orders
            sales_data = frappe.db.sql("""
                SELECT 
                    COUNT(name) as total_orders,
                    SUM(grand_total) as total_sales,
                    MAX(posting_date) as last_order_date
                FROM `tabSales Invoice`
                WHERE customer=%s AND docstatus=1
            """, customer_name, as_dict=True)[0]

            total_sales = sales_data.get("total_sales") or 0
            total_orders = sales_data.get("total_orders") or 0
            last_order_date = sales_data.get("last_order_date")

            # Proformas (Draft Sales Orders or Proforma Invoices)
            proforma_count = frappe.db.count("Sales Invoice", {
                "customer": customer_name,
                "docstatus": 0  # Draft / Proforma
            })

            # Quotations (Sales Orders or Quotations)
            quotation_count = frappe.db.count("Quotation", {
                "party_name": customer_name,
            })

            # Check most sales
            if total_sales > summary_metrics["most_sales_amount"]:
                summary_metrics["most_sales"] = cust["customer_name"]
                summary_metrics["most_sales_amount"] = total_sales

            # Most proformas
            if proforma_count > summary_metrics["most_proformas_count"]:
                summary_metrics["most_proformas"] = cust["customer_name"]
                summary_metrics["most_proformas_count"] = proforma_count

            # Most quotations
            if quotation_count > summary_metrics["most_quotations_count"]:
                summary_metrics["most_quotations"] = cust["customer_name"]
                summary_metrics["most_quotations_count"] = quotation_count

            # Least active (based on last_order_date or total_orders)
            if total_orders == 0:
                summary_metrics["least_active"] = cust["customer_name"]
                summary_metrics["least_active_orders"] = 0
            elif (summary_metrics["least_active_orders"] is None 
                  or total_orders < summary_metrics["least_active_orders"]):
                summary_metrics["least_active"] = cust["customer_name"]
                summary_metrics["least_active_orders"] = total_orders

        return send_response(
            status="success",
            message="Customer summary metrics retrieved successfully",
            status_code=200,
            data=summary_metrics,
            http_status=200
        )

    except Exception as e:
        return send_response(
            status="error",
            message=f"Failed to generate customer summary: {str(e)}",
            status_code=500,
            data=None,
            http_status=500
        )