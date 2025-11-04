import frappe

def send_response(status="success", message="", data=None, status_code = None , http_status=200):

    if  not data:
        frappe.local.response = frappe._dict({

            "status_code": status_code, 
            "status": status,
            "message": message,
        })
        frappe.local.response.http_status_code = http_status

    else:
        frappe.local.response = frappe._dict({

            "status_code": status_code, 
            "status": status,
            "message": message,
            "data": data
        })
        frappe.local.response.http_status_code = http_status


