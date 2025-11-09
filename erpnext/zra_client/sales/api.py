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
    customer_id = (frappe.form_dict.get("customer_id") or "").strip()
    item_code = (frappe.form_dict.get("item_code") or "").strip()
    qty = frappe.form_dict.get("qty") or 1
    rate = frappe.form_dict.get("rate") or 0

    if not customer_id:
        return send_response(
            status="fail",
            message="Customer ID is required",
            status_code=400
        )

    if not item_code:
        send_response(
            status="fail",
            message="Item Code is required",
            status_code=400
        )

        return
    customer_data = get_customer_details(customer_id)
    if not customer_data or customer_data.get("status") == "fail":
        return customer_data

    
    item_details = get_item_details(item_code)
    if not item_details:
        return send_response(
            status="fail",
            message=f"Item '{item_code}' does not exist",
            status_code=404,
            http_status=404
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
    
    FIRST_PAYLOAD = {
        "sale_name": "SINV-00045",
        "customer_name": "Absa Bank",
        "customer_tpin": "2206741731",
        "export_destination_country": " ",
        "lpo_number": "LPO-98765",
        "is_lpo_transactions": "true",
        "is_export": "true",
        "is_rvat_agent": "false",
        "principal_id": "PRINC-001",
        "currency_code": "USD",
        "exchangeRt": 19.5,
        "is_stock_updated": "true",
        "created_by": "john.doe@example.com",
        "items": [
            {
            "itemCode": "ZM2BOXU61613",
            "itemName": "Cake",
            "qty": 2,
            "itemClassCode": "CLASS-A",
            "product_type": "Finished Goods",
            "packageUnitCode": "BOX",
            "price": 200,
            "VatCd": "B",
            "unitOfMeasure": "PCS",
            "IplCd": "",
            "TlCd": "",
            "ExciseCd": "",
            },
        ]
        }

    NORMAL_SALE_INSTANCE.send_sale_data(FIRST_PAYLOAD)
    try:
        doc = frappe.get_doc({
            "doctype": "Sales Invoice",
            "customer": customer_data.get("name"),
            "items": [
                {
                    "item_code": item_code,
                    "item_name": item_details.get("itemName"),
                    "qty": qty,
                    "rate": rate
                }
            ]
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
