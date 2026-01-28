from erpnext.zra_client.generic_api import send_response, send_response_list_sale
from erpnext.zra_client.main import ZRAClient
from frappe.utils import today, getdate
import frappe
import json
import random

ZRA_INSTANCE = ZRAClient()

def generate_proforma_number():
    last_id = frappe.db.get_value(
        "Proforma",
        {},
        "id",
        order_by="creation desc"
    )

    if not last_id:
        next_no = 1
    else:
        try:
            next_no = int(last_id.split("-")[1]) + 1
        except Exception:
            next_no = 1

    return f"PRO-{next_no:05d}"



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
    
    next_proforma_invoice_id = generate_proforma_number()
    id = next_proforma_invoice_id

    try:

        proforma = frappe.get_doc({
            "doctype": "Proforma",
            "name": next_proforma_invoice_id,
            "id": id,
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
        proforma.insert(ignore_permissions=True)

        total_items = 0
        grand_total = 0

        for item in items:
            qty = float(item.get("quantity", 1))
            unit_price = float(item.get("price", 0))
            discount = float(item.get("discount", 0))
            tax = float(item.get("tax", 0))

            item_total = (qty * unit_price) - discount + tax
            getItemDetails = ZRA_INSTANCE.get_item_details(item.get("itemCode"))

            frappe.get_doc({
                "doctype": "Proforma Item",
                "proforma_id": next_proforma_invoice_id,
                "item_name": getItemDetails.get("itemName"),
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
            "invoiceno": next_proforma_invoice_id,
            "general": general,
            "delivery": delivery,
            "cancellation": cancellation,
            "warranty": warranty,
            "liability": liability
        }).insert(ignore_permissions=True)


        frappe.get_doc({
            "doctype": "Sale Invoice Selling Payment",
            "invoiceno": next_proforma_invoice_id,
            "duedates": dueDates,
            "latecharges": lateCharges,
            "taxes": tax_notes,
            "notes": notes
        }).insert(ignore_permissions=True)


        for phase in phases:
            frappe.get_doc({
                "doctype": "Sale Invoice Selling Payment Phases",
                "invoiceno": next_proforma_invoice_id,
                "phase_name": phase.get("name"),
                "percentage": phase.get("percentage"),
                "condition": phase.get("condition")
            }).insert(ignore_permissions=True)

        frappe.db.commit()

        return send_response(
            status="success",
            message="Proforma created successfully",
            status_code=200
        )

    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Create Proforma API Error")
        return send_response("fail", str(e), 500)


@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_proforma_api():
    try:
        args = frappe.request.args

        page = args.get("page")
        page_size = args.get("page_size")

        if not page or not page_size:
            return send_response(
                status="error",
                message="'page' and 'page_size' are required",
                status_code=400,
                http_status=400
            )

        try:
            page = int(page)
            page_size = int(page_size)
            if page < 1 or page_size < 1:
                raise ValueError
        except ValueError:
            return send_response(
                status="error",
                message="'page' and 'page_size' must be positive integers",
                status_code=400,
                http_status=400
            )

        start = (page - 1) * page_size

        proformas = frappe.get_all(
            "Proforma",
            fields=[
                "name",
                "id",
                "customer_name",
                "currency",
                "exchange_rate",
                "due_date",
                "total_amount",
                "invoice_status",
                "creation"
            ],
            order_by="creation desc",
            limit_start=start,
            limit_page_length=page_size
        )

        total = frappe.db.count("Proforma")

        if total == 0:
            return send_response(
                status="success",
                message="No proformas found",
                data=[],
                status_code=200,
                http_status=200
            )

        formatted = []
        for p in proformas:
            customer_tpin = frappe.db.get_value(
                "Customer",
                {"customer_name": p.customer_name},
                "tax_id"
            ) or ""

            formatted.append({
                "proformaId": p.id,
                "customerName": p.customer_name,
                "customerTpin": customer_tpin,  
                "currency": p.currency,
                "exchangeRate": p.exchange_rate,
                "dueDate": str(p.due_date),
                "totalAmount": float(p.total_amount),
                "status": p.invoice_status,
                "createdAt": str(p.creation)
            })

        total_pages = (total + page_size - 1) // page_size

        pagination = {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1
        }

        return send_response_list_sale(
            status="success",
            message="Proformas retrieved successfully",
            data=formatted,
            pagination=pagination,
            status_code=200,
            http_status=200
        )

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Proforma API Error")
        return send_response(
            status="fail",
            message=str(e),
            status_code=500,
            http_status=500
        )


@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_proforma_by_id():
    proforma_id = (frappe.form_dict.get("id") or "").strip()

    if not proforma_id:
        return send_response(
            status="fail",
            message="Proforma id is required",
            status_code=400,
            http_status=400
        )

    # ---------------- CHECK PROFORMA EXISTS ----------------
    if not frappe.db.exists("Proforma", {"id": proforma_id}):
        return send_response(
            status="fail",
            message=f"Proforma {proforma_id} not found",
            status_code=404,
            http_status=404
        )

    try:
        # ---------------- FETCH PROFORMA ----------------
        doc = frappe.get_doc("Proforma", {"id": proforma_id})

        # ---------------- FETCH ITEMS ----------------
        items = frappe.get_all(
            "Proforma Item",
            filters={"proforma_id": proforma_id},
            fields=[
                "item_code",
                "item_name",
                "description",
                "qty",
                "unit_price",
                "discount",
                "tax",
                "item_total"
            ]
        )

        formatted_items = [
            {
                "itemCode": i.item_code,
                "itemName": i.item_name,
                "description": i.description,
                "quantity": i.qty,
                "price": i.unit_price,
                "discount": i.discount,
                "tax": i.tax,
                "itemTotal": i.item_total
            } for i in items
        ]

        # ---------------- TERMS AND PAYMENTS ----------------
        terms_doc = frappe.get_doc(
            "Sale Invoice Selling Terms",
            {"invoiceno": proforma_id}
        ) if frappe.db.exists("Sale Invoice Selling Terms", {"invoiceno": proforma_id}) else None

        payment_doc = frappe.get_doc(
            "Sale Invoice Selling Payment",
            {"invoiceno": proforma_id}
        ) if frappe.db.exists("Sale Invoice Selling Payment", {"invoiceno": proforma_id}) else None

        phases = frappe.get_all(
            "Sale Invoice Selling Payment Phases",
            filters={"invoiceno": proforma_id},
            fields=["phase_name as name", "percentage", "condition"]
        )

        # ---------------- RESPONSE DATA ----------------
        data = {
            "proformaId": doc.id,  # using your custom 'id'
            "customerName": doc.customer_name,
            "currencyCode": doc.currency,
            "exchangeRt": str(doc.exchange_rate),
            "dueDate": str(doc.due_date),
            "invoiceStatus": doc.invoice_status,
            "totalAmount": float(doc.total_amount or 0),

            "billingAddress": {
                "line1": doc.billing_address_line_1,
                "line2": doc.billing_address_line_2,
                "postalCode": doc.billing_address_postal_code,
                "city": doc.billing_address_city,
                "state": doc.billing_address_state,
                "country": doc.billing_address_country
            },

            "shippingAddress": {
                "line1": doc.shipping_address_line_1,
                "line2": doc.shipping_address_line_2,
                "postalCode": doc.shipping_address_postal_code,
                "city": doc.shipping_address_city,
                "state": doc.shipping_address_state,
                "country": doc.shipping_address_country
            },

            "paymentInformation": {
                "paymentTerms": doc.payment_terms,
                "paymentMethod": doc.payment_method,
                "bankName": doc.bank_name,
                "accountNumber": doc.account_number,
                "routingNumber": doc.routing_number,
                "swiftCode": doc.swift_code
            },

            "items": formatted_items,

            "terms": {
                "selling": {
                    "general": getattr(terms_doc, "general", ""),
                    "delivery": getattr(terms_doc, "delivery", ""),
                    "cancellation": getattr(terms_doc, "cancellation", ""),
                    "warranty": getattr(terms_doc, "warranty", ""),
                    "liability": getattr(terms_doc, "liability", ""),
                    "payment": {
                        "dueDates": getattr(payment_doc, "duedates", ""),
                        "lateCharges": getattr(payment_doc, "latecharges", ""),
                        "taxes": getattr(payment_doc, "taxes", ""),
                        "notes": getattr(payment_doc, "notes", ""),
                        "phases": phases
                    }
                }
            }
        }

        return send_response(
            status="success",
            message=f"Proforma {proforma_id} fetched successfully",
            data=data,
            status_code=200,
            http_status=200
        )

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Proforma By ID API Error")
        return send_response(
            status="fail",
            message=str(e),
            status_code=500,
            http_status=500
        )
        

@frappe.whitelist(allow_guest=False, methods=["PATCH"])
def update_proforma_status():
    try:
        data = frappe.form_dict

        proforma_id = (data.get("proformaId") or "").strip()
        proforma_status = (data.get("proformaStatus") or "").strip()

        if not proforma_id or not proforma_status:
            return send_response(
                status="fail",
                message="Both 'proformaId' and 'proformaStatus' are required",
                status_code=400
            )
        ALLOWED_PROFORMA_STATUS = {"Draft", "Approved", "Rejected", "Paid", "Cancelled"}
        if proforma_status not in ALLOWED_PROFORMA_STATUS:
            return send_response(
                status="fail",
                message=(
                    f"Invalid proformaStatus '{proforma_status}'. "
                    f"Allowed values: {', '.join(sorted(ALLOWED_PROFORMA_STATUS))}"
                ),
                status_code=400,
                http_status=404,
            )

        if not frappe.db.exists("Proforma", {"id": proforma_id}):
            return send_response(
                status="fail",
                message=f"Proforma '{proforma_id}' not found",
                status_code=404,
                http_status=404
            )
        if not frappe.has_permission("Proforma", "write", {"id": proforma_id}):
            return send_response(
                status="fail",
                message="You do not have permission to update this proforma",
                status_code=403
            )

        frappe.db.set_value(
            "Proforma",
            {"id": proforma_id},
            "invoice_status",
            proforma_status
        )
        frappe.db.commit()

        return send_response(
            status="success",
            message=f"Proforma '{proforma_id}' status updated to '{proforma_status}'",
            status_code=200
        )

    except Exception as e:
        frappe.log_error(
            frappe.get_traceback(),
            "Update Proforma Status API Error"
        )
        return send_response(
            status="fail",
            message=f"Unexpected Error: {str(e)}",
            status_code=500
        )

@frappe.whitelist(allow_guest=False, methods=["DELETE"])
def delete_proforma():
    try:
        proforma_id = (frappe.form_dict.get("proformaId") or "").strip()

        if not proforma_id:
            return send_response(
                status="fail",
                message="'proformaId' is required",
                status_code=400,
                http_status=400,
            )
        doc_name = frappe.db.get_value("Proforma", {"id": proforma_id})
        if not doc_name:
            return send_response(
                status="fail",
                message=f"Proforma '{proforma_id}' not found",
                status_code=404,
                http_status=404
            )

        if not frappe.has_permission("Proforma", "delete", doc_name):
            return send_response(
                status="fail",
                message="You do not have permission to delete this proforma",
                status_code=403,
                http_status=403
            )

        frappe.db.delete("Proforma Item", {"proforma_id": proforma_id})
        frappe.db.delete("Sale Invoice Selling Terms", {"invoiceno": proforma_id})
        frappe.db.delete("Sale Invoice Selling Payment", {"invoiceno": proforma_id})
        frappe.db.delete("Sale Invoice Selling Payment Phases", {"invoiceno": proforma_id})

        doc = frappe.get_doc("Proforma", doc_name)
        doc.delete()
        frappe.db.commit()

        return send_response(
            status="success",
            message=f"Proforma '{proforma_id}' and related documents deleted successfully",
            status_code=200,
            http_status=200,
        )

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Delete Proforma API Error")
        return send_response(
            status="fail",
            message=f"Unexpected Error: {str(e)}",
            status_code=500,
            http_status=500
        )