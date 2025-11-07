import json
from erpnext.zra_client.main import ZRAClient
from erpnext.zra_client.generic_api import send_response
from frappe.utils.data import flt
from datetime import datetime
import frappe

ZRA_CLIENT = ZRAClient()

def validate_item_and_warehouse(item_code, warehouse):
    """Validate that Item and Warehouse exist"""
    if not frappe.db.exists("Item", item_code):
        return send_response(
            status="fail",
            message=f"Item '{item_code}' does not exist",
            status_code=404,
            http_status=404
        )
    if not frappe.db.exists("Warehouse", warehouse):
        return send_response(
            status="fail",
            message=f"Warehouse '{warehouse}' does not exist",
            status_code=404,
            http_status=404
        )
    return None


@frappe.whitelist(allow_guest=False)
def create_item_stock_api():
    try:
        data = frappe.form_dict
        item_code = data.get("item_code")
        warehouse = data.get("warehouse")
        qty = data.get("qty")
        price = data.get("price")

        if isinstance(item_code, list):
            item_code = item_code[0]
        if isinstance(warehouse, list):
            warehouse = warehouse[0]

        qty = float(qty[0]) if isinstance(qty, list) else float(qty or 0)
        price = float(price[0]) if isinstance(price, list) else float(price or 0)

        if not item_code or not warehouse:
            return send_response("fail", "Item Code and Warehouse are required", 400, 400)

        today = datetime.today().strftime('%Y%m%d')


        itemUnitPrice = price
        vatAmount = price * 0.16
        taxblAmt = itemUnitPrice - vatAmount
        totTaxblAmt = taxblAmt
        totTaxAmt = vatAmount

        PAYLOAD = {
            "tpin": ZRA_CLIENT.get_tpin(),
            "bhfId": ZRA_CLIENT.get_branch_code(),
            "sarNo": 1,
            "orgSarNo": 0,
            "regTyCd": "M",
            "sarTyCd": "04",
            "ocrnDt": today,
            "totItemCnt": 1,
            "totTaxblAmt": totTaxblAmt,
            "totTaxAmt": totTaxAmt,
            "totAmt": price,
            "regrId": "Admin",
            "regrNm": "Admin",
            "modrNm": "Admin",
            "modrId": "Admin",
            "itemList": [
                {
                "itemSeq": 1,
                "itemCd": "20044",
                "itemClsCd": "50102517",
                "itemNm": "Soupu dedede",
                "pkgUnitCd": "BA",
                "qtyUnitCd": "BE",
                "qty": 1,
                "pkg": 1,
                "totDcAmt": 0,
                "prc": itemUnitPrice,
                "splyAmt": price,
                "taxblAmt": taxblAmt,
                "vatCatCd": "A",
                "taxAmt": vatAmount,
                "totAmt": itemUnitPrice
                }
            ]
            }
        
        print(json.dumps(PAYLOAD, indent=4))
        result = ZRA_CLIENT.create_item_stock_zra_client(PAYLOAD)
        data = result.json()
        print(data)

        if data.get("resultCd") != "000":
            send_response(
                status="fail",
                message=data.get("resultMsg", "Customer Sync Failed"),
                status_code=400,
                data=None,
                http_status=400
            )
            return

        stock_entry = frappe.get_doc({
            "doctype": "Stock Entry",
            "stock_entry_type": "Material Receipt",
            "items": [{
                "item_code": item_code,
                "t_warehouse": warehouse,
                "qty": qty,
                "basic_rate": price
            }]
        })
        stock_entry.insert()
        stock_entry.submit()

        stock_data = {
            "name": stock_entry.name,
            "item_code": item_code,
            "warehouse": warehouse,
            "qty": qty,
            "price": price
        }

        return send_response("success", "Stock created successfully", 201, 201)

    except frappe.PermissionError:
        return send_response("fail", "Permission denied", 403, 403)
    except Exception as e:
        return send_response("error", f"Failed to create stock: {str(e)}", 500, 500)


@frappe.whitelist(allow_guest=False)
def get_all_stocks():
    try:
        stock_entries = frappe.get_all(
            "Stock Entry",
            fields=["name", "stock_entry_type", "posting_date"],
            order_by="creation desc",
            limit_page_length=100
        )

        all_data = []

        for se in stock_entries:
            name = se.name[0] if isinstance(se.name, list) else se.name
            se_doc = frappe.get_doc("Stock Entry", name)
            if se_doc.items:
                item = se_doc.items[0]
                all_data.append({
                    "name": se_doc.name,
                    "item_code": item.item_code,
                    "warehouse": item.t_warehouse,
                    "qty": item.qty,
                    "price": item.basic_rate,
                    "posting_date": se_doc.posting_date
                })

        return send_response(
            status="success",
            message="Stock retrieved",
            data=all_data,
            status_code=200,
            http_status=200
        )

    except frappe.PermissionError:
        return send_response("fail", "Permission denied", [], 403, 403)
    except Exception as e:
        frappe.log_error(f"get_all_stocks() error: {str(e)}", "Stock API Error")
        return send_response("error", f"Failed to retrieve stocks: {str(e)}", [], 500, 500)



@frappe.whitelist(allow_guest=False)
def get_stock_by_id(bin_id=None):
    if not bin_id:
        return send_response("fail", "Bin ID is required", 400, 400)

    try:
        bin_doc = frappe.get_doc("Bin", bin_id)
        price = frappe.db.sql("""
            SELECT IFNULL(SUM(sle.valuation_rate * sle.actual_qty)/NULLIF(SUM(sle.actual_qty),0),0)
            FROM `tabStock Ledger Entry` sle
            WHERE sle.item_code=%s AND sle.warehouse=%s
        """, (bin_doc.item_code, bin_doc.warehouse))
        price = price[0][0] if price else 0.0

        data = {
            "name": bin_doc.name,
            "item_code": bin_doc.item_code,
            "warehouse": bin_doc.warehouse,
            "actual_qty": bin_doc.actual_qty,
            "reserved_qty": bin_doc.reserved_qty,
            "ordered_qty": bin_doc.ordered_qty,
            "price": flt(price)
        }
        return send_response("success", "Stock retrieved", data=data, status_code=200, http_status=200)

    except frappe.DoesNotExistError:
        return send_response("fail", f"Bin '{bin_id}' does not exist", 404, 404)
    except Exception as e:
        return send_response("error", f"Failed to retrieve stock: {str(e)}", 500, 500)


@frappe.whitelist(allow_guest=False)
def delete_stock_entry(stock_entry_id=None):
    if not stock_entry_id:
        return send_response("fail", "Stock Entry ID is required", 400, 400)

    try:
        se_doc = frappe.get_doc("Stock Entry", stock_entry_id)
        se_doc.cancel()
        se_doc.delete()
        frappe.db.commit()
        return send_response("success", f"Stock Entry '{stock_entry_id}' deleted", 200, 200)

    except frappe.DoesNotExistError:
        return send_response("fail", f"Stock Entry '{stock_entry_id}' does not exist", 404, 404)
    except frappe.PermissionError:
        return send_response("fail", "Permission denied", 403, 403)
    except frappe.LinkExistsError as e:
        return send_response("fail", f"Cannot delete: {str(e)}", 400, 400)
    except Exception as e:
        msg = str(e)
        if "is linked with" in msg:
            return send_response("fail", "Cannot delete this Stock Entry because it is linked to GL Entries or other records.", 409, 409)
        return send_response("error", f"Failed to delete stock entry: {msg}", 500, 500)


@frappe.whitelist(allow_guest=False)
def get_stock_by_name(bin_name=None):
    if not bin_name:
        return send_response("fail", "Bin name is required", 400, 400)

    try:
        bin_doc = frappe.get_doc("Bin", bin_name)
        data = {
            "name": bin_doc.name,
            "item_code": bin_doc.item_code,
            "warehouse": bin_doc.warehouse,
            "actual_qty": flt(bin_doc.actual_qty),
            "reserved_qty": flt(bin_doc.reserved_qty),
            "ordered_qty": flt(bin_doc.ordered_qty),
            "valuation_rate": flt(bin_doc.valuation_rate)
        }
        return send_response("success", "Stock retrieved successfully", data=data, status_code=200, http_status=200)

    except frappe.DoesNotExistError:
        return send_response("fail", f"Bin '{bin_name}' does not exist", 404, 404)
    except frappe.PermissionError:
        return send_response("fail", "Permission denied", 403, 403)
    except Exception as e:
        return send_response("error", f"Failed to retrieve stock: {str(e)}", 500, 500)

