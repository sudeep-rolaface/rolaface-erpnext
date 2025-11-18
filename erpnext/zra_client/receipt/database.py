import threading
from erpnext.zra_client.main import ZRAClient
import frappe
import time

class UpdateRecieptUrl(ZRAClient):
    def update_invoice(self, invoice_name, file_url):
        def worker():
            
            frappe.init(site=self.get_current_site())
            frappe.connect()
            frappe.set_user(self.get_current_user())
            time.sleep(30)
            doc = frappe.get_doc("Sales Invoice", invoice_name)
            doc.db_set("custom_receipt", file_url)
            frappe.db.commit()
            frappe.destroy()
            return f"Updated invoice {invoice_name} with receipt URL: {file_url}"
        threading.Thread(target=worker, daemon=False).start()