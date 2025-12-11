from erpnext.zra_client.generic_api import send_response
from datetime import datetime, date
from frappe import _
import frappe


@frappe.whitelist(allow_guest=False)
def create_proforma_api():
    data = frappe.local.form_dict