from erpnext.zra_client.generic_api import send_response
from erpnext.zra_client.main import ZRAClient
from frappe import _
import random
import frappe
import json




@frappe.whitelist(allow_guest=False)
def create_item_stock_api(item_code=None, warehouse=None, qty=0):
    if not item_code or not warehouse:
        return send_response(
            status="fail",
            message="Item code and warehouse are required",
            status_code=400,
            http_status=400
        )
    try:
        stock = frappe.get_doc({
            "doctype": "Stock",
            "item_code": item_code,
            "warehouse": warehouse,
            "qty": qty
        })
        stock.insert()
        frappe.db.commit()
        return send_response(
            status="success",
            message="Stock created",
            data=stock.as_dict(),
            status_code=201,
            http_status=201
        )
    except Exception as e:
        return send_response(
            status="error",
            message=f"Failed to create stock: {str(e)}",
            status_code=500,
            http_status=500
        )

@frappe.whitelist(allow_guest=False)
def get_all_item_stocks():
    try:
        stocks = frappe.get_all("Stock", fields=["name", "item_code", "warehouse", "qty"])
        return send_response(
            status="success",
            message="Stocks retrieved",
            data=stocks,
            status_code=200,
            http_status=200
        )
    except Exception as e:
        return send_response(
            status="error",
            message=f"Failed to retrieve stocks: {str(e)}",
            status_code=500,
            http_status=500
        )

@frappe.whitelist(allow_guest=False)
def update_item_stock_api(stock_name=None, qty=None):
    if not stock_name or qty is None:
        return send_response(
            status="fail",
            message="Stock name and qty are required",
            status_code=400,
            http_status=400
        )
    try:
        stock = frappe.get_doc("Stock", stock_name)
        stock.qty = qty
        stock.save()
        frappe.db.commit()
        return send_response(
            status="success",
            message="Stock updated",
            data=stock.as_dict(),
            status_code=200,
            http_status=200
        )
    except Exception as e:
        return send_response(
            status="error",
            message=f"Failed to update stock: {str(e)}",
            status_code=500,
            http_status=500
        )

@frappe.whitelist(allow_guest=False)
def delete_item_stock_api(stock_name=None):
    if not stock_name:
        return send_response(
            status="fail",
            message="Stock name is required",
            status_code=400,
            http_status=400
        )
    try:
        frappe.delete_doc("Stock", stock_name)
        frappe.db.commit()
        return send_response(
            status="success",
            message="Stock deleted",
            status_code=200,
            http_status=200
        )
    except Exception as e:
        return send_response(
            status="error",
            message=f"Failed to delete stock: {str(e)}",
            status_code=500,
            http_status=500
        )
