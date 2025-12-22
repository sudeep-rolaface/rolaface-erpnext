from erpnext.zra_client.generic_api import send_response, send_response_list
from erpnext.selling.doctype.quotation.quotation import Quotation
from erpnext.zra_client.main import ZRAClient
from frappe.utils import getdate, today
from frappe import _
import json
import frappe
import re

ZRA_INSTANCE = ZRAClient()


def generate_Quotation_number():
    frappe.db.sql("LOCK TABLES `tabQuotation` WRITE")

    last = frappe.db.sql("""
        SELECT name FROM `tabQuotation`
        WHERE name LIKE 'QUO-%'
        ORDER BY creation DESC
        LIMIT 1
    """, as_dict=True)

    if not last:
        next_no = 1
    else:
        next_no = int(last[0]["name"].split("-")[1]) + 1

    quotation_no = f"QUO-{next_no:03d}"

    frappe.db.sql("UNLOCK TABLES")

    return quotation_no

def get_customer_details(customer_id):
    if not customer_id:
        return send_response(
            status="fail",
            message="Customer ID is required",
            status_code=400,
            http_status=400
        )

    try:
        customer = frappe.get_all("Customer", filters={"custom_id": customer_id}, limit=1)
        if not customer:
            return send_response(
                status="fail",
                message=f"Customer with ID '{customer_id}' not found",
                status_code=404,
                http_status=404
            )
        
        customer_doc = frappe.get_doc("Customer", customer[0]["name"])

        def safe_attr(obj, attr):
            return getattr(obj, attr, "") or ""

        data = {
            "custom_customer_tpin": safe_attr(customer_doc, "tax_id"),
            "name": safe_attr(customer_doc, "name"),
            "customer_name": safe_attr(customer_doc, "customer_name"),
        }
        return data
    
    except Exception as e:
        return send_response(
            status="fail",
            message=str(e),
            status_code=500,
            http_status=500
        )

@frappe.whitelist(allow_guest=False)
def get_all_quotations():
    try:
        args = frappe.request.args
        page = args.get("page")
        if not page:
            return send_response(
                status="error",
                message="'page' parameter is required.",
                data=None,
                status_code=400,
                http_status=400
            )
        try:
            page = int(page)
            if page < 1:
                raise ValueError
        except ValueError:
            return send_response(
                status="error",
                message="'page' must be a positive integer.",
                data=None,
                status_code=400,
                http_status=400
            )

        
        page_size = args.get("page_size")
        if not page_size:
            return send_response(
                status="error",
                message="'page_size' parameter is required.",
                data=None,
                status_code=400,
                http_status=400
            )
        try:
            page_size = int(page_size)
            if page_size < 1:
                raise ValueError
        except ValueError:
            return send_response(
                status="error",
                message="'page_size' must be a positive integer.",
                data=None,
                status_code=400,
                http_status=400
            )

        start = (page - 1) * page_size
        end = start + page_size

        all_quotations = frappe.get_all(
            "Quotation",
            fields=[
                "name",
                "customer_name",
                "custom_industry_bases",
                "transaction_date",
                "valid_till",
                "grand_total",
                "currency"
            ],
            order_by="creation desc"
        )

        total_quotations = len(all_quotations)

        if total_quotations == 0:
            return send_response(
                status="success",
                message="No quotations found.",
                data=[],
                status_code=200,
                http_status=200
            )


        quotations = all_quotations[start:end]
        total_pages = (total_quotations + page_size - 1) // page_size

        response_data = {
            "success": True,
            "message": "Quotations fetched successfully",
            "data": quotations,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total_quotations,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1
            }
        }

        return send_response_list(
            status="success",
            message="Quotations fetched successfully",
            status_code=200,
            http_status=200,
            data=response_data
        )

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get All Quotations API Error")
        return send_response(
            status="fail",
            message=str(e),
            status_code=500,
            http_status=500
        )

    

@frappe.whitelist(allow_guest=False)
def get_quotation_details():
    data = frappe.local.form_dict
    quotation_id = data.get("quotation_id")
    if not quotation_id:
        return send_response(
            status="fail",
            message=_("Quotation ID is required"),
            status_code=400,
            http_status=400
        )

    try:
        try:
            quotation = frappe.get_doc("Quotation", quotation_id)
        except frappe.DoesNotExistError:
            return send_response(
                status="fail",
                message=f"Quotation  with id { quotation_id } not found",
                status_code=404,
                http_status=404
            )

        quotation_details = {
            "name": quotation.name,
            "customer_name": quotation.customer_name,
            "currency": quotation.currency,
            "custom_industry_bases": quotation.custom_industry_bases,
            "transaction_date": quotation.transaction_date,
            "valid_till": quotation.valid_till,
            "grand_total": quotation.grand_total,
            "custom_tc": quotation.custom_tc,
            "custom_swift": quotation.custom_swift,
            "custom_bank_name": quotation.custom_bank_name,
            "custom_payment_terms": quotation.custom_payment_terms,
            "custom_payment_method": quotation.custom_payment_method,
            "custom_account_number": quotation.custom_account_number,
            "custom_routing_number": quotation.custom_routing_number,
            "custom_billing_address_line_1": quotation.custom_billing_address_line_1,
            "custom_billing_address_line_2": quotation.custom_billing_address_line_2,
            "custom_billing_address_city": quotation.custom_billing_address_city,
            "custom_billing_address_postal_code" : quotation.custom_billing_address_postal_code,
            "items": [
                {
                    "item_code": item.item_code,
                    "item_name": item.item_name,
                    "quantity": item.qty,
                    "rate": item.rate,
                    "amount": item.amount
                } for item in quotation.items
            ]
        }

        return send_response(
            status="success",
            message=_("Quotation details fetched successfully"),
            data=quotation_details,
            status_code=200,
            http_status=200
        )

    except Exception as e:
        return send_response(
            status="fail",
            message=str(e),
            status_code=500,
            http_status=500
        )

@frappe.whitelist(allow_guest=False)
def delete_quotation():
    data = frappe.local.form_dict
    quotation_id = data.get("quotation_id")
    if not quotation_id:
        return send_response(
            status="fail",
            message=_("Quotation ID is required"),
            status_code=400,
            http_status=400
        )

    try:
        try:
            quotation = frappe.get_doc("Quotation", quotation_id)
        except frappe.DoesNotExistError:
            return send_response(
                status="fail",
                message=f"Quotation with id { quotation_id } not found",
                status_code=404,
                http_status=404
            )

        quotation.delete()
        frappe.db.commit()

        return send_response(
            status="success",
            message=_("Quotation deleted successfully"),
            status_code=200,
            http_status=200
        )

    except Exception as e:
        return send_response(
            status="fail",
            message=str(e),
            status_code=500,
            http_status=500
        )



@frappe.whitelist(allow_guest=False)
def create_quotation():
    data = frappe.local.form_dict

    try:
        payload = json.loads(frappe.local.request.get_data().decode("utf-8"))
    except Exception as e:
        return send_response(status="fail", message=f"Invalid JSON payload: {str(e)}", status_code=400, http_status=400)
    
    customer_id = payload.get("customerId")
    currencyCd = payload.get("currencyCode", "ZMW")
    exchangeRt = float(payload.get("exchangeRt", 1))
    invoiceType = payload.get("invoiceType")
    invoiceStatus = payload.get("invoiceStatus")
    dateOfInvoice = payload.get("dateOfInvoice")
    dueDate = payload.get("dueDate")
    items = payload.get("items", [])
    
    if not dateOfInvoice:
        return send_response(status="fail", message="date Of Invoice is required", status_code=400, http_status=400)

    if not customer_id:
        return send_response(status="fail", message="customerId is required", status_code=400, http_status=400)

    if not dueDate:
        return send_response(status="fail", message="dueDate is required", status_code=400, http_status=400)

    if getdate(dueDate) < getdate(today()):
        return send_response(status="fail", message="Due Date cannot be in the past", status_code=400, http_status=400)

    if not items or not isinstance(items, list):
        return send_response(status="fail", message="Items must be a non-empty list", status_code=400, http_status=400)

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
        return send_response(status="fail", message="paymentMethod is required", status_code = 400, http_status=400)


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

    next_quotation_id = generate_Quotation_number()

    try:

        quotation = frappe.get_doc({
            "doctype": "Quotation",
            "name": next_quotation_id,
            "customer": customer_data.get("name"),
            "customer_name": customer_data.get("customer_name"),
            "invoice_type": invoiceType,
            "invoice_status": invoiceStatus,
            "currency": currencyCd,
            "exchange_rate": exchangeRt,
            "due_date": dueDate,
            "date_of_invoice": dateOfInvoice,
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
        quotation.insert(ignore_permissions=True)

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
                "proforma_id": next_proforma_invoice_id,
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
            "invoiceno": next_quotation_id,
            "general": general,
            "delivery": delivery,
            "cancellation": cancellation,
            "warranty": warranty,
            "liability": liability
        }).insert(ignore_permissions=True)


        frappe.get_doc({
            "doctype": "Sale Invoice Selling Payment",
            "invoiceno": next_quotation_id,
            "duedates": dueDates,
            "latecharges": lateCharges,
            "taxes": tax_notes,
            "notes": notes
        }).insert(ignore_permissions=True)


        for phase in phases:
            frappe.get_doc({
                "doctype": "Sale Invoice Selling Payment Phases",
                "invoiceno": next_quotation_id,
                "phase_name": phase.get("name"),
                "percentage": phase.get("percentage"),
                "condition": phase.get("condition")
            }).insert(ignore_permissions=True)

        frappe.db.commit()

        return send_response(
            status="success",
            message="Quotation created successfully",
            status_code=200
        )

    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Create Quotation API Error")
        return send_response("fail", str(e), 500)
        
@frappe.whitelist(allow_guest=False)
def update_quotation():
    data = frappe.local.form_dict
    quotation_id = data.get("quotation_id")

    if not quotation_id:
        return send_response(
            status="fail",
            message="Quotation ID is required",
            status_code=400,
            http_status=400,
        )

    try:
        quotation = frappe.get_doc("Quotation", quotation_id)
    except frappe.DoesNotExistError:
        return send_response(
            status="fail",
            message=f"Quotation {quotation_id} not found",
            status_code=404,
            http_status=404,
        )

    if quotation.docstatus != 0:
        return send_response(
            status="fail",
            message="Cannot update submitted or cancelled Quotation",
            status_code=400,
            http_status=400,
        )


    optional_fields = [
        "customer",
        "transaction_date",
        "custom_swift",
        "custom_bank_name",
        "custom_payment_terms",
        "custom_payment_method",
        "custom_account_number",
        "custom_routing_number",
        "custom_billing_address_line_1",
        "custom_billing_address_line_2",
        "custom_billing_address_city",
        "custom_billing_address_postal_code",
    ]

    for field in optional_fields:
        if field in data:
            quotation.set(field, data.get(field))
    if "items" in data:
        quotation.items = []   
        for item in data.get("items"):
            quotation.append("items", {
                "item_code": item.get("item_code"),
                "qty": item.get("qty"),
                "rate": item.get("rate"),
            })

    try:
        quotation.save(ignore_permissions=True)
    except Exception as e:
        return send_response(
            status="fail",
            message=f"Failed to update: {str(e)}",
            status_code=500,
            http_status=500,
        )

    return send_response(
        status="success",
        message="Quotation updated successfully",
        status_code=200,
        http_status=200,
    )
