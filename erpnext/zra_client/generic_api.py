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



def send_response_list(status="success", message="", data=None, status_code=200, http_status=200):

    response_payload = {
        "status_code": status_code,
        "status": status,
        "message": message
    }

    if data is not None:
        if isinstance(data, dict) and "success" in data and "data" in data:
            response_payload["data"] = data["data"]
            response_payload["pagination"] = data.get("pagination", {})
        else:
            response_payload["data"] = data

    frappe.local.response = frappe._dict(response_payload)
    frappe.local.response.http_status_code = http_status
