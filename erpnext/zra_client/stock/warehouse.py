from erpnext.zra_client.generic_api import send_response
from erpnext.zra_client.main import ZRAClient
from frappe import _
import random
import frappe
import json

@frappe.whitelist(allow_guest=False)
def create_warehouse_api(warehouse_name=None, warehouse_type=None, company="Izyane"):
    if not warehouse_name:
        return send_response(
            status="fail",
            message="Warehouse name required (warehouse_name)",
            status_code=400,
            http_status=400
        )
    try:
        existing = frappe.get_all("Warehouse", filters={"warehouse_name": warehouse_name})
        if existing:
            return send_response(
                status="fail",
                message=f"Warehouse '{warehouse_name}' already exists",
                status_code=400,
                http_status=400
            )

        warehouse = frappe.get_doc({
            "doctype": "Warehouse",
            "warehouse_name": warehouse_name,
            "company": company,
        })
        warehouse.insert(ignore_permissions=True)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Warehouse created",
            status_code=201,
            http_status=201
        )
    except frappe.DuplicateEntryError:
        return send_response(
            status="fail",
            message=f"Warehouse '{warehouse_name}' already exists",
            status_code=409,
            http_status=409
        )
    except Exception as e:
        return send_response(
            status="error",
            message=f"Failed to create warehouse: {str(e)}",
            status_code=500,
            http_status=500
        )


@frappe.whitelist(allow_guest=False)
def get_all_warehouses():
    try:
        warehouses = frappe.get_all("Warehouse", fields=["name"])
        return send_response(
            status="success",
            message="Warehouses retrieved",
            data=warehouses,
            status_code=200,
            http_status=200
        )
    except Exception as e:
        return send_response(
            status="error",
            message=f"Failed to retrieve warehouses: {str(e)}",
            status_code=500,
            http_status=500
        )

@frappe.whitelist(allow_guest=False)
def update_warehouse_api(warehouse_name=None, new_name=None, warehouse_type=None):
    if not warehouse_name:
        return send_response(
            status="fail",
            message="Current Warehouse name is required (warehouse_name)",
            status_code=400,
            http_status=400
        )
    if not new_name:
        return send_response(
            status="fail",
            message="New Warehouse name is required (new_name)",
            status_code=400,
            http_status=400
        )
    try:
        warehouse_exists = frappe.db.exists("Warehouse", warehouse_name)
        if not warehouse_exists:
            return send_response(
                status="fail",
                message=f"Warehouse '{warehouse_name}' does not exist",
                status_code=404,
                http_status=404
            )

        if frappe.db.exists("Warehouse", new_name):
            return send_response(
                status="fail",
                message=f"Warehouse '{new_name}' already exists",
                status_code=409,
                http_status=409
            )

        warehouse = frappe.get_doc("Warehouse", warehouse_name)
        warehouse.warehouse_name = new_name
        if warehouse_type:
            warehouse.warehouse_type = warehouse_type

        warehouse.save()
        frappe.db.commit()

        return send_response(
            status="success",
            message="Warehouse updated successfully",
            status_code=200,
            http_status=200
        )

    except Exception as e:
        return send_response(
            status="error",
            message=f"Failed to update warehouse: {str(e)}",
            status_code=500,
            http_status=500
        )


@frappe.whitelist(allow_guest=False)
def delete_warehouse_api(warehouse_name=None):
    if not warehouse_name:
        return send_response(
            status="fail",
            message="Warehouse name is required (warehouse_name)",
            status_code=400,
            http_status=400
        )
    try:
        frappe.delete_doc("Warehouse", warehouse_name)
        frappe.db.commit()
        return send_response(
            status="success",
            message="Warehouse deleted",
            status_code=200,
            http_status=200
        )
    except Exception as e:
        return send_response(
            status="error",
            message=f"Failed to delete warehouse: {str(e)}",
            status_code=500,
            http_status=500
        )
