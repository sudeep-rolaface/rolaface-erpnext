from erpnext.zra_client.generic_api import send_response
import frappe

@frappe.whitelist(allow_guest=False, methods=["GET"])
def summary():
    try:
        
        total_items = frappe.db.count("Item")
        serviceItems = frappe.db.count("Item", {"custom_itemtycd": "3"})
        rawMaterialItems = frappe.db.count("Item", {"custom_itemtycd": "1"})
        finishedProductsItems = frappe.db.count("Item", {"custom_itemtycd": "2"})
        total_imported_items = frappe.db.count("Import Item")
        finalTotal = total_items + total_imported_items

        response_data = {
            "totalItems": finalTotal,
            "serviceItems": serviceItems,
            "rawMaterialItems": rawMaterialItems,
            "finishedProductsItems": finishedProductsItems,
            "totalImportedItems": total_imported_items
        }

        return send_response(
            status="success",
            message="Inventory dashboard stats retrieved successfully",
            data=response_data,
            status_code=200,
            http_status=200
        )

    except Exception as e:
        frappe.log_error(message=str(e), title="Inventory Dashboard Stats Error")
        return send_response(
            status="fail",
            message="Failed to fetch inventory stats",
            data={"error": str(e)},
            status_code=500,
            http_status=500
        )