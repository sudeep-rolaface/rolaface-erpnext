from erpnext.zra_client.generic_api import send_response
from erpnext.zra_client.main import ZRAClient
from frappe import _
import frappe
import re

@frappe.whitelist(allow_guest=False)
def get_all_quotations():
    try:
        quotations = frappe.get_all("Quotation", 
                                    fields=[
                                        "name", 
                                        "customer_name", 
                                        "transaction_date", 
                                        "grand_total"
                                        ])
        return send_response(
            status="success",
            message=_("Quotations fetched successfully"),
            data=quotations,
            status_code=200,
            http_status=200
        )
    
    except Exception as e:
        send_response(
            status="fail",
            message=str(e),
            status_code=500,
            http_status=500
        ) 
        return  
    

@frappe.whitelist(allow_guest=False)
def get_quotation_details():
    data = frappe.local.form_dict
    quotation_id = data.get("quotation_id")
    if not quotation_id:
        return send_response(
            status="fail",
            message=_("Quotation ID is required"),
            status_code=400,
            http_status=400
        )

    try:
        try:
            quotation = frappe.get_doc("Quotation", quotation_id)
        except frappe.DoesNotExistError:
            return send_response(
                status="fail",
                message=f"Quotation  with id { quotation_id } not found",
                status_code=404,
                http_status=404
            )

        quotation_details = {
            "name": quotation.name,
            "customer_name": quotation.customer_name,
            "transaction_date": quotation.transaction_date,
            "grand_total": quotation.grand_total,
            "items": [
                {
                    "item_code": item.item_code,
                    "item_name": item.item_name,
                    "quantity": item.qty,
                    "rate": item.rate,
                    "amount": item.amount
                } for item in quotation.items
            ]
        }

        return send_response(
            status="success",
            message=_("Quotation details fetched successfully"),
            data=quotation_details,
            status_code=200,
            http_status=200
        )

    except Exception as e:
        return send_response(
            status="fail",
            message=str(e),
            status_code=500,
            http_status=500
        )

frappe.whitelist(allow_guest=False, methods=["DELETE"])
def delete_quotation():
    data = frappe.local.form_dict
    quotation_id = data.get("quotation_id")
    if not quotation_id:
        return send_response(
            status="fail",
            message=_("Quotation ID is required"),
            status_code=400,
            http_status=400
        )

    try:
        try:
            quotation = frappe.get_doc("Quotation", quotation_id)
        except frappe.DoesNotExistError:
            return send_response(
                status="fail",
                message=f"Quotation with id { quotation_id } not found",
                status_code=404,
                http_status=404
            )

        quotation.delete()
        frappe.db.commit()

        return send_response(
            status="success",
            message=_("Quotation deleted successfully"),
            status_code=200,
            http_status=200
        )

    except Exception as e:
        return send_response(
            status="fail",
            message=str(e),
            status_code=500,
            http_status=500
        )
        
        
frappe.whitelist(allow_guest=False)
def create_quotation():
    data = frappe.local.form_dict
    customer_name = data.get("customer_name")
    items = data.get("items")

    if not customer_name or not items:
        return send_response(
            status="fail",
            message=_("Customer name and items are required"),
            status_code=400,
            http_status=400
        )

    try:
        quotation = frappe.get_doc({
            "doctype": "Quotation",
            "customer_name": customer_name,
            "items": items
        })
        quotation.insert()
        frappe.db.commit()

        return send_response(
            status="success",
            message=_("Quotation created successfully"),
            data={"quotation_id": quotation.name},
            status_code=201,
            http_status=201
        )

    except Exception as e:
        return send_response(
            status="fail",
            message=str(e),
            status_code=500,
            http_status=500
        )