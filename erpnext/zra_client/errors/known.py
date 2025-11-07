import requests
import frappe

def known_error_check(api_func):
    try:
        return api_func()
    except requests.exceptions.Timeout:
        frappe.throw("Request timed out. Please try again later.")
    except requests.exceptions.ConnectionError:
        frappe.throw("Network problem detected. Please check your connection.")
    except requests.exceptions.HTTPError as e:
        status = getattr(e.response, "status_code", "unknown")
        if status == 404:
            frappe.throw("Requested resource not found (404). Please check the input and try again.")
        else:
            frappe.throw(f"HTTP error {status} occurred while processing your request.")
    except Exception as e:
        frappe.throw(f"An unexpected error occurred: {str(e)}")