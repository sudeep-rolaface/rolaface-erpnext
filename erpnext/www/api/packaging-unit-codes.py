import frappe

def get_context(context):
    frappe.response["type"] = "json"

    frappe.response["message"] = {
        "status": "success",
        "data": [
            {"code": "BOX", "description": "Box"},
            {"code": "CTN", "description": "Carton"},
            {"code": "PLT", "description": "Pallet"},
        ]
    } 
