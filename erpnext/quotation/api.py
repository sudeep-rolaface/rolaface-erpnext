import random
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

    quotation_no = f"QUO-{next_no:04d}"

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
        page_size = args.get("page_size")

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

        if not page_size:
            return send_response(
                status="error",
                message="'pageSize' parameter is required.",
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
                message="'pageSize' must be a positive integer.",
                data=None,
                status_code=400,
                http_status=400
            )

        start_index = (page - 1) * page_size
        end_index = start_index + page_size

        filters = {}
        or_filters = []

        customer = args.get("customer")
        if customer:
            filters["customer_name"] = ["like", f"%{customer}%"]

        id = args.get("id")
        if id:
            filters["name"] = ["like", f"%{id}%"]

        invoice_type = args.get("invoiceType")
        if invoice_type:
            filters["custom_invoice_type"] = ["like", f"%{invoice_type}%"]

        # FIX: currency filter was incorrectly filtering by name instead of currency
        currency = args.get("currency")
        if currency:
            filters["currency"] = ["like", f"%{currency}%"]

        industry = args.get("industryBase")
        if industry:
            filters["custom_industry_bases"] = industry

        from_date = args.get("from_date")
        to_date = args.get("to_date")
        if from_date and to_date:
            filters["transaction_date"] = ["between", [from_date, to_date]]
        elif from_date:
            filters["transaction_date"] = [">=", from_date]
        elif to_date:
            filters["transaction_date"] = ["<=", to_date]

        min_amount = args.get("minAmount")
        max_amount = args.get("maxAmount")

        if min_amount and max_amount:
            filters["grand_total"] = ["between", [float(min_amount), float(max_amount)]]
        elif min_amount:
            filters["grand_total"] = [">=", float(min_amount)]
        elif max_amount:
            filters["grand_total"] = ["<=", float(max_amount)]

        search = args.get("search")
        if search:
            or_filters = [
                ["name", "like", f"%{search}%"],
                ["customer_name", "like", f"%{search}%"],
            ]

            customers = frappe.get_all(
                "Customer",
                filters={"tax_id": ["like", f"%{search}%"]},
                pluck="name"
            )
            if customers:
                or_filters.append(["customer_name", "in", customers])

        allowed_sort_fields = {
            "id": "name",
            "customerName": "customer_name",
            "transactionDate": "transaction_date",
            "validTill": "valid_till",
            "grandTotal": "grand_total",
        }

        sort_by = args.get("sortBy", "transactionDate")
        sort_order = args.get("sortOrder", "desc").lower()

        sort_field = allowed_sort_fields.get(sort_by, "transaction_date")
        sort_order = "asc" if sort_order == "asc" else "desc"

        order_by = f"{sort_field} {sort_order}"

        all_quotations = frappe.get_all(
            "Quotation",
            filters=filters,
            or_filters=or_filters,
            fields=[
                "name",
                "custom_industry_bases",
                "customer_name",
                "custom_invoice_type",
                "transaction_date",
                "valid_till",
                "grand_total",
                "currency"
            ],
            order_by=order_by,
            start=start_index,
            page_length=page_size
        )

        total_quotations = len(
            frappe.get_all(
                "Quotation",
                filters=filters,
                or_filters=or_filters,
                pluck="name"
            )
        )

        if total_quotations == 0:
            return send_response(
                status="success",
                message="No quotations found.",
                data=[],
                status_code=200,
                http_status=200
            )

        paginated_quotations = all_quotations[start_index:end_index]
        total_pages = (total_quotations + page_size - 1) // page_size

        def to_camel_case(quotation):
            customerTpin = frappe.db.get_value(
                "Customer",
                quotation.get("customer_name"),
                "tax_id"
            ) or ""
            return {
                "id": quotation.get("name"),
                "customerName": quotation.get("customer_name"),
                "customerTpin": customerTpin,
                "invoiceType": quotation.get("custom_invoice_type"),
                "transactionDate": quotation.get("transaction_date"),
                "validTill": quotation.get("valid_till"),
                "grandTotal": quotation.get("grand_total"),
                "currency": quotation.get("currency"),
                "industryBases": quotation.get("custom_industry_bases"),
            }

        quotations_camel = [to_camel_case(q) for q in paginated_quotations]

        response_data = {
            "quotations": quotations_camel,
            "pagination": {
                "page": page,
                "pageSize": page_size,
                "total": total_quotations,
                "totalPages": total_pages,
                "hasNext": page < total_pages,
                "hasPrev": page > 1
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
def get_quotation_by_id():
    quotation_id = (frappe.form_dict.get("id") or "").strip()
    if not quotation_id:
        return send_response(
            status="fail",
            message="quotationId is required",
            status_code=400,
            http_status=400
        )

    try:
        quotation = frappe.get_doc("Quotation", quotation_id)
        customer_tpin = frappe.db.get_value(
            "Customer",
            quotation.customer_name,
            "tax_id"
        ) or ""
        billing_address = {
            "line1": quotation.custom_billing_address_line_1,
            "line2": quotation.custom_billing_address_line_2,
            "postalCode": quotation.custom_billing_address_postal_code,
            "city": quotation.custom_billing_address_city,
            "state": quotation.custom_billing_address_state,
            "country": quotation.custom_billing_address_country,
        }
        shipping_address = {
            "line1": quotation.custom_shipping_address_line_1,
            "line2": quotation.custom_shipping_address_line_2,
            "postalCode": quotation.custom_shipping_address_postal_code,
            "city": quotation.custom_shipping_address_city,
            "state": quotation.custom_shipping_address_state,
            "country": quotation.custom_shipping_address_country,
        }
        payment_information = {
            "paymentTerms": quotation.custom_payment_terms,
            "paymentMethod": quotation.custom_payment_method,
            "bankName": quotation.custom_bank_name,
            "accountNumber": quotation.custom_account_number,
            "routingNumber": quotation.custom_routing_number,
            "swiftCode": quotation.custom_swift,
        }
        items = []
        for item in quotation.items:
            items.append({
                "itemCode": item.item_code,
                "itemName": item.item_name,
                "description": item.description,
                "quantity": item.qty,
                "price": item.rate,
                "discount": item.discount_amount,
                # vatCode only shown for ZMW quotations
                "vatCode": item.get("custom_vat_code") if quotation.currency == "ZMW" else None,
            })

        terms_doc = frappe.get_doc("Sale Invoice Selling Terms", {"invoiceno": quotation_id}) \
            if frappe.db.exists("Sale Invoice Selling Terms", {"invoiceno": quotation_id}) else None

        payment_doc = frappe.get_doc("Sale Invoice Selling Payment", {"invoiceno": quotation_id}) \
            if frappe.db.exists("Sale Invoice Selling Payment", {"invoiceno": quotation_id}) else None

        phases = frappe.get_all(
            "Sale Invoice Selling Payment Phases",
            filters={"invoiceno": quotation_id},
            fields=["phase_name as name", "percentage", "condition"]
        ) if frappe.db.exists("Sale Invoice Selling Payment Phases", {"invoiceno": quotation_id}) else []

        terms = {
            "selling": {
                "general": getattr(terms_doc, "general", "") if terms_doc else "",
                "delivery": getattr(terms_doc, "delivery", "") if terms_doc else "",
                "cancellation": getattr(terms_doc, "cancellation", "") if terms_doc else "",
                "warranty": getattr(terms_doc, "warranty", "") if terms_doc else "",
                "liability": getattr(terms_doc, "liability", "") if terms_doc else "",
                "payment": {
                    "dueDates": getattr(payment_doc, "duedates", "") if payment_doc else "",
                    "lateCharges": getattr(payment_doc, "latecharges", "") if payment_doc else "",
                    "taxes": getattr(payment_doc, "taxes", "") if payment_doc else "",
                    "notes": getattr(payment_doc, "notes", "") if payment_doc else "",
                    "phases": phases
                }
            }
        }

        response_data = {
            "id": quotation.name,
            "customerId": quotation.customer_name,
            "customerTpin": customer_tpin,
            "currencyCode": quotation.currency,
            "exchangeRt": str(quotation.conversion_rate),
            "transactionDate": quotation.transaction_date,
            "industryBases": quotation.custom_industry_bases,
            "validUntil": quotation.valid_till,
            "invoiceStatus": quotation.status,
            "invoiceType": quotation.custom_invoice_type,
            "destnCountryCd": quotation.custom_destination_country_code,
            "lpoNumber": quotation.custom_lpo_number,
            "billingAddress": billing_address,
            "shippingAddress": shipping_address,
            "paymentInformation": payment_information,
            "items": items,
            "terms": terms
        }

        return send_response(
            status="success",
            message="Quotation fetched successfully",
            data=response_data,
            status_code=200,
            http_status=200
        )

    except frappe.DoesNotExistError:
        return send_response(
            status="fail",
            message="Quotation not found",
            status_code=404,
            http_status=404
        )

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Quotation API Error")
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
                message=f"Quotation with id {quotation_id} not found",
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
    data = frappe.form_dict
    customer_id = frappe.form_dict.get("customerId")
    currencyCd = frappe.form_dict.get("currencyCode")
    exchangeRt = frappe.form_dict.get("exchangeRt")
    destnCountryCd = frappe.form_dict.get("destnCountryCd")
    lpoNumber = frappe.form_dict.get("lpoNumber")
    invoiceStatus = frappe.form_dict.get("invoiceStatus")
    invoiceType = frappe.form_dict.get("invoiceType")
    validUntil = data.get("validUntil")
    industryBases = data.get("industryBases")

    billingAddress = data.get("billingAddress") or {}
    billingAddressLine1 = billingAddress.get("line1")
    billingAddressLine2 = billingAddress.get("line2")
    billingAddressPostalCode = billingAddress.get("postalCode")
    billingAddressCity = billingAddress.get("city")
    billingAddressState = billingAddress.get("state")
    billingAddressCountry = billingAddress.get("country")

    shippingAddress = data.get("shippingAddress") or {}
    shippingAddressLine1 = shippingAddress.get("line1")
    shippingAddressLine2 = shippingAddress.get("line2")
    shippingAddressPostalCode = shippingAddress.get("postalCode")
    shippingAddressCity = shippingAddress.get("city")
    shippingAddressState = shippingAddress.get("state")
    shippingAddressCountry = shippingAddress.get("country")

    payment_info = data.get("paymentInformation")

    # ── industryBases ──────────────────────────────────────────────────────────
    if not industryBases:
        return send_response(
            status="fail",
            message="Industry Bases is required",
            status_code=400,
            http_status=400
        )

    # ── paymentInformation ─────────────────────────────────────────────────────
    if not payment_info or not isinstance(payment_info, dict):
        return send_response(
            status="error",
            message="paymentInformation is required and must be an object",
            status_code=400,
            http_status=400
        )

    payment_terms = payment_info.get("paymentTerms")
    payment_method = payment_info.get("paymentMethod")
    bank_name = payment_info.get("bankName")
    account_number = payment_info.get("accountNumber")
    routing_number = payment_info.get("routingNumber")
    swift_code = payment_info.get("swiftCode")

    PAYMENT_METHOD_LIST = ["01", "02", "03", "04", "05", "06", "07", "08"]

    if not payment_method:
        return send_response(
            status="fail",
            message="'paymentMethod' is required.",
            status_code=400,
            http_status=400
        )

    if payment_method not in PAYMENT_METHOD_LIST:
        return send_response(
            status="fail",
            message=f"Invalid paymentMethod '{payment_method}'. Allowed values are {PAYMENT_METHOD_LIST}.",
            status_code=400,
            http_status=400
        )

    required_payment_fields = {
        "paymentTerms": payment_terms,
        "paymentMethod": payment_method,
        "bankName": bank_name,
        "accountNumber": account_number,
        "routingNumber": routing_number,
        "swiftCode": swift_code,
    }

    missing_fields = [key for key, value in required_payment_fields.items() if not value]
    if missing_fields:
        return send_response(
            status="error",
            message=f"Missing paymentInformation fields: {', '.join(missing_fields)}",
            status_code=400,
            http_status=400
        )

    # ── terms ──────────────────────────────────────────────────────────────────
    terms = data.get("terms") or {}
    selling = terms.get("selling") or {}

    general = (selling.get("general") or "").strip()
    delivery = (selling.get("delivery") or "").strip()
    cancellation = (selling.get("cancellation") or "").strip()
    warranty = (selling.get("warranty") or "").strip()
    liability = (selling.get("liability") or "").strip()

    payment_terms_data = selling.get("payment") or {}
    dueDates = payment_terms_data.get("dueDates", "")
    lateCharges = payment_terms_data.get("lateCharges", "")
    tax = payment_terms_data.get("taxes", "")
    notes = payment_terms_data.get("notes", "")
    phases = payment_terms_data.get("phases", [])

    # ── validUntil ─────────────────────────────────────────────────────────────
    today_date = getdate(today())

    if not validUntil:
        return send_response(
            status="fail",
            message="validUntil is required",
            data=None,
            status_code=400,
            http_status=400
        )

    due_date = getdate(validUntil)
    if due_date < today_date:
        return send_response(
            status="fail",
            message="Due Date cannot be before today's date",
            data=None,
            status_code=400,
            http_status=400
        )

    # ── customer ───────────────────────────────────────────────────────────────
    if not customer_id:
        return send_response(
            status="fail",
            message="Customer ID is required (customerId)",
            status_code=400,
            http_status=400
        )

    # ── invoiceType ────────────────────────────────────────────────────────────
    if not invoiceType:
        return send_response(
            status="fail",
            message="Missing required field: invoiceType",
            status_code=400,
            http_status=400
        )

    allowedInvoiceType = ZRA_INSTANCE.getTaxCategory()
    if invoiceType not in allowedInvoiceType:
        return send_response(
            status="fail",
            message=f"Invalid invoiceType. Allowed values are: {', '.join(allowedInvoiceType)}",
            status_code=400,
            http_status=400
        )

    # ── invoiceStatus ──────────────────────────────────────────────────────────
    if not invoiceStatus:
        return send_response(
            status="fail",
            message="Invoice status is required (invoiceStatus)",
            status_code=400,
            http_status=400
        )

    allowedInvoiceStatus = ["Draft", "Sent", "Paid", "Overdue"]
    if invoiceStatus not in allowedInvoiceStatus:
        return send_response(
            status="fail",
            message="Invalid invoice status. Allowed values are: Draft, Sent, Paid, Overdue.",
            status_code=400,
            http_status=400
        )

    # ── currency & exchange rate ───────────────────────────────────────────────
    # FIX: use = (assignment), not == (comparison)
    # FIX: default currency comes from ERPNext Global Defaults, not hardcoded ZMW
    if not currencyCd:
        currencyCd = frappe.db.get_single_value("Global Defaults", "default_currency") or "USD"
        exchangeRt = 1.0

    # FIX: dynamically load all enabled currencies from ERPNext — works for any country
    allowedCurrencies = frappe.get_all("Currency", filters={"enabled": 1}, pluck="name")

    if currencyCd not in allowedCurrencies:
        return send_response(
            status="fail",
            message=f"Invalid currency '{currencyCd}'. Please use a valid ISO 4217 currency code.",
            status_code=400,
            http_status=400
        )

    if not exchangeRt:
        return send_response(
            status="fail",
            message="Exchange rate is required and must not be null",
            status_code=400,
            http_status=400
        )

    # ── parse JSON payload for items ───────────────────────────────────────────
    try:
        payload = json.loads(frappe.local.request.get_data().decode("utf-8"))
    except Exception as e:
        return send_response(
            status="fail",
            message=f"Invalid JSON payload: {str(e)}",
            status_code=400,
            http_status=400
        )

    items = payload.get("items", [])

    if not items or not isinstance(items, list):
        return send_response(
            status="fail",
            message="Items must be a non-empty list",
            status_code=400,
            http_status=400
        )

    # ── VAT / tax code validation ──────────────────────────────────────────────
    # FIX: ZRA VAT rules (C1, C2, A) ONLY apply to ZMW currency.
    #      For all other currencies, vatCode is completely optional.
    for i in items:
        vatCd = i.get("vatCode")

        if currencyCd == "ZMW":
            # ZMW: vatCode is REQUIRED and must follow ZRA rules
            ZMW_VAT_LIST = ["A", "C1", "C2"]

            if not vatCd:
                return send_response(
                    status="fail",
                    message="'vatCode' is required for ZMW transactions.",
                    status_code=400,
                    http_status=400
                )

            if vatCd not in ZMW_VAT_LIST:
                return send_response(
                    status="fail",
                    message=f"'vatCode' must be a valid ZRA VAT category: {', '.join(ZMW_VAT_LIST)}. Rejected value: [{vatCd}]",
                    status_code=400,
                    http_status=400
                )

            if vatCd == "C2":
                if not lpoNumber:
                    return send_response(
                        status="fail",
                        message="Local Purchase Order number (lpoNumber) is required for ZMW transactions with vatCode 'C2'.",
                        status_code=400,
                        http_status=400
                    )

            if vatCd == "C1":
                if not destnCountryCd:
                    return send_response(
                        status="fail",
                        message="Destination country (destnCountryCd) is required for ZMW transactions with vatCode 'C1'.",
                        status_code=400,
                        http_status=400
                    )

            if vatCd == "A":
                if lpoNumber or destnCountryCd:
                    return send_response(
                        status="fail",
                        message="For ZMW vatCode 'A', lpoNumber and destnCountryCd must NOT be provided.",
                        status_code=400,
                        http_status=400
                    )

        else:
            # Non-ZMW: vatCode is OPTIONAL — no ZRA-specific rules enforced
            # If provided, we simply store it; if absent, that is also fine
            pass

    # ── fetch customer ─────────────────────────────────────────────────────────
    customer_data = get_customer_details(customer_id)
    if not customer_data or customer_data.get("status") == "fail":
        return customer_data

    quotation_no = generate_Quotation_number()

    # ── create quotation ───────────────────────────────────────────────────────
    try:
        quotation = frappe.get_doc({
            "doctype": "Quotation",
            "name": quotation_no,
            "customer": customer_data.get("name"),
            "customer_name": customer_data.get("customer_name"),
            "currency": currencyCd,
            "conversion_rate": exchangeRt,
            "valid_till": validUntil,
            "custom_destination_country_code": destnCountryCd,
            "custom_lpo_number": lpoNumber,
            "custom_industry_bases": industryBases,
            "custom_billing_address_line_1": billingAddressLine1,
            "custom_billing_address_line_2": billingAddressLine2,
            "custom_billing_address_postal_code": billingAddressPostalCode,
            "custom_billing_address_city": billingAddressCity,
            "custom_billing_address_state": billingAddressState,
            "custom_billing_address_country": billingAddressCountry,
            "custom_shipping_address_line_1": shippingAddressLine1,
            "custom_shipping_address_line_2": shippingAddressLine2,
            "custom_shipping_address_postal_code": shippingAddressPostalCode,
            "custom_shipping_address_city": shippingAddressCity,
            "custom_shipping_address_state": shippingAddressState,
            "custom_shipping_address_country": shippingAddressCountry,
            "custom_payment_method": payment_method,
            "custom_bank_name": bank_name,
            "custom_account_number": account_number,
            "custom_routing_number": routing_number,
            "custom_swift": swift_code,
            "custom_payment_terms": payment_terms,
            "custom_invoice_type": invoiceType,
            "total_qty": 0,
            "grand_total": 0,
            "status": "Draft"
        })

        total_qty = 0
        grand_total = 0

        for item in items:
            qty = float(item.get("quantity", 1))
            rate = float(item.get("price", 0))
            discount = float(item.get("discount", 0))
            item_tax = float(item.get("tax", 0))

            item_total = (qty * rate) - discount + item_tax

            quotation.append("items", {
                "item_code": item.get("itemCode"),
                "item_name": item.get("itemName"),
                "description": item.get("description"),
                "qty": qty,
                "rate": rate,
                "discount_amount": discount,
                "amount": item_total,
                # FIX: vatCode stored for all currencies but only validated for ZMW
                # defaults to empty string if not provided (safe for non-ZMW)
                "custom_vat_code": item.get("vatCode") or ""
            })

            total_qty += qty
            grand_total += item_total

        quotation.total_qty = total_qty
        quotation.grand_total = grand_total

        quotation.insert(ignore_permissions=True)
        frappe.db.commit()

        # ── selling terms ──────────────────────────────────────────────────────
        terms_doc = frappe.get_doc({
            "doctype": "Sale Invoice Selling Terms",
            "invoiceno": quotation_no,
            "general": general,
            "delivery": delivery,
            "cancellation": cancellation,
            "warranty": warranty,
            "liability": liability
        })
        terms_doc.insert()
        frappe.db.commit()

        # ── payment terms ──────────────────────────────────────────────────────
        if payment_terms_data:
            payment_doc = frappe.get_doc({
                "doctype": "Sale Invoice Selling Payment",
                "invoiceno": quotation_no,
                "duedates": dueDates,
                "latecharges": lateCharges,
                "taxes": tax,
                "notes": notes
            })
            payment_doc.insert()
            frappe.db.commit()

        # ── payment phases ─────────────────────────────────────────────────────
        if phases:
            for phase in phases:
                random_id = "{:06d}".format(random.randint(0, 999999))
                phase_doc = frappe.get_doc({
                    "doctype": "Sale Invoice Selling Payment Phases",
                    "id": random_id,
                    "invoiceno": quotation_no,
                    "phase_name": phase.get("name"),
                    "percentage": phase.get("percentage", ""),
                    "condition": phase.get("condition", "")
                })
                phase_doc.insert()
                frappe.db.commit()

        return send_response(
            status="success",
            message="Quotation created successfully",
            status_code=200,
            http_status=200
        )

    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Create Quotation API Error")
        return send_response(
            status="fail",
            message=str(e),
            status_code=500,
            http_status=500
        )


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


@frappe.whitelist(allow_guest=False, methods=["PATCH"])
def update_quotation_status():
    data = frappe.local.form_dict
    quotation_id = data.get("id")
    new_status = data.get("invoiceStatus")

    if not quotation_id:
        return send_response(
            status="fail",
            message="Quotation ID is required",
            status_code=400,
            http_status=400,
        )

    if not new_status:
        return send_response(
            status="fail",
            message="Status is required",
            status_code=400,
            http_status=400,
        )

    allowed_status = ZRA_INSTANCE.AllowedInvoiceStatuses()

    if new_status not in allowed_status:
        return send_response(
            status="fail",
            message=f"Invalid status. Allowed values are: {', '.join(allowed_status)}",
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
            message="Cannot update status of submitted or cancelled Quotation",
            status_code=400,
            http_status=400,
        )

    try:
        frappe.db.sql("""
            UPDATE `tabQuotation`
            SET `status` = %s
            WHERE `name` = %s
        """, (new_status, quotation_id))

        frappe.db.commit()

        return send_response(
            status="success",
            message="Quotation status updated successfully",
            status_code=200,
            http_status=200,
        )

    except Exception as e:
        frappe.db.rollback()
        return send_response(
            status="fail",
            message=str(e),
            status_code=500,
            http_status=500,
        )
