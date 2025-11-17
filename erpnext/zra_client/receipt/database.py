import frappe

class UpdateRecieptUrl:
    def update_invoice(self, invoice_name, file_url):
        doc = frappe.get_doc("Sales Invoice", invoice_name)
        doc.db_set("custom_receipt", file_url)
        frappe.db.commit()
        return f"Updated invoice {invoice_name} with receipt URL: {file_url}"