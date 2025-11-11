import json
from erpnext.zra_client.sales.sale_helper import NormaSale
from erpnext.zra_client.generic_api import send_response
from frappe import _
import frappe

NORMAL_SALE_INSTANCE = NormaSale()

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

    return {
        "itemName": itemName,
        "itemClassCd": itemClassCd,
        "itemPackingUnitCd": itemPackingUnitCd,
        "itemUnitCd": itemUnitCd
    }



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
            status_code=400
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

        if vatCd == "C2":
            if lpoNumber is None:
                send_response(
                    status="fail",
                    message="Local Purchase Order number (LPO) is required for transactions with VatCd 'B' and cannot be null.",
                    status_code=400,
                    http_status=400
                )
                return
        if vatCd == "C":
            if destnCountryCd is None:
                send_response(
                    status="fail",
                    message="Destination country is required for VatCd 'C' transactions. Please ensure the export flag (isExport) is set correctly.",
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
            "qty": qty,
            "rate": rate
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

    sale_payload = {
        "sale_name": payload.get("sale_name", "SINV-00001"),
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
    print("results: ", result)
    if result.get("resultCd") != "000":
        return send_response(
            status="fail",
            message=result.get("resultMsg", "Unknown error from ZRA"),
            status_code=400,
            http_status=400
        )

    try:
        doc = frappe.get_doc({
            "doctype": "Sales Invoice",
            "customer": customer_data.get("name"),
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
