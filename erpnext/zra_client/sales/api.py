from erpnext.accounts.doctype.sales_invoice.sales_invoice import SalesInvoice
from erpnext.zra_client.main import ZRAClient
from erpnext.zra_client.sales.sale_helper import NormaSale
from erpnext.zra_client.sales.credit_note import CreditNoteSale
from erpnext.zra_client.sales.debit_note import DebitNoteSale
from erpnext.zra_client.generic_api import send_response
from frappe import _
import random
import frappe
import json


CREDIT_NOTE_SALE_INSTANCE = CreditNoteSale()
DEBIT_NOTE_INSTANCE = DebitNoteSale()
NORMAL_SALE_INSTANCE = NormaSale()
ZRA_CLIENT_INSTANCE = ZRAClient()


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
    print("calling create sale api")
    customer_id = frappe.form_dict.get("customer_id")
    isExport = frappe.form_dict.get("isExport")
    isRvatSale = frappe.form_dict.get("isRvatAgent")
    principalId = frappe.form_dict.get("principalId")
    currencyCd = frappe.form_dict.get("currencyCode")
    exchangeRt = frappe.form_dict.get("exchangeRt")
    createBy = frappe.form_dict.get("created_by")
    destnCountryCd = frappe.form_dict.get("destnCountryCd")
    lpoNumber = frappe.form_dict.get("lpoNumber")
        
    if not currencyCd:
        currencyCd = "ZMW"
        exchangeRt = "1"

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

    customer_id = payload.get("customer_id")
    items = payload.get("items", [])

    if not customer_id:
        return send_response(
            status="fail",
            message="Customer ID is required",
            status_code=400,
            http_status=400
        )

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
        item_code = item.get("item_code")
        qty = item.get("qty", 1)
        rate = item.get("price")
        vatCd = item.get("vatCd")
        iplCd = item.get("iplCd")
        tlCd = item.get("tlCd")
        
        VAT_LIST = ["A", "B", "C1", "C2", "C3", "D", "E", "RVAT"]

        if vatCd not in VAT_LIST:
            send_response(
                status="fail",
                message=f"'vatCatCd' must be a valid VAT tax category: {', '.join(VAT_LIST)}. Rejected value: [{vatCd}]",
                status_code=400,
                http_status=400
            )
            return
        
        checkStockResponse, checkStockStatusCode = ZRA_CLIENT_INSTANCE.check_stock(item_code, qty)
        if checkStockStatusCode != 200:
            return checkStockResponse
    

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
            "warehouse": "Lusaka 1 - IIS",
            "qty": qty,
            "rate": rate,
            "custom_vatcd": vatCd,
            "custom_iplcd": iplCd,
            "custom_tlcd":tlCd
        
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
            "TlCd": tlCd
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

    print("Sales payload data: ",sale_payload)
    

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



    print("results: ", result)
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
            "custom_exchange_rate": exchange_rate,
            "custom_total_tax_amount": total_tax,
            "custom_zra_currency": currency,
            "customer": customer_data.get("name"),
            "update_stock": 1 if canUpdateInvoice else 0,  
            "items": invoice_items
        })
        doc.insert(ignore_permissions=True)
        doc.submit()
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
        invoices = frappe.get_all(
            "Sales Invoice",
            fields=["name", "customer", "posting_date", "grand_total", "status"],
            order_by="creation desc"
        )

        return send_response(
            status="success",
            message="All Sales Invoices fetched successfully",
            status_code=200,
            http_status=200,
            data=invoices
        )

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get All Sales Invoices API Error")
        return send_response(
            status="fail",
            message=str(e),
            status_code=500,
            http_status=500
        )


@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_sales_invoice_by_id():
    invoice_name = (frappe.form_dict.get("id") or "").strip()
    if not invoice_name:
        send_response(
            status="fail",
            message="Invoice id is required",
            status_code=400,
            http_status=400
        )

    try:
        if invoice_name:
            doc = frappe.get_doc("Sales Invoice", invoice_name)
            data = {
                "invoice_name": doc.name,
                "customer": doc.customer,
                "posting_date": doc.posting_date,
                "total": doc.grand_total,
                "status": doc.status,
                "items": [
                    {
                        "item_code": i.item_code,
                        "item_name": i.item_name,
                        "qty": i.qty,
                        "rate": i.rate,
                        "amount": i.amount
                    }
                    for i in doc.items
                ]
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
            "custom_tlcd": item_codes["tlCd"]
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
            "custom_tlcd": tlCd
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
