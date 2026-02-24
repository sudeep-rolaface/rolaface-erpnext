import frappe
import json

@frappe.whitelist()
def get_uom_list(fields=None, filters=None, limit_start=0, limit_page_length=20, order_by="modified desc"):
    """Get list of Unit of Measures"""
    
    # Parse fields
    if isinstance(fields, str):
        try:
            fields = json.loads(fields)
        except:
            fields = ["name"]
    elif fields is None:
        fields = ["name", "uom_name", "enabled"]
    
    # Parse filters
    if isinstance(filters, str):
        try:
            filters = json.loads(filters)
        except:
            filters = {}
    elif filters is None:
        filters = {}
    
    # Get data
    data = frappe.get_all(
        "UOM",
        fields=fields,
        filters=filters,
        limit_start=int(limit_start),
        limit_page_length=int(limit_page_length),
        order_by=order_by
    )
    
    return {"data": data}
