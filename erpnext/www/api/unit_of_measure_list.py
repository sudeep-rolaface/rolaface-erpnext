import frappe
import json

no_cache = 1

def get_handler():
    """Handle GET requests to /api/resource/unit-of-measure-list"""
    
    # Check authentication
    if frappe.session.user == "Guest":
        frappe.throw("Authentication required", frappe.AuthenticationError)
    
    # Get query parameters
    fields = frappe.form_dict.get('fields', '["name"]')
    filters = frappe.form_dict.get('filters', '{}')
    limit_start = int(frappe.form_dict.get('limit_start', 0))
    limit_page_length = int(frappe.form_dict.get('limit_page_length', 20))
    order_by = frappe.form_dict.get('order_by', 'modified desc')
    
    # Parse JSON strings
    if isinstance(fields, str):
        try:
            fields = json.loads(fields)
        except:
            fields = ["name"]
    
    if isinstance(filters, str):
        try:
            filters = json.loads(filters)
        except:
            filters = {}
    
    # Get data from UOM doctype
    try:
        data = frappe.get_all(
            "UOM",
            fields=fields,
            filters=filters,
            limit_start=limit_start,
            limit_page_length=limit_page_length,
            order_by=order_by
        )
        
        # Set response as JSON
        frappe.response['message'] = {
            'data': data
        }
        
    except Exception as e:
        frappe.throw(str(e))

# This makes it work as an API endpoint
get = get_handler
