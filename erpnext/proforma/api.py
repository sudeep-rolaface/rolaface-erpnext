from erpnext.zra_client.generic_api import send_response
from datetime import datetime, date
from frappe import _
import frappe


@frappe.whitelist(allow_guest=False)
def get_proforma_invoices():
    try:
        proforma_invoices = frappe.get_all(
            "Proforma",
            fields=[
                "name",
                "customer_name",
                "date_of_invoice",
                "due_date",
            ],
            filters={
                "docstatus": 1
            },
            order_by="date_of_invoice"
        )

        send_response(
            status="success",
            message=_("Proforma Invoices fetched successfully"),
            data=proforma_invoices,
            status_code=200,
            http_status=200
        )
        return

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), _("Error fetching Proforma Invoices"))
        return send_response(
            status="error",
            message=_("An error occurred while fetching Proforma Invoices."),
            data={"error": str(e)},
            status_code=500,
            http_status=500
        )



@frappe.whitelist(allow_guest=False)
def create_proforma_invoice():
    import frappe
    from datetime import datetime, date
    from frappe import _

    data = frappe.local.form_dict

    # --------------------
    # Extract input
    # --------------------
    customer_id = data.get("customer_id")
    date_of_invoice = data.get("date_of_invoice")
    due_date = data.get("due_date")
    currency = data.get("currency")
    status = data.get("status", "Draft")  # Default to Draft

    # --------------------
    # Validation
    # --------------------
    VALID_STATUSES = ["Draft", "Sent", "Paid", "Overdue"]
    SUPPORTED_CURRENCIES = ["USD", "EUR", "ZMW"]
    DATE_FORMATS = ["%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y"]

    if not customer_id:
        return send_response(status="error", message=_("Customer id is required."), data={}, status_code=400)
    if not date_of_invoice:
        return send_response(status="error", message=_("Date of invoice is required."), data={}, status_code=400)
    if not due_date:
        return send_response(status="error", message=_("Due date is required."), data={}, status_code=400)
    if not currency:
        return send_response(status="error", message=_("Currency is required."), data={}, status_code=400)
    if status not in VALID_STATUSES:
        return send_response(status="error", message=_("Invalid status provided."), data={}, status_code=400)
    if currency not in SUPPORTED_CURRENCIES:
        return send_response(status="error", message=_("Unsupported currency provided."), data={}, status_code=400)

    # --------------------
    # Date parsing
    # --------------------
    def parse_date(value):
        for fmt in DATE_FORMATS:
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
        return None

    parsed_invoice_date = parse_date(date_of_invoice)
    parsed_due_date = parse_date(due_date)

    if not parsed_invoice_date or not parsed_due_date:
        return send_response(status="error",
                             message=_("Invalid date format. Use YYYY-MM-DD, DD-MM-YYYY, or MM/DD/YYYY."),
                             data={}, status_code=400)
    if parsed_invoice_date > parsed_due_date:
        return send_response(status="error", message=_("Due date must be after date of invoice."), data={}, status_code=400)
    if parsed_due_date < date.today():
        return send_response(status="error", message=_("Due date cannot be in the past."), data={}, status_code=400)

    # --------------------
    # Get customer name
    # --------------------
    customer_name = frappe.get_value("Customer", {"custom_id": customer_id}, "customer_name")
    if not customer_name:
        return send_response(status="error", message=_("Customer not found."), data={}, status_code=404)

    try:
        # --------------------
        # Step 1: Create parent Proforma
        # --------------------
        proforma_parent = frappe.get_doc({
            "doctype": "Proforma Invoice",
            "customer_name": customer_name,
            "date_of_invoice": parsed_invoice_date.strftime("%Y-%m-%d"),
            "due_date": parsed_due_date.strftime("%Y-%m-%d"),
            "currency": currency,
            "invoice_status": status
        })
        proforma_parent.insert(ignore_permissions=True)
        frappe.db.commit()

        return send_response(
            status="success",
            message=_("Proforma Invoice created successfully."),
            data={"proforma_name": proforma_parent.name},
            status_code=201
        )

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), _("Error creating Proforma Invoice"))
        return send_response(
            status="error",
            message=_("An error occurred while creating Proforma Invoice."),
            data={"error": str(e)},
            status_code=500
        )
