from frappe import _
import frappe
from erpnext.zra_client.generic_api import send_response  

@frappe.whitelist(allow_guest=False, methods=["GET"])
def summary():
    try:
        
        total_suppliers = frappe.db.count("Supplier")
        active_suppliers = frappe.db.count(
            "Supplier",
            {"custom_status": "Active"}
        )
        inactive_suppliers = frappe.db.count(
            "Supplier",
            {"custom_status": "Inactive"}
        )
        
        total_purchase_invoices = frappe.db.count("Purchase Invoice")
        total_pos = frappe.db.count("Purchase Order")


    

        return send_response(
            status="success",
            message="Procurement statistics fetched successfully",
            data={
                "totalSuppliers": total_suppliers,
                "activeSuppliers": active_suppliers,
                "inactiveSuppliers": inactive_suppliers,
                "totalPurchaseInvoice":total_purchase_invoices,
                "totalPurchaseOrder":total_pos,
            },
            status_code=200,
            http_status=200
        )

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Supplier Stats Error")
        return send_response(
            status="error",
            message=str(e),
            data={},
            status_code=500,
            http_status=500
        )