from erpnext.accounts.doctype.sales_invoice.sales_invoice import SalesInvoice
from erpnext.zra_client.generic_api import send_response, send_response_list
from erpnext.zra_client.main import ZRAClient
from erpnext.zra_client.sales.sale_helper import NormaSale
from erpnext.zra_client.sales.credit_note import CreditNoteSale
from erpnext.zra_client.sales.debit_note import DebitNoteSale
from frappe.utils import today, getdate
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
    currencyCd = frappe.form_dict.get("currencyCode")
    exchangeRt = frappe.form_dict.get("exchangeRt")
    createBy = frappe.form_dict.get("created_by")
    destnCountryCd = frappe.form_dict.get("destnCountryCd")
    lpoNumber = frappe.form_dict.get("lpoNumber")
    invoiceStatus = frappe.form_dict.get("invoiceStatus")
    invoiceType = frappe.form_dict.get("invoiceType")
    dueDate = data.get("dueDate")
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
    
    today_date = getdate(today())
    
    due_date_str = data.get("dueDate")
    if not due_date_str:
        return send_response(
            status="fail",
            message="dueDate is required",
            data=None,
            status_code=400,
            http_status=400
        )

    due_date = getdate(due_date_str)
    if due_date < today_date:
        return send_response(
            status="fail",
            message="Due Date cannot be before today's date",
            data=None,
            status_code=400,
            http_status=400
        )

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
        
        VAT_LIST = ["A", "C1", "C2"]

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
            
        ALLOWED_VAT_CODES = ["A", "C1", "C2"]
        if vatCd not in ALLOWED_VAT_CODES:
            return send_response(
                status="fail",
                message=f"Invalid VatCd '{vatCd}'. Allowed values are A, C1, C2.",
                status_code=400,
                http_status=400
            )
            

        if vatCd == "C2":
            if not lpoNumber:
                send_response(
                    status="fail",
                    message="Local Purchase Order number (LPO) is required for transactions with VatCd 'C2' and cannot be null.",
                    status_code=400,
                    http_status=400
                )
                return
        if vatCd == "C1":
            if not destnCountryCd:
                send_response(
                    status="fail",
                    message="Destination country (destnCountryCd) is required for VatCd 'C1' transactions. ",
                    status_code=400,
                    http_status=400
                )
                return
            
        if vatCd == "A":
            if lpoNumber or destnCountryCd:
                return send_response(
                    status="fail",
                    message="For VatCd 'A', lpoNumber and destnCountryCd must NOT be provided.",
                    status_code=400,
                    http_status=400
                )

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
        "PaymentMethod": payment_method,
        "lpoNumber": lpoNumber,
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
            "due_date": dueDate,
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
            "custom_export_destination_country": destnCountryCd,
            "custom_local_purchase_order_number": lpoNumber,
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
                "due_date",
                "grand_total",
                "custom_total_tax_amount",
                "custom_invoice_status",
                "is_return",
                "is_debit_note",
                "return_against",
                "amended_from",
                "outstanding_amount",
            ],
            order_by="creation desc",
            limit_start=start,
            limit_page_length=page_size
        )

        total_invoices = frappe.db.count("Sales Invoice")

        if total_invoices == 0:
            return send_response(
                status="success",
                message="No sales invoices found.",
                data=[],
                status_code=200,
                http_status=200
            )

        formatted_invoices = []

        for inv in all_invoices:
            invoice_type_parent = "Normal"
            invoice_type = inv.custom_invoice_type

            if inv.is_return == 1 and inv.return_against:
                parent_invoice_type = frappe.db.get_value(
                    "Sales Invoice",
                    inv.return_against,
                    "custom_invoice_type"
                )
                invoice_type_parent = "Credit Note"
                invoice_type = parent_invoice_type

            elif inv.is_debit_note == 1 and inv.amended_from:
                parent_invoice_type = frappe.db.get_value(
                    "Sales Invoice",
                    inv.amended_from,
                    "custom_invoice_type"
                )
                invoice_type_parent = "Debit Note"
                invoice_type = parent_invoice_type

            formatted_invoices.append({
                "invoiceNumber": inv.name,
                "customerName": inv.customer,
                "receiptNumber": inv.custom_rcptno,
                "currency": inv.custom_zra_currency,
                "exchangeRate": inv.custom_exchange_rate,
                "dateOfInvoice": str(inv.posting_date),
                "dueDate": inv.due_date,
                "totalAmount": float(inv.grand_total),
                "totalTax": inv.custom_total_tax_amount,
                "invoiceStatus": inv.custom_invoice_status,
                "outstandingAmount": inv.outstanding_amount,
                "invoiceTypeParent": invoice_type_parent,
                "invoiceType": invoice_type
            })

        total_pages = (total_invoices + page_size - 1) // page_size

        response_data = {
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
        frappe.log_error(frappe.get_traceback(), "Get Sales Invoices API Error")
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
        if getattr(doc, "is_debit_note", 0) == 1:
            invoice_type = "Debit Note"
        elif getattr(doc, "is_return", 0) == 1:
            invoice_type = "Return Invoice"
        else:
            invoice_type = "Normal Invoice"

        parent_invoice_name = getattr(doc, "return_against", None) or invoice_name
        parent_doc = frappe.get_doc("Sales Invoice", parent_invoice_name)
        current_invoice = frappe.get_doc("Sales Invoice", parent_invoice_name)

        terms_doc = frappe.get_doc("Sale Invoice Selling Terms", {"invoiceno": parent_invoice_name}) \
            if frappe.db.exists("Sale Invoice Selling Terms", {"invoiceno": parent_invoice_name}) else None

        payment_doc = frappe.get_doc("Sale Invoice Selling Payment", {"invoiceno": parent_invoice_name}) \
            if frappe.db.exists("Sale Invoice Selling Payment", {"invoiceno": parent_invoice_name}) else None

        phases = frappe.get_all(
            "Sale Invoice Selling Payment Phases",
            filters={"invoiceno": parent_invoice_name},
            fields=["phase_name as name", "percentage", "condition"]
        ) if frappe.db.exists("Sale Invoice Selling Payment Phases", {"invoiceno": parent_invoice_name}) else []

        items_data = []
        for i in doc.items:
            items_data.append({
                "itemCode": i.item_code,
                "quantity": i.qty,
                "description": i.description,
                "discount": i.discount_amount,
                "price": i.rate,
                "vatCode": i.custom_vatcd,
                "vatTaxableAmount": i.custom_vattaxblamt,
            })
        def get_address(field_prefix):
            return {
                "line1":getattr(parent_doc, "custom_billing_address_line_1", ""),
                "line2": getattr(parent_doc, "custom_billing_address_line_2", ""),
                "postalCode": getattr(doc, f"{field_prefix}_postal_code", None) or getattr(parent_doc, f"{field_prefix}_postal_code", ""),
                "city": getattr(doc, f"{field_prefix}_city", None) or getattr(parent_doc, f"{field_prefix}_city", ""),
                "state": getattr(doc, f"{field_prefix}_state", None) or getattr(parent_doc, f"{field_prefix}_state", ""),
                "country": getattr(doc, f"{field_prefix}_country", None) or getattr(parent_doc, f"{field_prefix}_country", "")
            }

        data = {
            "invoiceNumber": doc.name,
            "invoiceType": parent_doc.custom_invoice_type,
            "originInvoice": getattr(doc, "return_against", None),
            "customerName": doc.customer,
            "currencyCode": doc.custom_zra_currency or doc.currency,
            "exchangeRt": str(doc.custom_exchange_rate or 1),
            "dateOfInvoice": str(doc.posting_date),
            "dueDate": str(doc.due_date),
            "invoiceStatus": doc.custom_invoice_status,
            "Receipt": doc.custom_receipt,
            "ReceiptNo": doc.custom_rcptno,
            "lpoNumber": doc.custom_local_purchase_order_number or parent_doc.custom_local_purchase_order_number,
            "destnCountryCd": doc.custom_export_destination_country or parent_doc.custom_export_destination_country,

            "billingAddress": get_address("custom_billing_address"),
            "shippingAddress": get_address("custom_shipping_address"),

            "paymentInformation": {
                "paymentTerms": getattr(doc, "custom_payment_terms", None) or (getattr(parent_doc, "custom_payment_terms", None) if parent_doc else None) or (getattr(payment_doc, "duedates", None) if payment_doc else None),
                "paymentMethod": getattr(doc, "custom_payment_method", None) or (getattr(parent_doc, "custom_payment_method", None) if parent_doc else None) or (getattr(payment_doc, "payment_method", None) if payment_doc else None),
                "bankName": getattr(doc, "custom_bank_name", None) or getattr(parent_doc, "custom_bank_name", None),
                "accountNumber": getattr(doc, "custom_account_number", None) or getattr(parent_doc, "custom_account_number", None),
                "routingNumber": getattr(doc, "custom_routing_number", None) or getattr(parent_doc, "custom_routing_number", None),
                "swiftCode": getattr(doc, "custom_swift", None) or getattr(parent_doc, "custom_swift", None)
            },

            "items": items_data,

            "terms": {
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
def create_credit_note_from_sales_invoice():
    raw_body = frappe.local.request.get_data().decode("utf-8")
    try:
        request_data = json.loads(raw_body)
    except Exception:
        return send_response(
            status="fail",
            message="Invalid JSON payload",
            status_code=400,
            http_status=400
        )

    original_invoice_no = request_data.get("originalSalesInvoiceNumber")
    requested_items = request_data.get("items", [])
    CreditNoteReasonCode = request_data.get("CreditNoteReasonCode")
    invcAdjustReason = request_data.get("invcAdjustReason")
    transactionProgress = request_data.get("transactionProgress")
    if not transactionProgress:
        return send_response(
            status="fail",
            message="Transaction progress is required",
            status_code=400,
            http_status=400
        )

    VALID_TRANSACTION_PROGRESS = ["02", "05", "06", "04"]

    if transactionProgress not in VALID_TRANSACTION_PROGRESS:
        return send_response(
            status="fail",
            message=f"Invalid transaction progress: {transactionProgress}. Allowed values are {VALID_TRANSACTION_PROGRESS}",
            status_code=400,
            http_status=400
        )


    if not invcAdjustReason:
        return send_response(
            status="fail",
            message="Invoice adjustment reason (invcAdjustReason) is required.",
            status_code=400,
            http_status= 400
        )

    
    if not CreditNoteReasonCode:
        return send_response(
            status="fail",
            message="Credit Note Reason Code is required",
            status_code=400,
            http_status=400,
        )
    ALLOWED_CREDIT_REASON_CODE = ["01", "02", "03", "04", "05", "06", "07"]
    if CreditNoteReasonCode not in ALLOWED_CREDIT_REASON_CODE:
        return send_response(
        status="fail",
        message=(
            f"Invalid Credit Note Reason Code '{CreditNoteReasonCode}'. "
            f"Allowed values are: {', '.join(ALLOWED_CREDIT_REASON_CODE)}."
        ),
        status_code=400,
        http_status=400
    )

    if not original_invoice_no:
        return send_response(
            status="fail",
            message="originalSalesInvoiceNumber is required",
            status_code=400,
            http_status=400
        )

    if not isinstance(requested_items, list):
        return send_response(
            status="fail",
            message="items must be a list",
            status_code=400,
            http_status=400
        )

    if not frappe.db.exists("Sales Invoice", original_invoice_no):
        return send_response(
            status="fail",
            message=f"Sales Invoice '{original_invoice_no}' not found",
            status_code=404,
            http_status=404
        )

    sales_invoice = frappe.get_doc("Sales Invoice", original_invoice_no)
    customer = frappe.get_doc("Customer", sales_invoice.customer)

    customer_info = get_customer_details(customer.custom_id)
    if not customer_info or customer_info.get("status") == "fail":
        return customer_info

    credit_note_items = []
    zra_sale_items = []
    vat_codes_detected = set()

    for invoice_item in sales_invoice.items:
        requested_item = next(
            (i for i in requested_items if i.get("itemCode") == invoice_item.item_code),
            None
        )
        if not requested_item:
            continue

        quantity = float(requested_item.get("quantity", invoice_item.qty))
        if quantity <= 0:
            continue

        unit_price = float(requested_item.get("price", invoice_item.rate))
        tax_codes = get_sales_item_codes(original_invoice_no, invoice_item.item_code)

        vat_code = tax_codes.get("vatCd")
        vat_codes_detected.add(vat_code)

        item_master = get_item_details(invoice_item.item_code)
        if not item_master:
            return send_response(
                status="fail",
                message=f"Item '{invoice_item.item_code}' does not exist",
                status_code=404,
                http_status=404
            )

        credit_note_items.append({
            "item_code": invoice_item.item_code,
            "item_name": invoice_item.item_name,
            "qty": -abs(quantity),
            "rate": unit_price,
            "vatCd": vat_code,
            "iplCd": tax_codes.get("iplCd"),
            "tlCd": tax_codes.get("tlCd"),
            "custom_vatcd": vat_code,
            "custom_iplcd": tax_codes.get("iplCd"),
            "custom_tlcd": tax_codes.get("tlCd"),
            "warehouse": "Finished Goods - Izyane",
            "expense_account": "Stock Difference - Izyane - I",
        })

        zra_sale_items.append({
            "itemCode": invoice_item.item_code,
            "itemName": invoice_item.item_name,
            "qty": quantity,
            "itemClassCode": item_master.get("itemClassCd"),
            "productType": getattr(invoice_item, "product_type", "Finished Goods"),
            "packageUnitCode": item_master.get("itemPackingUnitCd"),
            "price": unit_price,
            "unitOfMeasure": item_master.get("itemUnitCd"),
            "VatCd": vat_code,
            "IplCd": tax_codes.get("iplCd"),
            "TlCd": tax_codes.get("tlCd"),
        })

    if not credit_note_items:
        return send_response(
            status="fail",
            message="No valid items found for Credit Note creation",
            status_code=400,
            http_status=400
        )

    if len(vat_codes_detected) > 1:
        return send_response(
            status="fail",
            message="Mixed VAT codes (C1 and C2) are not allowed in one Credit Note",
            status_code=400,
            http_status=400
        )

    vat_code = next(iter(vat_codes_detected))
    destination_country_code = None
    local_purchase_order_number = None
    paymentMethod = sales_invoice.custom_payment_method

    if not paymentMethod:
        return send_response(
            status="fail",
            message="Payment method is required for this sales invoice.",
            status_code=400
        )

    if vat_code == "C1":
        destination_country_code = sales_invoice.custom_export_destination_country
        if not destination_country_code:
            return send_response(
                status="fail",
                message="Export Destination Country is required on Sales Invoice for VAT C1",
                status_code=400,
                http_status=400
            )

    elif vat_code == "C2":
        local_purchase_order_number = sales_invoice.custom_local_purchase_order_number
        if not local_purchase_order_number:
            return send_response(
                status="fail",
                message="Local Purchase Order Number is required on Sales Invoice for VAT C2",
                status_code=400,
                http_status=400
            )

    next_invoice_number = SalesInvoice.get_next_invoice_name()

    zra_payload = {
        "originalInvoice": original_invoice_no,
        "name": next_invoice_number,
        "CreditNoteReasonCode": CreditNoteReasonCode,
        "invcAdjustReason": invcAdjustReason,
        "paymentMethod": paymentMethod,
        "transactionProgress": transactionProgress,
        "customerName": customer_info.get("customer_name"),
        "items": zra_sale_items
    }

    if destination_country_code:
        zra_payload["destnCountryCd"] = destination_country_code

    if local_purchase_order_number:
        zra_payload["lpoNumber"] = local_purchase_order_number

    zra_response = CREDIT_NOTE_SALE_INSTANCE.send_sale_data(zra_payload)

    if zra_response.get("resultCd") != "000":
        return send_response(
            status="fail",
            message=zra_response.get("resultMsg", "Unknown ZRA error"),
            status_code=400,
            http_status=400
        )

    additional_info = zra_response.get("additionalInfo", [])
    currency_code = additional_info[0] if len(additional_info) > 0 else None
    exchange_rate = additional_info[1] if len(additional_info) > 1 else None
    total_tax_amount = additional_info[2] if len(additional_info) > 2 else None

    zra_item_info = zra_response.get("additionInfoToBeSavedItem", [])
    zra_tax_lookup = {i["itemCd"]: i["vatTaxblAmt"] for i in zra_item_info}

    for item in credit_note_items:
        item_code = item.get("item_code")
        if item_code in zra_tax_lookup:
            item["custom_vattaxblamt"] = zra_tax_lookup[item_code]

    update_stock_allowed = 1 if sales_invoice.update_stock else 0

    credit_note = frappe.get_doc({
        "doctype": "Sales Invoice",
        "customer": sales_invoice.customer,
        "company": sales_invoice.company,
        "is_return": 1,
        "return_against": sales_invoice.name,
        "posting_date": frappe.utils.today(),
        "update_stock": 1 if update_stock_allowed else 0,
        "items": credit_note_items,
        "custom_exchange_rate": exchange_rate,
        "custom_total_tax_amount": total_tax_amount,
        "custom_zra_currency": currency_code,
        "title": f"Credit for {original_invoice_no}"
    })

    credit_note.insert(ignore_permissions=True)
    credit_note.submit()
    frappe.db.commit()

    return send_response(
        status="success",
        message=f"Credit Note '{credit_note.name}' created successfully",
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

    sales_invoice_no = payload.get("originalSalesInvoiceNumber")
    DebitNoteReasonCode = payload.get("DebitNoteReasonCode")
    invcAdjustReason = payload.get("invcAdjustReason")
    transactionProgress = payload.get("transactionProgress")
    if not transactionProgress:
        return send_response(
            status="fail",
            message="Transaction progress is required",
            status_code=400,
            http_status=400
        )

    VALID_TRANSACTION_PROGRESS = ["02", "05", "06", "04"]

    if transactionProgress not in VALID_TRANSACTION_PROGRESS:
        return send_response(
            status="fail",
            message=f"Invalid transaction progress: {transactionProgress}. Allowed values are {VALID_TRANSACTION_PROGRESS}",
            status_code=400,
            http_status=400
        )


    if not invcAdjustReason:
        return send_response(
            status="fail",
            message="Invoice adjustment reason (invcAdjustReason) is required.",
            status_code=400,
            http_status= 400
        )

    
    if not DebitNoteReasonCode:
        return send_response(
            status="fail",
            message="Credit Note Reason Code is required",
            status_code=400,
            http_status=400,
        )
    ALLOWED_DEBIT_REASON_CODE = ["01", "02", "03", "04"]
    if DebitNoteReasonCode not in ALLOWED_DEBIT_REASON_CODE:
        return send_response(
        status="fail",
        message=(
            f"Invalid Credit Note Reason Code '{DebitNoteReasonCode}'. "
            f"Allowed values are: {', '.join(ALLOWED_DEBIT_REASON_CODE)}."
        ),
        status_code=400,
        http_status=400
    )
    req_items = payload.get("items", [])

    if not sales_invoice_no:
        return send_response(status="fail", message="Original Sales Invoice number is required", status_code=400)

    if not isinstance(req_items, list) or not req_items:
        return send_response(status="fail", message="Items must be a non-empty list", status_code=400)

    if not frappe.db.exists("Sales Invoice", sales_invoice_no):
        return send_response(status="fail", message=f"Sales Invoice '{sales_invoice_no}' not found", status_code=404)

    sales_invoice = frappe.get_doc("Sales Invoice", sales_invoice_no)
    if not sales_invoice.customer:
        return send_response(status="fail", message="Sales Invoice has no customer assigned", status_code=400)

    customer_doc = frappe.get_doc("Customer", sales_invoice.customer)
    customer_data = get_customer_details(customer_doc.custom_id)

    if not customer_data or customer_data.get("status") == "fail":
        return customer_data

    debit_items = []
    sale_payload_items = []

    for inv_item in sales_invoice.items:

        req_item = next((i for i in req_items if i.get("itemCode") == inv_item.item_code), None)
        if not req_item:
            continue

        qty = float(req_item.get("quantity", inv_item.qty))
        if qty <= 0:
            continue

        item_code = inv_item.item_code
        item_codes = get_sales_item_codes(sales_invoice_no, item_code)
        rate = float(req_item.get("price", inv_item.rate))

        vatCd = item_codes.get("vatCd", "")
        iplCd = item_codes.get("iplCd", "")
        tlCd = item_codes.get("tlCd", "")
        destination_country_code = None
        local_purchase_order_number = None
        paymentMethod = sales_invoice.custom_payment_method

        if not paymentMethod:
            return send_response(
                status="fail",
                message="Payment method is required for this sales invoice.",
                status_code=400
            )

        if vatCd == "C1":
            destination_country_code = getattr(sales_invoice, "custom_export_destination_country", None)
            if not destination_country_code:
                return send_response(
                    status="fail",
                    message=f"Export Destination Country is required on Sales Invoice for item {item_code}",
                    status_code=400
                )

        if vatCd == "C2":
            local_purchase_order_number = getattr(sales_invoice, "custom_local_purchase_order_number", None)
            if not local_purchase_order_number:
                return send_response(
                    status="fail",
                    message=f"Local Purchase Order Number is required on Sales Invoice for item {item_code} with VAT C",
                    status_code=400
                )

        item_details = get_item_details(item_code)
        if not item_details:
            return send_response(
                status="fail",
                message=f"Item '{item_code}' does not exist",
                status_code=404
            )
        debit_items.append({
            "item_code": item_code,
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
            "itemCode": item_code,
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
        "customer_tpin": customer_data.get("tax_id"),
        "destnCountryCd": destination_country_code,
        "lpoNumber": local_purchase_order_number,
        "DebitNoteReasonCode": DebitNoteReasonCode,
        "invcAdjustReason": invcAdjustReason,
        "paymentMethod": paymentMethod,
        "transactionProgress": transactionProgress,
        "items": sale_payload_items
    }

    print("Sales Payload to be procced: ", sale_payload)
    print("DEBIT PAYLOAD:", sale_payload)

    result = DEBIT_NOTE_INSTANCE.send_sale_data(sale_payload)
    if result.get("resultCd") != "000":
        return send_response(
            status="fail",
            message=result.get("resultMsg", "Unknown error from ZRA"),
            status_code=400
        )

    canUpdateInvoice = all(
        ZRA_CLIENT_INSTANCE.canItemStockBeUpdate(item.get("itemCode")) 
        for item in debit_items
    )

    additional_info = result.get("additionalInfo", [None, None, None])
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
            status_code=201,
            http_status=201
        )
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Create Debit Note API Error")
        frappe.db.rollback()
        return send_response(status="fail", message=f"Unexpected Error: {str(e)}", status_code=500)



@frappe.whitelist(allow_guest=False, methods=["PATCH"])
def update_invoice_status():
    try:
        data = frappe.form_dict

        invoice_name = data.get("invoiceNumber")
        invoice_status = data.get("invoiceStatus")

        if not invoice_name or not invoice_status:
            return send_response(
                status="fail",
                message="invoiceNumber and invoiceStatus are required",
                status_code=400
            )
            
        ALLOWED_INVOICE_STATUS = {
            "Draft",
            "Approved",
            "Rejected",
            "Paid",
            "Cancelled"
        }

        if invoice_status not in ALLOWED_INVOICE_STATUS:
            return send_response(
                status="fail",
                message=(
                    f"Invalid invoiceStatus '{invoice_status}'. "
                    f"Allowed values are: {', '.join(ALLOWED_INVOICE_STATUS)}"
                ),
                status_code=400
            )
        if not frappe.db.exists("Sales Invoice", invoice_name):
            return send_response(
                status="fail",
                message=f"Sales Invoice {invoice_name} not found",
                status_code=404
            )

        if not frappe.has_permission("Sales Invoice", "write", invoice_name):
            return send_response(
                status="fail",
                message="You do not have permission to update this invoice",
                status_code=403
            )

        frappe.db.sql(
            """
            UPDATE `tabSales Invoice`
            SET custom_invoice_status = %s
            WHERE name = %s
            """,
            (invoice_status, invoice_name)
        )

        frappe.db.commit()

        return send_response(
            status="success",
            message=f"Invoice {invoice_name} status updated to {invoice_status}",
            status_code=200
        )

    except Exception as e:
        frappe.log_error(
            frappe.get_traceback(),
            "Update Invoice Status SQL + Enum Error"
        )
        return send_response(
            status="fail",
            message=f"Unexpected Error: {str(e)}",
            status_code=500
        )


