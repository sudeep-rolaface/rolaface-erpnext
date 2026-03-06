# import json
# from erpnext.zra_client.main import ZRAClient
# from erpnext.zra_client.generic_api import send_response
# from frappe.utils.data import flt
# from datetime import datetime
# import frappe

# from erpnext.zra_client.custom_frappe_client import CustomFrappeClient
# CUSTOM_FRAPPE_INSTANCE = CustomFrappeClient()

# ZRA_CLIENT = ZRAClient()

# def get_item_details(item_code):
#     if not item_code:
#         return send_response(
#             status="fail",
#             message="Item code is required.",
#             status_code=400,
#             http_status=400
#         )
    
#     try:
#         item = frappe.get_doc("Item", item_code)
#     except frappe.DoesNotExistError:
#         return send_response(
#             status="fail",
#             message="Item not found",
#             status_code=404,
#             http_status=404
#         )
#     except Exception as e:
#         return send_response(
#             status="fail",
#             message=f"Cannot proceed: {str(e)}",
#             status_code=400,
#             http_status=400
#         )
    
#     itemName = item.item_name
#     itemClassCd = getattr(item, "custom_itemclscd", None)
#     itemPackingUnitCd = getattr(item, "custom_pkgunitcd", None)
#     itemUnitCd = getattr(item, "stock_uom", None)

#     return {
#         "itemName": itemName,
#         "itemClassCd": itemClassCd,
#         "itemPackingUnitCd": itemPackingUnitCd,
#         "itemUnitCd": itemUnitCd
#     }


# def validate_item_and_warehouse(item_code, warehouse):
#     if not frappe.db.exists("Item", item_code):
#         return send_response(
#             status="fail",
#             message=f"Item '{item_code}' does not exist",
#             status_code=404,
#             http_status=404
#         )
#     if not frappe.db.exists("Warehouse", warehouse):
#         return send_response(
#             status="fail",
#             message=f"Warehouse '{warehouse}' does not exist",
#             status_code=404,
#             http_status=404
#         )
#     return None


# @frappe.whitelist(allow_guest=False)
# def create_item_stock_api():
#     try:
#         data = json.loads(frappe.request.data)
#         warehouse = data.get("warehouse")
#         items_data = data.get("items", [])

#         if not warehouse:
#             warehouse = "Finished Goods - RI"
# 	    #return send_response("fail", "Warehouse is required", 400, 400)

#         if not frappe.db.exists("Warehouse", warehouse):
#             return send_response("fail", f"Warehouse '{warehouse}' does not exist", 404, 404)

#         if not items_data:
#             return send_response("fail", "No items provided", 400, 400)

#         # Read ZRA flag from site_config.json
#         enable_zra = frappe.conf.get("enable_zra_sync", False)

#         today = datetime.today().strftime('%Y%m%d')

#         itemList = []
#         totTaxblAmt = totTaxAmt = totAmt = 0
#         stock_items = []

#         for i, item in enumerate(items_data):
#             item_code = item.get("item_code")
#             qty = flt(item.get("qty", 0))
#             price = flt(item.get("price", 0))
#             batch_no = item.get("batch_no")
#             if not item_code or qty <= 0 or price <= 0:
#                 return send_response("fail", f"Invalid data for item {i+1}", 400, 400)

#             item_details = get_item_details(item_code)
#             if not item_details:
#                 return send_response(
#                     status="fail",
#                     message=f"Item '{item_code}' does not exist",
#                     status_code=404,
#                     http_status=404
#                 )

#             splyAmt = round(price * qty, 4)
#             taxblAmt = round(splyAmt / 1.16, 4)
#             vatAmount = round(splyAmt - taxblAmt, 4)
#             totItemAmt = round(splyAmt, 4)

#             totTaxblAmt += taxblAmt
#             totTaxAmt += vatAmount
#             totAmt += totItemAmt

#             itemList.append({
#                 "itemSeq": i + 1,
#                 "itemCd": item_code,
#                 "itemClsCd": item_details.get("itemClassCd"),
#                 "itemNm": item_details.get("itemName"),
#                 "pkgUnitCd": item_details.get("itemPackingUnitCd"),
#                 "qtyUnitCd": item_details.get("itemUnitCd"),
#                 "qty": qty,
#                 "pkg": 1,
#                 "totDcAmt": 0,
#                 "prc": price,
#                 "splyAmt": splyAmt,
#                 "taxblAmt": taxblAmt,
#                 "vatCatCd": "A",
#                 "taxAmt": vatAmount,
#                 "totAmt": totItemAmt
#             })

#             stock_items.append({
#                 "item_code": item_code,
#                 "t_warehouse": warehouse,
#                 "qty": qty,
#                 "basic_rate": price,
#                 "custom_taxable_amount": taxblAmt,
#                 "custom_tax_amount": vatAmount,
#                 "custom_total_amount": totItemAmt,
#                 "batch_no": batch_no
#             })

#         # Default values used when ZRA is disabled
#         org_sar_no = 0
#         reg_ty_cd = "M"
#         sar_ty_cd = "04"

#         # ── ZRA Sync (only when enable_zra_sync = true in site_config.json) ──
#         if enable_zra:
#             PAYLOAD = {
#                 "tpin": ZRA_CLIENT.get_tpin(),
#                 "bhfId": ZRA_CLIENT.get_branch_code(),
#                 "sarNo": 1,
#                 "orgSarNo": 0,
#                 "regTyCd": reg_ty_cd,
#                 "sarTyCd": sar_ty_cd,
#                 "ocrnDt": today,
#                 "totItemCnt": len(itemList),
#                 "totTaxblAmt": round(totTaxblAmt, 4),
#                 "totTaxAmt": round(totTaxAmt, 4),
#                 "totAmt": round(totAmt, 4),
#                 "regrId": frappe.session.user,
#                 "regrNm": frappe.session.user,
#                 "modrNm": frappe.session.user,
#                 "modrId": frappe.session.user,
#                 "itemList": itemList
#             }

#             print(json.dumps(PAYLOAD, indent=4))

#             org_sar_no = 0
#             if frappe.conf.get("enable_zra_sync", False):
#                 result = ZRA_CLIENT.create_item_stock_zra_client(PAYLOAD)
#                 data_result = result.json()
#                 print(data_result)
#                 if data_result.get("resultCd") != "000":
#                     return send_response(
#                         status="fail",
#                         message=data_result.get("resultMsg", "ZRA Stock Sync Failed"),
#                         status_code=400,
#                         data=None,
#                         http_status=400
#                     )

#                 org_sar_no = data_result.get("orgSarNo", 0)

#         # ── Create Stock Entry (always runs, ZRA or not) ───────────────────────
#         company = frappe.defaults.get_global_default("company")

#         stock_entry = frappe.get_doc({
#             "doctype": "Stock Entry",
#             "company": company,
#             "stock_entry_type": "Material Receipt",
#             "custom_original_sar_no": org_sar_no,
#             "custom_registration_type_code": reg_ty_cd,
#             "custom_sar_type_code": sar_ty_cd,
#             "custom_total_taxable_amount": round(totTaxblAmt, 4),
#             "difference_account": "Stock Adjustment - " + company,
#             "items": stock_items
#         })

#         stock_entry.insert(ignore_permissions=True)
#         stock_entry.submit()

#         return send_response("success", "Stock created successfully", 201, 201)

#     except frappe.PermissionError:
#         return send_response("fail", "Permission denied", 403, 403)

#     except Exception as e:
#         frappe.log_error(frappe.get_traceback(), "Create Item Stock API Error")
#         return send_response("error", f"Failed to create stock: {str(e)}", 500, 500)


# @frappe.whitelist(allow_guest=False)
# def get_all_stock_entries():
#     try:
#         stock_entries_list = []
#         stock_entries = frappe.get_all(
#             "Stock Entry",
#             fields=[
#                 "name",
#                 "posting_date",
#                 "custom_original_sar_no",
#                 "custom_registration_type_code",
#                 "custom_sar_type_code",
#                 "custom_total_taxable_amount",
#             ],
#             order_by="creation desc"
#         )

#         for entry in stock_entries:
#             items = frappe.get_all(
#                 "Stock Entry Detail",
#                 filters={"parent": entry["name"]},
#                 fields=[
#                     "item_code",
#                     "qty",
#                     "basic_rate",
#                     "custom_taxable_amount",
#                     "custom_tax_amount",
#                     "custom_total_amount"
#                 ]
#             )

#             warehouse = frappe.get_value(
#                 "Stock Entry Detail",
#                 {"parent": entry["name"]},
#                 "t_warehouse"
#             )

#             stock_entries_list.append({
#                 "name": entry["name"],
#                 "posting_date": entry["posting_date"],
#                 "custom_original_sar_no": entry["custom_original_sar_no"],
#                 "custom_registration_type_code": entry["custom_registration_type_code"],
#                 "custom_sar_type_code": entry["custom_sar_type_code"],
#                 "custom_total_taxable_amount": entry["custom_total_taxable_amount"],
#                 "warehouse": warehouse,
#                 "items": items
#             })

#         return send_response(
#             status="success",
#             message="",
#             data=stock_entries_list,
#             status_code=200,
#             http_status=200
#         )

#     except Exception as e:
#         frappe.log_error(frappe.get_traceback(), "Get Stock Entries Error")
#         return send_response(
#             "error",
#             f"Failed to fetch stock entries: {str(e)}",
#             500,
#             500
#         )


# @frappe.whitelist(allow_guest=False)
# def get_stock_by_id(bin_id=None):
#     if not bin_id:
#         return send_response("fail", "Bin ID is required", 400, 400)

#     try:
#         bin_doc = frappe.get_doc("Bin", bin_id)
#         price = frappe.db.sql("""
#             SELECT IFNULL(SUM(sle.valuation_rate * sle.actual_qty)/NULLIF(SUM(sle.actual_qty),0),0)
#             FROM `tabStock Ledger Entry` sle
#             WHERE sle.item_code=%s AND sle.warehouse=%s
#         """, (bin_doc.item_code, bin_doc.warehouse))
#         price = price[0][0] if price else 0.0

#         data = {
#             "name": bin_doc.name,
#             "item_code": bin_doc.item_code,
#             "warehouse": bin_doc.warehouse,
#             "actual_qty": bin_doc.actual_qty,
#             "reserved_qty": bin_doc.reserved_qty,
#             "ordered_qty": bin_doc.ordered_qty,
#             "price": flt(price)
#         }
#         return send_response("success", "Stock retrieved", data=data, status_code=200, http_status=200)

#     except frappe.DoesNotExistError:
#         return send_response("fail", f"Bin '{bin_id}' does not exist", 404, 404)
#     except Exception as e:
#         return send_response("error", f"Failed to retrieve stock: {str(e)}", 500, 500)


# @frappe.whitelist(allow_guest=False)
# def delete_stock_entry(stock_entry_id=None):
#     if not stock_entry_id:
#         return send_response("fail", "Stock Entry ID is required", 400, 400)

#     try:
#         se_doc = frappe.get_doc("Stock Entry", stock_entry_id)

#         if se_doc.docstatus == 1:
#             se_doc.cancel()
#         se_doc.delete()
#         frappe.db.commit()

#         return send_response(
#             "success",
#             f"Stock Entry '{stock_entry_id}' deleted successfully",
#             200,
#             200
#         )

#     except frappe.DoesNotExistError:
#         return send_response(
#             "fail",
#             f"Stock Entry '{stock_entry_id}' does not exist",
#             404,
#             404
#         )

#     except frappe.PermissionError:
#         return send_response("fail", "Permission denied", 403, 403)

#     except frappe.LinkExistsError as e:
#         return send_response(
#             "fail",
#             "Cannot delete this Stock Entry because it is linked to other records (GL Entry, Accounting, etc.)",
#             400,
#             400
#         )

#     except Exception as e:
#         frappe.log_error(frappe.get_traceback(), "Delete Stock Entry Error")
#         return send_response(
#             "error",
#             f"Failed to delete Stock Entry: {str(e)}",
#             500,
#             500
#         )
import json
from erpnext.zra_client.main import ZRAClient
from erpnext.zra_client.generic_api import send_response
from frappe.utils.data import flt
from datetime import datetime
import frappe

from collections import defaultdict

from erpnext.zra_client.custom_frappe_client import CustomFrappeClient
CUSTOM_FRAPPE_INSTANCE = CustomFrappeClient()

ZRA_CLIENT = ZRAClient()

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


def validate_item_and_warehouse(item_code, warehouse):
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
        data = json.loads(frappe.request.data)
        warehouse = data.get("warehouse")
        items_data = data.get("items", [])

        if not warehouse:
            warehouse = "Finished Goods - RI"

        if not frappe.db.exists("Warehouse", warehouse):
            return send_response("fail", f"Warehouse '{warehouse}' does not exist", 404, 404)

        if not items_data:
            return send_response("fail", "No items provided", 400, 400)

        # Read ZRA flag from site_config.json
        enable_zra = frappe.conf.get("enable_zra_sync", False)

        today = datetime.today().strftime('%Y%m%d')

        itemList = []
        totTaxblAmt = totTaxAmt = totAmt = 0
        stock_items = []

        for i, item in enumerate(items_data):
            item_code = item.get("item_code")
            qty = flt(item.get("qty", 0))
            price = flt(item.get("price", 0))
            batch_no = item.get("batch_no")
            if not item_code or qty <= 0 or price <= 0:
                return send_response("fail", f"Invalid data for item {i+1}", 400, 400)

            item_details = get_item_details(item_code)
            if not item_details:
                return send_response(
                    status="fail",
                    message=f"Item '{item_code}' does not exist",
                    status_code=404,
                    http_status=404
                )

            splyAmt = round(price * qty, 4)
            taxblAmt = round(splyAmt / 1.16, 4)
            vatAmount = round(splyAmt - taxblAmt, 4)
            totItemAmt = round(splyAmt, 4)

            totTaxblAmt += taxblAmt
            totTaxAmt += vatAmount
            totAmt += totItemAmt

            itemList.append({
                "itemSeq": i + 1,
                "itemCd": item_code,
                "itemClsCd": item_details.get("itemClassCd"),
                "itemNm": item_details.get("itemName"),
                "pkgUnitCd": item_details.get("itemPackingUnitCd"),
                "qtyUnitCd": item_details.get("itemUnitCd"),
                "qty": qty,
                "pkg": 1,
                "totDcAmt": 0,
                "prc": price,
                "splyAmt": splyAmt,
                "taxblAmt": taxblAmt,
                "vatCatCd": "A",
                "taxAmt": vatAmount,
                "totAmt": totItemAmt
            })

            stock_items.append({
                "item_code": item_code,
                "t_warehouse": warehouse,
                "qty": qty,
                "basic_rate": price,
                "custom_taxable_amount": taxblAmt,
                "custom_tax_amount": vatAmount,
                "custom_total_amount": totItemAmt,
                "batch_no": batch_no
            })

        # Default values used when ZRA is disabled
        org_sar_no = 0
        reg_ty_cd = "M"
        sar_ty_cd = "04"

        # ── ZRA Sync (only when enable_zra_sync = true in site_config.json) ──
        if enable_zra:
            PAYLOAD = {
                "tpin": ZRA_CLIENT.get_tpin(),
                "bhfId": ZRA_CLIENT.get_branch_code(),
                "sarNo": 1,
                "orgSarNo": 0,
                "regTyCd": reg_ty_cd,
                "sarTyCd": sar_ty_cd,
                "ocrnDt": today,
                "totItemCnt": len(itemList),
                "totTaxblAmt": round(totTaxblAmt, 4),
                "totTaxAmt": round(totTaxAmt, 4),
                "totAmt": round(totAmt, 4),
                "regrId": frappe.session.user,
                "regrNm": frappe.session.user,
                "modrNm": frappe.session.user,
                "modrId": frappe.session.user,
                "itemList": itemList
            }

            print(json.dumps(PAYLOAD, indent=4))

            org_sar_no = 0
            if frappe.conf.get("enable_zra_sync", False):
                result = ZRA_CLIENT.create_item_stock_zra_client(PAYLOAD)
                data_result = result.json()
                print(data_result)
                if data_result.get("resultCd") != "000":
                    return send_response(
                        status="fail",
                        message=data_result.get("resultMsg", "ZRA Stock Sync Failed"),
                        status_code=400,
                        data=None,
                        http_status=400
                    )

                org_sar_no = data_result.get("orgSarNo", 0)

        # ── Create Batches if batch_no provided ──────────────────────────────
        for stock_item in stock_items:
            batch_no = stock_item.get("batch_no")
            item_code = stock_item.get("item_code")
            if batch_no and item_code:
                if not frappe.db.exists("Batch", batch_no):
                    batch = frappe.get_doc({
                        "doctype": "Batch",
                        "batch_id": batch_no,
                        "item": item_code
                    })
                    batch.insert(ignore_permissions=True)
                    frappe.db.commit()

        # ── Create Stock Entry (always runs, ZRA or not) ─────────────────────
        company = frappe.defaults.get_global_default("company")

        stock_entry = frappe.get_doc({
            "doctype": "Stock Entry",
            "company": company,
            "stock_entry_type": "Material Receipt",
            "custom_original_sar_no": org_sar_no,
            "custom_registration_type_code": reg_ty_cd,
            "custom_sar_type_code": sar_ty_cd,
            "custom_total_taxable_amount": round(totTaxblAmt, 4),
            "difference_account": "Stock Adjustment - " + company,
            "items": stock_items
        })

        stock_entry.insert(ignore_permissions=True)
        stock_entry.submit()

        return send_response("success", "Stock created successfully", 201, 201)

    except frappe.PermissionError:
        return send_response("fail", "Permission denied", 403, 403)

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Create Item Stock API Error")
        return send_response("error", f"Failed to create stock: {str(e)}", 500, 500)


@frappe.whitelist(allow_guest=False)
def get_all_stock_entries():
    try:
        stock_entries_list = []
        stock_entries = frappe.get_all(
            "Stock Entry",
            fields=[
                "name",
                "posting_date",
                "custom_original_sar_no",
                "custom_registration_type_code",
                "custom_sar_type_code",
                "custom_total_taxable_amount",
            ],
            order_by="creation desc"
        )

        for entry in stock_entries:
            items = frappe.get_all(
                "Stock Entry Detail",
                filters={"parent": entry["name"]},
                fields=[
                    "item_code",
                    "qty",
                    "basic_rate",
                    "custom_taxable_amount",
                    "custom_tax_amount",
                    "custom_total_amount"
                ]
            )

            warehouse = frappe.get_value(
                "Stock Entry Detail",
                {"parent": entry["name"]},
                "t_warehouse"
            )

            stock_entries_list.append({
                "name": entry["name"],
                "posting_date": entry["posting_date"],
                "custom_original_sar_no": entry["custom_original_sar_no"],
                "custom_registration_type_code": entry["custom_registration_type_code"],
                "custom_sar_type_code": entry["custom_sar_type_code"],
                "custom_total_taxable_amount": entry["custom_total_taxable_amount"],
                "warehouse": warehouse,
                "items": items
            })

        return send_response(
            status="success",
            message="",
            data=stock_entries_list,
            status_code=200,
            http_status=200
        )

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Stock Entries Error")
        return send_response(
            "error",
            f"Failed to fetch stock entries: {str(e)}",
            500,
            500
        )


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

        if se_doc.docstatus == 1:
            se_doc.cancel()
        se_doc.delete()
        frappe.db.commit()

        return send_response(
            "success",
            f"Stock Entry '{stock_entry_id}' deleted successfully",
            200,
            200
        )

    except frappe.DoesNotExistError:
        return send_response(
            "fail",
            f"Stock Entry '{stock_entry_id}' does not exist",
            404,
            404
        )

    except frappe.PermissionError:
        return send_response("fail", "Permission denied", 403, 403)

    except frappe.LinkExistsError as e:
        return send_response(
            "fail",
            "Cannot delete this Stock Entry because it is linked to other records (GL Entry, Accounting, etc.)",
            400,
            400
        )

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Delete Stock Entry Error")
        return send_response(
            "error",
            f"Failed to delete Stock Entry: {str(e)}",
            500,
            500
        )





@frappe.whitelist()
def get_stock_balance(
    from_date=None,     # ← optional now
    to_date=None,       # ← optional now
    warehouse=None,
    item_code=None,
    page=1,             # ← pagination: page number
    page_size=20,       # ← pagination: records per page
):
    """
    Custom Stock Balance API
    GET /api/method/custom_stock_api.api.stock.get_stock_balance
        &from_date=2025-12-01     (optional)
        &to_date=2026-03-06       (optional)
        &warehouse=Finished Goods (optional)
        &item_code=ITEM-001       (optional)
        &page=1                   (optional, default 1)
        &page_size=20             (optional, default 20)
    """

    page      = int(page)
    page_size = int(page_size)

    # ── Step 1: Opening qty (SLE before from_date) ───────────────────────────
    opening_map = {}

    if from_date:
        opening_filters = {
            "posting_date": ("<", from_date),
            "docstatus":    1,
            "is_cancelled": 0,
        }
        if warehouse: opening_filters["warehouse"] = warehouse
        if item_code: opening_filters["item_code"] = item_code

        opening_entries = frappe.get_all(
            "Stock Ledger Entry",
            filters=opening_filters,
            fields=["item_code", "name", "warehouse",
                    "qty_after_transaction", "valuation_rate"],
            order_by="posting_date asc, posting_time asc",
            limit=0,   # fetch all
        )

        for e in opening_entries:
            key = (e["item_code"], e["warehouse"])
            opening_map[key] = {
                "name":      e["name"],
                "opening_qty":    e["qty_after_transaction"],
                "valuation_rate": e["valuation_rate"] or 0,
            }

    # ── Step 2: Movement entries ─────────────────────────────────────────────
    range_filters = {
        "docstatus":    1,
        "is_cancelled": 0,
    }
    if from_date: range_filters["posting_date"] = (">=", from_date)
    if to_date:   range_filters["posting_date"] = ("<=", to_date)

    # both from and to date provided — use between
    if from_date and to_date:
        range_filters["posting_date"] = ("between", [from_date, to_date])

    if warehouse: range_filters["warehouse"] = warehouse
    if item_code: range_filters["item_code"] = item_code

    range_entries = frappe.get_all(
        "Stock Ledger Entry",
        filters=range_filters,
        fields=[
            "item_code", "name", "warehouse", "actual_qty",
            "qty_after_transaction", "valuation_rate", "stock_value"
        ],
        order_by="posting_date asc, posting_time asc",
        limit=0,   # fetch all for calculation
    )

    # ── Step 3: Calculate in/out per (item, warehouse) ───────────────────────
    movement = defaultdict(lambda: {
        "name": "", "in_qty": 0.0, "out_qty": 0.0,
        "last_qty_after": 0.0, "last_valuation_rate": 0.0,
    })

    for e in range_entries:
        key = (e["item_code"], e["warehouse"])
        movement[key]["name"]           = e["name"]
        movement[key]["last_qty_after"]      = e["qty_after_transaction"]
        movement[key]["last_valuation_rate"] = e["valuation_rate"] or 0

        if e["actual_qty"] > 0:
            movement[key]["in_qty"]  += e["actual_qty"]
        else:
            movement[key]["out_qty"] += abs(e["actual_qty"])

    # ── Step 4: Build full result ─────────────────────────────────────────────
    all_keys = set(opening_map.keys()) | set(movement.keys())
    result = []

    for (code, wh) in sorted(all_keys):
        o = opening_map.get((code, wh), {
            "name": "", "opening_qty": 0.0, "valuation_rate": 0.0
        })
        m = movement.get((code, wh), {
            "name": "", "in_qty": 0.0, "out_qty": 0.0,
            "last_valuation_rate": 0.0
        })

        opening_qty = o["opening_qty"]
        in_qty      = m["in_qty"]
        out_qty     = m["out_qty"]
        bal_qty     = opening_qty + in_qty - out_qty
        val_rate    = m["last_valuation_rate"] or o["valuation_rate"]
        bal_val     = round(bal_qty * val_rate, 2)

        result.append({
            "item_code":      code,
            "name":      o["name"] or m["name"],
            "warehouse":      wh,
            "opening_qty":    opening_qty,
            "in_qty":         in_qty,
            "out_qty":        out_qty,
            "bal_qty":        bal_qty,
            "bal_val":        bal_val,
            "valuation_rate": val_rate,
        })

    # ── Step 5: Pagination ────────────────────────────────────────────────────
    total_records = len(result)
    total_pages   = max(1, -(-total_records // page_size))  # ceiling division
    start         = (page - 1) * page_size
    end           = start + page_size
    paginated     = result[start:end]

    return {
        "data":          paginated,
        "pagination": {
            "page":          page,
            "page_size":     page_size,
            "total_records": total_records,
            "total_pages":   total_pages,
            "has_next":      page < total_pages,
            "has_prev":      page > 1,
        }
    }