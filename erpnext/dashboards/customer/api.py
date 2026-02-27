from frappe import _
import frappe
from frappe.utils import flt
from frappe.utils.data import getdate
from erpnext.zra_client.generic_api import send_response  

@frappe.whitelist(allow_guest=False, methods=["GET"])
def summary():
    try:


        total_customers = frappe.db.count("Customer")

        total_individual = frappe.db.count(
            "Customer", {"customer_type": "Individual"}
        )

        total_company = frappe.db.count(
            "Customer", {"customer_type": "Company"}
        )

        total_partnership = frappe.db.count(
            "Customer", {"customer_type": "Partnership"}
        )
        
        lop_count = frappe.db.count(
            "Customer",
            {"tax_category": "Lpo"}
        )

        export_count = frappe.db.count(
            "Customer",
            {"tax_category": "EXPORT"}
        )

        non_export_count = frappe.db.count(
            "Customer",
            {"tax_category": ["!=", "EXPORT"]}
        )

        data = {
            "cards": {
                "totalCustomers": total_customers,
                "totalIndividualCustomers": total_individual,
                "totalCompanyCustomers": total_company,
                "lopCustomers": lop_count,
                "exportCustomers": export_count,
                "nonExportCustomers": non_export_count
            }
        }

        return send_response(
            status="success",
            message="Customer dashboard retrieved successfully",
            data=data,
            status_code=200,
            http_status=200
        )

    except Exception as e:
        return send_response(
            status="error",
            message=str(e),
            data=None,
            status_code=500,
            http_status=500
        )