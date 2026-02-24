import frappe

no_cache = 1

def get_handler():
    frappe.response['message'] = {'status': 'success', 'data': 'Hello from test endpoint'}

get = get_handler
