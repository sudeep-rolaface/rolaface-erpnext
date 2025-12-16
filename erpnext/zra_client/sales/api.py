from erpnext.accounts.doctype.sales_invoice.sales_invoice import SalesInvoice
from erpnext.zra_client.generic_api import send_response, send_response_list
from erpnext.zra_client.main import ZRAClient
from erpnext.zra_client.sales.sale_helper import NormaSale
from erpnext.zra_client.sales.credit_note import CreditNoteSale
from erpnext.zra_client.sales.debit_note import DebitNoteSale
from frappe import _
import random
import frappe
import json


CREDIT_NOTE_SALE_INSTANCE = CreditNoteSale()
DEBIT_NOTE_INSTANCE = DebitNoteSale()
NORMAL_SALE_INSTANCE = NormaSale()
ZRA_CLIENT_INSTANCE = ZRAClient()

def ensure_account(account_name, account_type="Expense", company="Izyane"):
    """Create account if it doesn't exist"""
    if not frappe.db.exists("Account", {"account_name": account_name, "company": company}):
        acct = frappe.get_doc({
            "doctype": "Account",
            "account_name": account_name,
            "company": company,
            "account_type": account_type,
            "root_type": "Expense" if account_type=="Expense" else "Income",
            "is_group": 0
        })
        acct.insert(ignore_permissions=True)
        frappe.db.commit()

def ensure_company_accounts(company_name):
    try:
        expense_root = frappe.get_all("Account", filters={
            "root_type": "Expense",
            "company": company_name,
            "is_group": 1
        }, limit=1)

        if not expense_root:
            frappe.throw(f"Expense root account not found for company {company_name}")

        expense_root_name = expense_root[0].name

        round_off_account_name = "Round Off - Izyane - I"
        if not frappe.db.exists("Account", {"account_name": round_off_account_name, "company": company_name}):
            round_off_group = frappe.get_doc({
                "doctype": "Account",
                "account_name": round_off_account_name,
                "company": company_name,
                "parent_account": expense_root_name,
                "account_type": "Round Off", 
                "root_type": "Expense",
                "is_group": 1
            })
            round_off_group.insert(ignore_permissions=True)
            frappe.db.commit()
        else:
            round_off_group = frappe.get_doc("Account", round_off_account_name)

        stock_diff_name = "Stock Difference - Izyane - I"
        if not frappe.db.exists("Account", {"account_name": stock_diff_name, "company": company_name}):
            stock_diff = frappe.get_doc({
                "doctype": "Account",
                "account_name": stock_diff_name,
                "company": company_name,
                "parent_account": round_off_account_name,
                "account_type": "Expense Account",
                "root_type": "Expense",
                "is_group": 0
            })
            stock_diff.insert(ignore_permissions=True)
            frappe.db.commit()
        company = frappe.get_doc("Company", company_name)
        updated = False
        if not company.round_off_account:
            company.round_off_account = round_off_account_name
            updated = True
        if not company.default_expense_account:
            company.default_expense_account = stock_diff_name
            updated = True
        if updated:
            company.save(ignore_permissions=True)
            frappe.db.commit()

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Ensure Company Accounts Error")



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
        frappe.log_error(frappe.get_traceback(), "Get Customer Details API Error")
        return send_response(
            status="fail",
            message=f"Error retrieving customer: {str(e)}",
            status_code=500,
            http_status=500
        )


def get_item_details(item_code):
    if not item_code:
        return send_response(
            status="fail",
            message="Item code is required.",
            status_code=400,
            http_status=400
        )
    
    try:
        item = frappe.get_doc("Item", item_code)
    except frappe.DoesNotExistError:
        return send_response(
            status="fail",
            message="Item not found",
            status_code=404,
            http_status=404
        )
    except Exception as e:
        return send_response(
            status="fail",
            message=f"Cannot proceed: {str(e)}",
            status_code=400,
            http_status=400
        )
    
    itemName = item.item_name
    itemClassCd = getattr(item, "custom_itemclscd", None)
    itemPackingUnitCd = getattr(item, "custom_pkgunitcd", None)
    itemUnitCd = getattr(item, "stock_uom", None)
    itemVatCd = getattr(item, "custom_vatcd", None)
    itemIplCd = getattr(item, "custom_iplcd", None)
    itemTlCd = getattr(item, "custom_tlcd", None)

    return {
        "itemName": itemName,
        "itemClassCd": itemClassCd,
        "itemPackingUnitCd": itemPackingUnitCd,
        "itemUnitCd": itemUnitCd,
        "itemVatCd": itemVatCd,
        "itemIplCd": itemIplCd,
        "itemTlCd": itemTlCd
    }
    
def get_sales_item_codes(sales_invoice_no=None, item_code=None):
    if not sales_invoice_no:
        return send_response(
            status="fail",
            message="Sales Invoice number is required.",
            status_code=400,
            http_status=400
        )

    if not item_code:
        return send_response(
            status="fail",
            message="Item code is required.",
            status_code=400,
            http_status=400
        )

    try:
        invoice = frappe.get_doc("Sales Invoice", sales_invoice_no)
        for item in invoice.items:
            if item.item_code == item_code:
                data = {
                    "vatCd": item.custom_vatcd or "",
                    "iplCd": item.custom_iplcd or "",
                    "tlCd": item.custom_tlcd or ""
                }
                print("**** item codes", data)

                return data

        return send_response(
            status="fail",
            message=f"Item '{item_code}' not found in Sales Invoice '{sales_invoice_no}'.",
            status_code=404,
            http_status=404
        )

    except frappe.DoesNotExistError:
        return send_response(
            status="fail",
            message=f"Sales Invoice '{sales_invoice_no}' does not exist.",
            status_code=404,
            http_status=404
        )

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "get_sales_item_codes Error")

        return send_response(
            status="fail",
            message=f"Unexpected error: {str(e)}",
            status_code=500,
            http_status=500
        )





@frappe.whitelist(allow_guest=False, methods=["POST"])
def create_sales_invoice():
    data = frappe.form_dict
    customer_id = frappe.form_dict.get("customerId")
    isExport = frappe.form_dict.get("isExport")
    isRvatSale = frappe.form_dict.get("isRvatAgent")
    principalId = frappe.form_dict.get("principalId")
    currencyCd = frappe.form_dict.get("currencyCode")
    exchangeRt = frappe.form_dict.get("exchangeRt")
    createBy = frappe.form_dict.get("created_by")
    destnCountryCd = frappe.form_dict.get("destnCountryCd")
    lpoNumber = frappe.form_dict.get("lpoNumber")
    invoiceStatus = frappe.form_dict.get("invoiceStatus")
    invoiceType = frappe.form_dict.get("invoiceType")
    
    billingAddress = data.get("billingAddress")
    billingAddressLine1 = billingAddress.get("line1")
    billingAddressLine2 = billingAddress.get("line2")
    billingAddressPostalCode = billingAddress.get("postalCode")
    billingAddressCity = billingAddress.get("city")
    billingAddressState = billingAddress.get("state")
    billingAddressCountry = billingAddress.get("country")
    
    shippingAddress = data.get("shippingAddress")
    shippingAddressLine1 = shippingAddress.get("line1")
    shippingAddressLine2 = shippingAddress.get("line2")
    shippingAddressPostalCode = shippingAddress.get("postalCode")
    shippingAddressCity = shippingAddress.get("city")
    shippingAddressState = shippingAddress.get("state")
    shippingAddressCountry = shippingAddress.get("country")
    
    payment_info = data.get("paymentInformation")

    if not payment_info or not isinstance(payment_info, dict):
        return send_response(
            status="error",
            message="paymentInformation is required and must be an object",
            status_code=400
        )
    payment_terms = payment_info.get("paymentTerms")
    payment_method = payment_info.get("paymentMethod")
    bank_name = payment_info.get("bankName")
    account_number = payment_info.get("accountNumber")
    routing_number = payment_info.get("routingNumber")
    swift_code = payment_info.get("swiftCode")
    
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


    required_fields = {
        "paymentTerms": payment_terms,
        "paymentMethod": payment_method,
        "bankName": bank_name,
        "accountNumber": account_number,
        "routingNumber": routing_number,
        "swiftCode": swift_code,
    }

    missing_fields = [key for key, value in required_fields.items() if not value]

    if missing_fields:
        return send_response(
            status="error",
            message=f"Missing paymentInformation fields: {', '.join(missing_fields)}",
            status_code=400
        )

            
    allowedInvoiceType = ["Non-Export", "Export", "LPO"]
    
    if not customer_id:
        return send_response(
            status="fail",
            message="Customer ID is required (customerId)",
            status_code=400,
            http_status=400
        )
    

    if not invoiceType:
        return send_response(
            status="fail",
            message="Missing required field: invoiceType",
            status_code=400,
            http_status=400
        )

    if invoiceType not in allowedInvoiceType:
        return send_response(
            status="fail",
            message=f"Invalid custom_invoice_type. Allowed values are: {', '.join(allowedInvoiceType)}",
            status_code=400,
            http_status=400
        )

    if not invoiceStatus:
        send_response(
            status="fail",
            message="Invoice status is required(invoiceStatus)",
            status_code=400,
            http_status=400
        )
        return
    allowedInvoiceStatus = ["Draft", "Sent", "Paid", "Overdue"]

    if invoiceStatus not in allowedInvoiceStatus:
        send_response(
            status="fail",
            message="Invalid invoice status. Allowed values are: Draft, Sent, Paid, Overdue.",
            status_code=400,
            http_status=400
        )
        return

    if not currencyCd:
        currencyCd == "ZMW"
        exchangeRt == 1

    allowedCurrencies = ["ZMW", "USD", "ZRA", "GBP", "CNY", "EUR"]

    if currencyCd not in allowedCurrencies:
        send_response(
            status="fail",
            message=f"Invalid currency. Allowed currencies are: {', '.join(allowedCurrencies)}",
            status_code=400,
            http_status=400
        )
        return

    if not exchangeRt:
        send_response(
            status="fail",
            message="Exchange rate must not be null",
            status_code=400,
            http_status=400
        )
        
        return

    try:
        payload = json.loads(frappe.local.request.get_data().decode("utf-8"))
    except Exception as e:
        return send_response(
            status="fail",
            message=f"Invalid JSON payload: {str(e)}",
            status_code=400
        )
    items = payload.get("items", [])

    if not items or not isinstance(items, list):
        return send_response(
            status="fail",
            message="Items must be a non-empty list",
            status_code=400,
            http_status=400
        )

    customer_data = get_customer_details(customer_id)
    if not customer_data or customer_data.get("status") == "fail":
        return customer_data


    invoice_items = []
    sale_payload_items = []

    for item in items:
        item_code = item.get("itemCode")
        qty = item.get("quantity", 1)
        rate = item.get("price")
        vatCd = item.get("vatCode")
        iplCd = item.get("iplCd")
        tlCd = item.get("tlCd")
        discount = float(item.get("discount", 0))
        description = item.get("description")
        validatedDiscount = discount if discount else 0
        if not description:
            send_response(
                status="fail",
                message="Item description is required",
                status_code=400,
                http_status=400
            )
            return
        
        VAT_LIST = ["A", "B", "C1", "C2", "C3", "D", "E", "RVAT"]

        if vatCd not in VAT_LIST:
            send_response(
                status="fail",
                message=f"'vatCatCd' must be a valid VAT tax category: {', '.join(VAT_LIST)}. Rejected value: [{vatCd}]",
                status_code=400,
                http_status=400
            )
            return
        
        checkStockResponse, checkStockStatusCode = (
            ZRA_CLIENT_INSTANCE.check_stock(item_code, qty)
        )

        if checkStockStatusCode != 200:
            return send_response(
                status=checkStockResponse["status"],
                message=checkStockResponse["message"],
                data=checkStockResponse.get("data"),
                status_code=checkStockStatusCode,
                http_status=checkStockStatusCode
            )
    

        if vatCd == "C2":
            if lpoNumber is None:
                send_response(
                    status="fail",
                    message="Local Purchase Order number (LPO) is required for transactions with VatCd 'C2' and cannot be null.",
                    status_code=400,
                    http_status=400
                )
                return
        if vatCd == "C1":
            if destnCountryCd is None:
                send_response(
                    status="fail",
                    message="Destination country (destnCountryCd) is required for VatCd 'C1' transactions. ",
                    status_code=400,
                    http_status=400
                )
                return

        if not item_code:
            return send_response(
                status="fail",
                message="Item code is required for each item",
                status_code=400
            )

        item_details = get_item_details(item_code)
        if not item_details:
            return send_response(
                status="fail",
                message=f"Item '{item_code}' does not exist",
                status_code=404
            )

        try:
            qty = float(qty)
            rate = float(rate)
        except ValueError:
            return send_response(
                status="fail",
                message="Quantity and Rate must be numeric",
                status_code=400
            )

        invoice_items.append({
            "item_code": item_code,
            "item_name": item_details.get("itemName"),
            "warehouse": "Finished Goods - Izyane",
            "qty": qty,
            "rate": rate,
            "discount_amount": validatedDiscount,
            "custom_vatcd": vatCd,
            "custom_iplcd": iplCd,
            "custom_tlcd":tlCd,
            "description": description,
            "expense_account": "Stock Difference - Izyane - I",
        
        })
    
        sale_payload_items.append({
            "itemCode": item_code,
            "itemName": item_details.get("itemName"),
            "qty": qty,
            "itemClassCode": item_details.get("itemClassCd"),
            "product_type": item.get("product_type", "Finished Goods"),
            "packageUnitCode": item_details.get("itemPackingUnitCd"),
            "price": rate,
            "VatCd": vatCd,
            "unitOfMeasure": item_details.get("itemUnitCd"),
            "IplCd": iplCd,
            "TlCd": tlCd,
            "discountRate": validatedDiscount
            
        })

    new_invoice_name = SalesInvoice.get_next_invoice_name()
    sale_payload = {
        "name": new_invoice_name,
        "customerName": customer_data.get("customer_name"),
        "customer_tpin": customer_data.get("custom_customer_tpin"),
        "destnCountryCd": destnCountryCd,
        "lpoNumber": lpoNumber,
        "isExport": isExport,
        "isRvatAgent": isRvatSale,
        "principalId": principalId,
        "currencyCd": currencyCd,
        "exchangeRt": exchangeRt,
        "created_by": createBy,
        "items": sale_payload_items
    }
    

    result = NORMAL_SALE_INSTANCE.send_sale_data(sale_payload)
    additional_info = result.get("additionalInfo") or []
    if additional_info and len(additional_info) >= 3:
        currency = additional_info[0]
        exchange_rate = additional_info[1]
        total_tax = additional_info[2]
    else:
        currency = None
        exchange_rate = None
        total_tax = None

    zra_items = result.get("additionInfoToBeSavedItem") or []
    if zra_items:
        zra_lookup = {item["itemCd"]: item["vatTaxblAmt"] for item in zra_items}
        for inv_item in invoice_items:
            item_code = inv_item.get("item_code")
            if item_code in zra_lookup:
                inv_item["custom_vattaxblamt"] = zra_lookup[item_code]
                
    if result.get("resultCd") != "000":
        return send_response(
            status="fail",
            message=result.get("resultMsg", "Unknown error from ZRA"),
            status_code=400,
            http_status=400
        )
    canUpdateInvoice = all(ZRA_CLIENT_INSTANCE.canItemStockBeUpdate(item.get("item_code")) for item in items)
    try:
        doc = frappe.get_doc({
            "doctype": "Sales Invoice",
            "name": new_invoice_name,
            "custom_invoice_type": invoiceType,
            "custom_exchange_rate": exchange_rate,
            "custom_total_tax_amount": total_tax,
            "custom_zra_currency": currency,
            "custom_invoice_status": invoiceStatus,
            "custom_billing_address_line_1": billingAddressLine1,
            "custom_billing_address_line_2": billingAddressLine2,
            "custom_billing_address_postal_code": billingAddressPostalCode,
            "custom_billing_address_city":  billingAddressCity,
            "custom_billing_address_state": billingAddressState,
            "custom_billing_address_country": billingAddressCountry,
            "custom_shipping_address_line1": shippingAddressLine1,
            "custom_shipping_address_line2": shippingAddressLine2,
            "custom_shipping_address_postal_code": shippingAddressPostalCode, 
            "custom_shipping_address_city": shippingAddressCity, 
            "custom_shipping_address_state": shippingAddressState, 
            "custom_shipping_address_country": shippingAddressCountry,
            "custom_payment_terms": payment_terms,
            "custom_payment_method": payment_method,
            "custom_bank_name": bank_name,
            "custom_account_number": account_number,
            "custom_routing_number": routing_number,
            "custom_swift": swift_code,
            "customer": customer_data.get("name"),
            "update_stock": 1 if canUpdateInvoice else 0,
            "items": invoice_items
        })
        doc.insert(ignore_permissions=True)
        doc.submit()
        frappe.db.commit()
        
        terms_doc = frappe.get_doc({
            "doctype": "Sale Invoice Selling Terms",
            "invoiceno": new_invoice_name,
            "general": general,
            "delivery": delivery,
            "cancellation": cancellation,
            "warranty": warranty,
            "liability": liability
        })
        terms_doc.insert()
        frappe.db.commit()
        
        if payment_terms_data:
            payment_doc = frappe.get_doc({
                "doctype": "Sale Invoice Selling Payment",
                "invoiceno": new_invoice_name,
                "duedates": dueDates,     
                "latecharges": lateCharges, 
                "taxes": tax,
                "notes": notes
            })
            payment_doc.insert()
            frappe.db.commit()
        if phases:
            for phase in phases:
                
                random_id = "{:06d}".format(random.randint(0, 999999)) 
                phase_doc = frappe.get_doc({
                    "doctype": "Sale Invoice Selling Payment Phases",
                    "id": random_id,
                    "invoiceno": new_invoice_name, 
                    "phase_name": phase.get("name"),
                    "percentage": phase.get("percentage", ""),
                    "condition": phase.get("condition", "")
                })
                phase_doc.insert()
                frappe.db.commit()

        return send_response(
            status="success",
            message="Sales Invoice created successfully",
            status_code=200
        )
    except frappe.DuplicateEntryError as de:
        frappe.db.rollback()
        return send_response(
            status="fail",
            message=f"Duplicate Entry Error: {str(de)}",
            status_code=409
        )
    except frappe.ValidationError as ve:
        frappe.db.rollback()
        return send_response(
            status="fail",
            message=f"Validation Error: {str(ve)}",
            status_code=400
        )
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Create Sales Invoice API Error")
        frappe.db.rollback()
        return send_response(
            status="fail",
            message=f"Unexpected Error: {str(e)}",
            status_code=500
        )




@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_sales_invoice():
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

        # -------- Validate Page Size --------
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
        all_invoices = frappe.get_all(
            "Sales Invoice",
            fields=[
                "name",
                "customer",
                "custom_invoice_type",
                "custom_rcptno",
                "custom_zra_currency",
                "custom_exchange_rate",
                "posting_date",
                "grand_total",
                "custom_total_tax_amount",
                "custom_invoice_status",
                "is_return",
                "is_debit_note",
                "outstanding_amount",
            ],
            order_by="creation desc"
        )

        total_invoices = len(all_invoices)

        if total_invoices == 0:
            return send_response(
                status="success",
                message="No sales invoices found.",
                data=[],
                status_code=200,
                http_status=200
            )

        invoices = all_invoices[start:end]
        formatted_invoices = []

        for inv in invoices:
            if inv.is_return == 1:
                invoice_type = "Credit Note"
            elif inv.is_debit_note == 1:
                invoice_type = "Debit Note"
            elif inv.grand_total < 0 or inv.outstanding_amount < 0:
                invoice_type = "Debit Note"
            else:
                invoice_type = "Normal"

            formatted_invoices.append({
                "invoiceNumber": inv.name,
                "customerName": inv.customer,
                "receiptNumber": inv.custom_rcptno,
                "currency": inv.custom_zra_currency,
                "exchangeRate": inv.custom_exchange_rate,
                "Date": str(inv.posting_date),
                "Total": float(inv.grand_total),
                "totalTax": inv.custom_total_tax_amount,
                "custom_invoice_status": inv.custom_invoice_status,
                "invoiceTypeParent": invoice_type,
                "custom_invoice_type": inv.custom_invoice_type
            })

        total_pages = (total_invoices + page_size - 1) // page_size

        response_data = {
            "success": True,
            "message": "Sales invoices retrieved successfully",
            "data": formatted_invoices,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total_invoices,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1
            }
        }

        return send_response_list(
            status="success",
            message="Sales invoices retrieved successfully",
            status_code=200,
            http_status=200,
            data=response_data
        )

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get All Sales Invoices API Error")
        return send_response(
            status="fail",
            message=str(e),
            data=None,
            status_code=500,
            http_status=500
        )



@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_sales_invoice_by_id():
    invoice_name = (frappe.form_dict.get("id") or "").strip()

    if not invoice_name:
        return send_response(
            status="fail",
            message="Invoice id is required",
            status_code=400,
            http_status=400
        )
    if not frappe.db.exists("Sales Invoice", invoice_name):
        return send_response(
            status="fail",
            message=f"Invoice {invoice_name} not found",
            status_code=404,
            http_status=404
        )

    try:
        doc = frappe.get_doc("Sales Invoice", invoice_name)

        if doc.is_return == 1:
            invoice_type = "Credit Note"
        elif getattr(doc, "is_debit_note", 0) == 1:
            invoice_type = "Debit Note"
        elif doc.grand_total < 0 or doc.outstanding_amount < 0:
            invoice_type = "Debit Note"
        else:
            invoice_type = "Normal"
        items_data = []
        total_item_discount = 0
        for i in doc.items:
            
            itemInfo = get_item_details(i.item_code)
            itemClassficationCode = itemInfo.get("itemClassCd")
            items_data.append({
                "itemCode": i.item_code,
                "itemClassCode": itemClassficationCode,
                "itemName": i.item_name,
                "qty": i.qty,
                "price": i.rate,
                "discount": total_item_discount,
                "amount": i.amount,
                "vatCode": i.custom_vatcd,
                "iplCode": i.custom_iplcd,
                "tlCode": i.custom_tlcd,
                "vatTaxableAmount": i.custom_vattaxblamt,
                "description": i.description
            })
            
            total_item_discount += i.discount_amount
            
        data = {
            "invoiceNumber": doc.name,
            "custom_invoice_type": doc.custom_invoice_type,
            "receiptNumber": doc.custom_rcptno,
            "customerName": doc.customer,
            "postingDate": str(doc.posting_date),
            "Total": doc.grand_total,
            "totalTax": doc.custom_total_tax_amount,
            # "status": doc.status,
            # "invoiceType": invoice_type,
            "Receipt": doc.custom_receipt,
            "custom_invoice_status": doc.custom_invoice_status,
            "custom_terms_and_conditions": doc.custom_terms_and_conditions,
            "custom_billing_address_line_1": doc.custom_billing_address_line_1,
            "custom_billing_address_line_2": doc.custom_billing_address_line_2,
            "custom_billing_address_postal_code": doc.custom_billing_address_postal_code,
            "custom_billing_address_city": doc.custom_billing_address_city,
            "custom_billing_address_state": doc.custom_billing_address_state,
            "custom_billing_address_country": doc.custom_billing_address_country,
            "custom_payment_terms": doc.custom_payment_terms,
            "custom_payment_method": doc.custom_payment_method,
            "custom_bank_name": doc.custom_bank_name,
            "custom_account_number": doc.custom_account_number,
            "custom_routing_number": doc.custom_routing_number,
            "custom_swift": doc.custom_swift,
            "items": items_data
        }

        return send_response(
            status="success",
            message=f"Invoice {invoice_name} fetched successfully",
            status_code=200,
            http_status=200,
            data=data
        )

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Sales Invoice API Error")
        return send_response(
            status="fail",
            message=str(e),
            status_code=500,
            http_status=500
        )




@frappe.whitelist(allow_guest=False, methods=["DELETE"])
def delete_sales_invoice():
    invoice_name = (frappe.form_dict.get("id") or "").strip()

    if not invoice_name:
        return send_response(
            status="fail",
            message="Invoice id is required to delete (id)",
            status_code=400,
            http_status=400
        )

    try:
        doc = frappe.get_doc("Sales Invoice", invoice_name)
        if doc.docstatus != 0:
            return send_response(
                status="fail",
                message="Only Draft invoices can be deleted",
                status_code=400,
                http_status=400
            )
        doc.delete()
        frappe.db.commit()

        return send_response(
            status="success",
            message=f"Invoice {invoice_name} deleted successfully",
            status_code=200,
            http_status=200
        )

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Delete Sales Invoice API Error")
        return send_response(
            status="fail",
            message=str(e),
            status_code=500,
            http_status=500
        )

@frappe.whitelist(allow_guest=False, methods=["POST"])
def create_credit_note_from_invoice():
    data = frappe.local.request.get_data().decode("utf-8")
    try:
        data = json.loads(data)
    except Exception:
        return send_response(status="fail", message="Invalid JSON data", status_code=400, http_status=400)

    sales_invoice_no = data.get("sales_invoice_no")
    items_qty = data.get("items", [])

    if not sales_invoice_no:
        return send_response(status="fail", message="Sales Invoice number is required", status_code=400, http_status=400)

    if not isinstance(items_qty, list):
        return send_response(status="fail", message="Items must be provided as a list", status_code=400, http_status=400)

    if not frappe.db.exists("Sales Invoice", sales_invoice_no):
        return send_response(status="fail", message=f"Sales Invoice '{sales_invoice_no}' not found", status_code=404, http_status=404)

    sales_invoice = frappe.get_doc("Sales Invoice", sales_invoice_no)
    customer_doc = frappe.get_doc("Customer", sales_invoice.customer)
    customer_data = get_customer_details(customer_doc.custom_id)
    if not customer_data or customer_data.get("status") == "fail":
        return customer_data

    credit_items = []
    sale_payload_items = []

    for item in sales_invoice.items:
        qty_entry = next((i for i in items_qty if i.get("item_code") == item.item_code), None)
        if not qty_entry:
            continue

        qty = qty_entry.get("qty", item.qty)
        if qty <= 0:
            continue
        item_code = item.item_code
        if not item_code:
            return send_response(
                status="fail",
                message="Item code is required for each item",
                status_code=400
            )
            
        item_details = get_item_details(item_code)
        if not item_details:
            return send_response(
                status="fail",
                message=f"Item '{item_code}' does not exist",
                status_code=404
            )

        qty = float(qty)
        rate = float(qty_entry.get("price", item.rate))  
        item_codes = get_sales_item_codes(sales_invoice_no, item_code)
        credit_items.append({
            "item_code": item.item_code,
            "item_name": item.item_name,
            "vatCd": item_codes["vatCd"],
            "iplCd": item_codes["iplCd"],
            "tlCd": item_codes["tlCd"],
            "qty": -abs(qty),
            "rate": rate,
            "custom_vatcd": item_codes["vatCd"],
            "custom_iplcd": item_codes["iplCd"],
            "custom_tlcd": item_codes["tlCd"],
            "warehouse": "Finished Goods - Izyane",
            "expense_account": "Stock Difference - Izyane - I",
        })

        item_details = get_item_details(item.item_code)
        
        sale_payload_items.append({
            "itemCode": item.item_code,
            "itemName": item.item_name,
            "qty": qty,
            "itemClassCode": item_details.get("itemClassCd"),
            "product_type": getattr(item, "product_type", "Finished Goods"),
            "packageUnitCode": item_details.get("itemPackingUnitCd"),
            "price": rate,
            "unitOfMeasure": item_details.get("itemUnitCd"),
            "VatCd": item_codes["vatCd"],
            "IplCd": item_codes["iplCd"],
            "TlCd": item_codes["tlCd"],
        })

    if not credit_items:
        return send_response(status="fail", message="No valid items to create Credit Note", status_code=400, http_status=400)

    new_invoice_name = SalesInvoice.get_next_invoice_name()
    sale_payload = {
        "originalInvoice": sales_invoice_no,
        "name": new_invoice_name,
        "customerName": customer_data.get("customer_name"),
        "customer_tpin": customer_data.get("custom_customer_tpin"),
        "isExport": False,
        "isRvatAgent": False,
        "items": sale_payload_items
    }
    print("Credit Note Payload: ", sale_payload)
    print("**** end of credit payload ****")
    result = CREDIT_NOTE_SALE_INSTANCE.send_sale_data(sale_payload)
    if result.get("resultCd") != "000":
        return send_response(status="fail", message=result.get("resultMsg", "Unknown error from ZRA"), status_code=400, http_status=400)

    additional_info = result["additionalInfo"]
    currency = additional_info[0]
    exchange_rate = additional_info[1]
    total_tax = additional_info[2]
    zra_items = result.get("additionInfoToBeSavedItem", [])
    zra_lookup = { item["itemCd"]: item["vatTaxblAmt"] for item in zra_items }
    for inv_item in credit_items:
        item_code = inv_item.get("item_code")
        if item_code in zra_lookup:
            inv_item["custom_vattaxblamt"] = zra_lookup[item_code]
            
    canUpdateInvoice = all(
        ZRA_CLIENT_INSTANCE.canItemStockBeUpdate(item.get("item_code")) 
        for item in credit_items
    )

    credit_note = frappe.get_doc({
        "doctype": "Sales Invoice",
        "customer": sales_invoice.customer,
        "company": sales_invoice.company,
        "custom_exchange_rate": exchange_rate,
        "custom_total_tax_amount": total_tax,
        "custom_zra_currency": currency,
        "is_return": 1,
        "return_against": sales_invoice.name,
        "items": credit_items,
        "posting_date": frappe.utils.today(),
        "update_stock": 1 if canUpdateInvoice else 0,
        "title": f"Credit for {sales_invoice_no}"
    })
    credit_note.insert(ignore_permissions=True)
    credit_note.submit()
    frappe.db.commit()

    return send_response(
        status="success",
        message=f"Credit Note '{credit_note.name}' created for {sales_invoice_no}",
        data={"credit_note_no": credit_note.name},
        status_code=201,
        http_status=201
    )

@frappe.whitelist(allow_guest=False, methods=["POST"])
def create_debit_note_from_invoice():
    try:
        payload = json.loads(frappe.local.request.get_data().decode("utf-8"))
    except Exception as e:
        return send_response(
            status="fail",
            message=f"Invalid JSON payload: {str(e)}",
            status_code=400
        )

    sales_invoice_no = payload.get("sales_invoice_no")
    req_items = payload.get("items", [])

    if not sales_invoice_no:
        return send_response(status="fail", message="Sales Invoice number is required", status_code=400)

    if not isinstance(req_items, list) or not req_items:
        return send_response(status="fail", message="Items must be a non-empty list", status_code=400)

    if not frappe.db.exists("Sales Invoice", sales_invoice_no):
        return send_response(status="fail", message=f"Sales Invoice '{sales_invoice_no}' not found", status_code=404)

    sales_invoice = frappe.get_doc("Sales Invoice", sales_invoice_no)
    customer_doc = frappe.get_doc("Customer", sales_invoice.customer)
    customer_data = get_customer_details(customer_doc.custom_id)

    if not customer_data or customer_data.get("status") == "fail":
        return customer_data

    debit_items = []
    sale_payload_items = []

    for inv_item in sales_invoice.items:
        req_item = next((i for i in req_items if i.get("item_code") == inv_item.item_code), None)
        if not req_item:
            continue

        qty = float(req_item.get("qty", inv_item.qty))
        if qty <= 0:
            continue
        item_code = inv_item.item_code
        item_codes = get_sales_item_codes(sales_invoice_no, item_code)
        
        rate = float(req_item.get("price", inv_item.rate))
        vatCd = item_codes["vatCd"]
        iplCd =  item_codes["iplCd"]
        tlCd = item_codes["tlCd"]

        if vatCd == "C2" and not payload.get("lpoNumber"):
            return send_response(status="fail", message="LPO number is required for VatCd 'C2'", status_code=400)

        if vatCd == "C" and not payload.get("destnCountryCd"):
            return send_response(status="fail", message="Destination country is required for VatCd 'C'", status_code=400)

        item_details = get_item_details(inv_item.item_code)
        if not item_details:
            return send_response(
                status="fail",
                message=f"Item '{inv_item.item_code}' does not exist",
                status_code=404
            )

        debit_items.append({
            "item_code": inv_item.item_code,
            "item_name": inv_item.item_name,
            "qty": qty,
            "rate": rate,
            "vatCd": vatCd,
            "iplCd": iplCd,
            "tlCd": tlCd,
            "custom_vatcd": vatCd,
            "custom_iplcd": iplCd,
            "custom_tlcd": tlCd,
            "warehouse": "Finished Goods - Izyane",
            "expense_account": "Stock Difference - Izyane - I",
        })
        sale_payload_items.append({
            "itemCode": inv_item.item_code,
            "itemName": inv_item.item_name,
            "qty": qty,
            "itemClassCode": item_details.get("itemClassCd"),
            "product_type": getattr(inv_item, "product_type", "Finished Goods"),
            "packageUnitCode": item_details.get("itemPackingUnitCd"),
            "unitOfMeasure": item_details.get("itemUnitCd"),
            "price": rate,
            "VatCd": vatCd,
            "IplCd": iplCd,
            "TlCd": tlCd
        })

    if not debit_items:
        return send_response(
            status="fail",
            message="No valid items to create Debit Note",
            status_code=400
        )
    new_invoice_name = SalesInvoice.get_next_invoice_name()
    sale_payload = {
        "name": new_invoice_name,
        "originInvoice": sales_invoice,
        "customerName": customer_data.get("customer_name"),
        "customer_tpin": customer_data.get("custom_customer_tpin"),
        "isExport": payload.get("isExport", False),
        "isRvatAgent": payload.get("isRvatAgent", False),
        "items": sale_payload_items
    }

    print("DEBIT PAYLOAD:", sale_payload)
    result = DEBIT_NOTE_INSTANCE.send_sale_data(sale_payload)
    if result.get("resultCd") != "000":
        return send_response(
            status="fail",
            message=result.get("resultMsg", "Unknown error from ZRA"),
            status_code=400
        )
    
    canUpdateInvoice = all(
        ZRA_CLIENT_INSTANCE.canItemStockBeUpdate(item.get("item_code")) 
        for item in debit_items
    )
    additional_info = result["additionalInfo"]
    currency = additional_info[0]
    exchange_rate = additional_info[1]
    total_tax = additional_info[2]
    zra_items = result.get("additionInfoToBeSavedItem", [])
    zra_lookup = { item["itemCd"]: item["vatTaxblAmt"] for item in zra_items }
    for inv_item in debit_items:
        item_code = inv_item.get("item_code")
        if item_code in zra_lookup:
            inv_item["custom_vattaxblamt"] = zra_lookup[item_code]
    try:
        debit_note_doc = frappe.get_doc({
            "doctype": "Sales Invoice",
            "customer": sales_invoice.customer,
            "company": sales_invoice.company,
            "custom_exchange_rate": exchange_rate,
            "custom_total_tax_amount": total_tax,
            "custom_zra_currency": currency,
            "is_debit_note": 1,
            "return_against": sales_invoice.name,
            "items": debit_items,
            "posting_date": frappe.utils.today(),
            "update_stock": 1 if canUpdateInvoice else 0,
            "title": f"Debit for {sales_invoice_no}"
        })
        debit_note_doc.insert(ignore_permissions=True)
        debit_note_doc.submit()
        frappe.db.commit()

        return send_response(
            status="success",
            message=f"Debit Note '{debit_note_doc.name}' created for {sales_invoice_no}",
            data={"debit_note_no": debit_note_doc.name},
            status_code=201,
            http_status=201
        )
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Create Debit Note API Error")
        frappe.db.rollback()
        return send_response(status="fail", message=f"Unexpected Error: {str(e)}", status_code=500)
