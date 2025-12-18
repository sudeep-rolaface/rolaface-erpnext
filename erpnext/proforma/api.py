from erpnext.zra_client.generic_api import send_response
from erpnext.zra_client.main import ZRAClient
from frappe.utils import today, getdate
import frappe
import json
import random

ZRA_INSTANCE = ZRAClient()


@frappe.whitelist(allow_guest=False)
def create_proforma_api():
    try:
        payload = json.loads(frappe.local.request.get_data().decode("utf-8"))
    except Exception as e:
        return send_response("fail", f"Invalid JSON payload: {str(e)}", 400)
    
    customer_id = payload.get("customerId")
    currencyCd = payload.get("currencyCode", "ZMW")
    exchangeRt = float(payload.get("exchangeRt", 1))
    invoiceType = payload.get("invoiceType")
    invoiceStatus = payload.get("invoiceStatus")
    dueDate = payload.get("dueDate")
    items = payload.get("items", [])

    if not customer_id:
        return send_response("fail", "customerId is required", 400)

    if not dueDate:
        return send_response("fail", "dueDate is required", 400)

    if getdate(dueDate) < getdate(today()):
        return send_response("fail", "Due Date cannot be in the past", 400)

    if not items or not isinstance(items, list):
        return send_response("fail", "Items must be a non-empty list", 400)

    customer_data = ZRA_INSTANCE.get_customer_details(customer_id)
    if not customer_data or customer_data.get("status") == "fail":
        return customer_data


    billing = payload.get("billingAddress", {})
    shipping = payload.get("shippingAddress", {})

    payment_info = payload.get("paymentInformation", {})
    payment_terms = payment_info.get("paymentTerms")
    payment_method = payment_info.get("paymentMethod")
    bank_name = payment_info.get("bankName")
    account_number = payment_info.get("accountNumber")
    routing_number = payment_info.get("routingNumber")
    swift_code = payment_info.get("swiftCode")

    if not payment_method:
        return send_response("fail", "paymentMethod is required", 400)


    terms = payload.get("terms", {}).get("selling", {})
    general = terms.get("general")
    delivery = terms.get("delivery")
    cancellation = terms.get("cancellation")
    warranty = terms.get("warranty")
    liability = terms.get("liability")

    payment_terms_data = terms.get("payment", {})
    dueDates = payment_terms_data.get("dueDates")
    lateCharges = payment_terms_data.get("lateCharges")
    tax_notes = payment_terms_data.get("taxes")
    notes = payment_terms_data.get("notes")
    phases = payment_terms_data.get("phases", [])

    try:

        proforma = frappe.get_doc({
            "doctype": "Proforma",
            "customer": customer_data.get("name"),
            "customer_name": customer_data.get("customer_name"),
            "invoice_type": invoiceType,
            "invoice_status": invoiceStatus,
            "currency": currencyCd,
            "exchange_rate": exchangeRt,
            "due_date": dueDate,

            "billing_address_line_1": billing.get("line1"),
            "billing_address_line_2": billing.get("line2"),
            "billing_address_postal_code": billing.get("postalCode"),
            "billing_address_city": billing.get("city"),
            "billing_address_state": billing.get("state"),
            "billing_address_country": billing.get("country"),

   
            "shipping_address_line_1": shipping.get("line1"),
            "shipping_address_line_2": shipping.get("line2"),
            "shipping_address_postal_code": shipping.get("postalCode"),
            "shipping_address_city": shipping.get("city"),
            "shipping_address_state": shipping.get("state"),
            "shipping_address_country": shipping.get("country"),


            "payment_terms": payment_terms,
            "payment_method": payment_method,
            "bank_name": bank_name,
            "account_number": account_number,
            "routing_number": routing_number,
            "swift_code": swift_code,

            "total_items": 0,
            "total_amount": 0
        })
        proforma.insert(ignore_permissions=True)

        total_items = 0
        grand_total = 0

        for item in items:
            qty = float(item.get("quantity", 1))
            unit_price = float(item.get("price", 0))
            discount = float(item.get("discount", 0))
            tax = float(item.get("tax", 0))

            item_total = (qty * unit_price) - discount + tax

            frappe.get_doc({
                "doctype": "Proforma Item",
                "proforma_id": proforma.name,
                "item_name": item.get("itemName"),
                "item_code": item.get("itemCode"),
                "description": item.get("description"),
                "qty": qty,
                "unit_price": unit_price,
                "discount": discount,
                "tax": tax,
                "item_total": item_total
            }).insert(ignore_permissions=True)

            total_items += qty
            grand_total += item_total

        proforma.total_items = total_items
        proforma.total_amount = grand_total
        proforma.save(ignore_permissions=True)

        frappe.get_doc({
            "doctype": "Sale Invoice Selling Terms",
            "invoiceno": proforma.name,
            "general": general,
            "delivery": delivery,
            "cancellation": cancellation,
            "warranty": warranty,
            "liability": liability
        }).insert(ignore_permissions=True)


        frappe.get_doc({
            "doctype": "Sale Invoice Selling Payment",
            "invoiceno": proforma.name,
            "duedates": dueDates,
            "latecharges": lateCharges,
            "taxes": tax_notes,
            "notes": notes
        }).insert(ignore_permissions=True)


        for phase in phases:
            frappe.get_doc({
                "doctype": "Sale Invoice Selling Payment Phases",
                "invoiceno": proforma.name,
                "phase_name": phase.get("name"),
                "percentage": phase.get("percentage"),
                "condition": phase.get("condition")
            }).insert(ignore_permissions=True)

        frappe.db.commit()

        return send_response(
            status="success",
            message="Proforma created successfully",
            data={
                "proforma_id": proforma.name,
                "total_items": total_items,
                "total_amount": grand_total
            },
            status_code=200
        )

    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Create Proforma API Error")
        return send_response("fail", str(e), 500)
