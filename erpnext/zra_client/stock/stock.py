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





# @frappe.whitelist()
# def get_stock_balance(
#     from_date=None,     # ← optional now
#     to_date=None,       # ← optional now
#     warehouse=None,
#     item_code=None,
#     batch_no=None, 
#     page=1,             # ← pagination: page number
#     page_size=20,       # ← pagination: records per page
# ):
#     """
#     Custom Stock Balance API
#     GET /api/method/custom_stock_api.api.stock.get_stock_balance
#         &from_date=2025-12-01     (optional)
#         &to_date=2026-03-06       (optional)
#         &warehouse=Finished Goods (optional)
#         &item_code=ITEM-001       (optional)
#         &batch_no=BATCH-001       (optional)
#         &page=1                   (optional, default 1)
#         &page_size=20             (optional, default 20)
#     """

#     page      = int(page)
#     page_size = int(page_size)

#     # ── Step 1: Opening qty (SLE before from_date) ───────────────────────────
#     opening_map = {}

#     if from_date:
#         opening_filters = {
#             "posting_date": ("<", from_date),
#             "docstatus":    1,
#             "is_cancelled": 0,
#         }
#         if warehouse: opening_filters["warehouse"] = warehouse
#         if item_code: opening_filters["item_code"] = item_code
#         if batch_no:  opening_filters["batch_no"]  = batch_no

#         opening_entries = frappe.get_all(
#             "Stock Ledger Entry",
#             filters=opening_filters,
#             fields=["item_code", "name", "warehouse","batch_no",
#                     "qty_after_transaction", "valuation_rate", "stock_value"],
#             order_by="posting_date asc, posting_time asc",
#             limit=0,   # fetch all
#         )

#         for e in opening_entries:
#             key = (e["item_code"], e["warehouse"], e["batch_no"] or "")
#             opening_map[key] = {
#                 "name":      e["name"],
#                 "opening_qty":    e["qty_after_transaction"],
#                 "opening_value":  e["stock_value"] or 0,
#                 "valuation_rate": e["valuation_rate"] or 0,
#             }

#     # ── Step 2: Movement entries ─────────────────────────────────────────────
#     range_filters = {
#         "docstatus":    1,
#         "is_cancelled": 0,
#     }
#     if from_date and to_date:
#         range_filters["posting_date"] = ("between", [from_date, to_date])
#     elif from_date:
#         range_filters["posting_date"] = (">=", from_date)
#     elif to_date:
#         range_filters["posting_date"] = ("<=", to_date)

    

#     if warehouse: range_filters["warehouse"] = warehouse
#     if item_code: range_filters["item_code"] = item_code
#     if batch_no:  range_filters["batch_no"]  = batch_no


#     range_entries = frappe.get_all(
#         "Stock Ledger Entry",
#         filters=range_filters,
#         fields=[
#             "item_code", "name", "warehouse", "actual_qty", "batch_no",
#             "qty_after_transaction", "valuation_rate", "stock_value", "stock_value_difference",  # ← for buy/sell value
#             "voucher_type",
#         ],
#         order_by="posting_date asc, posting_time asc",
#         limit=0,   # fetch all for calculation
#     )

#     # ── Step 3: Calculate in/out per (item, warehouse) ───────────────────────
#     movement = defaultdict(lambda: {
#         "name": "", "in_qty": 0.0, "out_qty": 0.0,
#         "buy_value":          0.0,   # ← total value of incoming stock
#         "sell_value":         0.0,  
#         "last_qty_after": 0.0, "last_valuation_rate": 0.0,
#     })

#     for e in range_entries:
#         key = (e["item_code"], e["warehouse"], e["batch_no"] or "")
#         movement[key]["name"]           = e["name"]
#         movement[key]["last_qty_after"]      = e["qty_after_transaction"]
#         movement[key]["last_valuation_rate"] = e["valuation_rate"] or 0

#         val_diff = e["stock_value_difference"] or 0

#         if e["actual_qty"] > 0:
#             movement[key]["in_qty"]  += e["actual_qty"]
#             movement[key]["buy_value"] += val_diff
#         else:
#             movement[key]["out_qty"] += abs(e["actual_qty"])
#             movement[key]["sell_value"] += abs(val_diff)

#     # ── Step 4: Build full result ─────────────────────────────────────────────
#     all_keys = set(opening_map.keys()) | set(movement.keys())
#     result = []

#     for (code, wh, batch) in sorted(all_keys):
#         o = opening_map.get((code, wh, batch), {
#             "name": "", "opening_qty": 0.0,"opening_value":  0.0,
# "valuation_rate": 0.0
#         })
#         m = movement.get((code, wh, batch), {
#             "name": "", "in_qty": 0.0, "out_qty": 0.0,"buy_value": 0.0,
#             "sell_value": 0.0,
#             "last_valuation_rate": 0.0
#         })

#         opening_qty = o["opening_qty"]
#         in_qty      = m["in_qty"]
#         out_qty     = m["out_qty"]
#         bal_qty     = opening_qty + in_qty - out_qty
#         val_rate    = m["last_valuation_rate"] or o["valuation_rate"]
#         bal_val     = round(bal_qty * val_rate, 2)

#         result.append({
#             "item_code":      code,
#             "name":      o["name"] or m["name"],
#             "warehouse":      wh,
#             "batch_no":       batch or None,      # ← batch no
#             "opening_qty":    opening_qty,
#             "in_qty":         in_qty,
#             "out_qty":        out_qty,
#             "bal_qty":        bal_qty,
#             "bal_val":        bal_val,
#             "valuation_rate": val_rate,
#             "buy_value":      round(m["buy_value"],  2),   # ← total incoming value
#             "sell_value":     round(m["sell_value"], 2),   
#         })

#     # ── Step 5: Pagination ────────────────────────────────────────────────────
#     total_records = len(result)
#     total_pages   = max(1, -(-total_records // page_size))  # ceiling division
#     start         = (page - 1) * page_size
#     end           = start + page_size
#     paginated     = result[start:end]

#     return {
#         "data":          paginated,
#         "pagination": {
#             "page":          page,
#             "page_size":     page_size,
#             "total_records": total_records,
#             "total_pages":   total_pages,
#             "has_next":      page < total_pages,
#             "has_prev":      page > 1,
#         }
#     }


# import frappe
# from collections import defaultdict


# @frappe.whitelist()
# def get_stock_balance(
#     from_date=None,
#     to_date=None,
#     warehouse=None,
#     item_code=None,
#     item_group=None,
#     batch_no=None,
#     page=1,
#     page_size=20,
# ):
#     """
#     Custom Stock Balance API
#     GET /api/method/custom_stock_api.api.stock.get_stock_balance
#         ?from_date=2025-12-01                   (optional)
#         &from_date=2025-12-01                   (optional)
#         &to_date=2026-03-06                     (optional)
#         &warehouse=Finished Goods - RI          (optional)
#         &item_code=ITEM-001                     (optional)
#         &item_group=raw material                (optional)
#         &batch_no=BATCH-001                     (optional)
#         &page=1                                 (optional, default 1)
#         &page_size=20                           (optional, default 20)
#     """

#     page      = int(page)
#     page_size = int(page_size)

#     # ── Helper: build base filters ───────────────────────────────────────────
#     def base_filters():
#         f = {
#             "company":      frappe.defaults.get_global_default("company"),
#             "docstatus":    1,
#             "is_cancelled": 0,
#         }
#         if warehouse:  f["warehouse"]  = warehouse
#         if item_code:  f["item_code"]  = item_code
#         if batch_no:   f["batch_no"]   = batch_no
#         return f

#     # ── Step 1: Opening qty (SLE before from_date) ───────────────────────────
#     opening_map = {}

#     if from_date:
#         opening_filters = base_filters()
#         opening_filters["posting_date"] = ("<", from_date)

#         opening_entries = frappe.get_all(
#             "Stock Ledger Entry",
#             filters=opening_filters,
#             fields=[
#                 "item_code", "warehouse", "batch_no",
#                 "qty_after_transaction", "valuation_rate", "stock_value"
#             ],
#             order_by="posting_date asc, posting_time asc",
#             limit=0,
#         )

#         for e in opening_entries:
#             key = (e["item_code"], e["warehouse"], e["batch_no"] or "")
#             opening_map[key] = {
#                 "opening_qty":    e["qty_after_transaction"],
#                 "opening_value":  round(e["stock_value"] or 0, 2),
#                 "valuation_rate": e["valuation_rate"] or 0,
#             }

#     # ── Step 2: Movement entries ─────────────────────────────────────────────
#     range_filters = base_filters()

#     if from_date and to_date:
#         range_filters["posting_date"] = ("between", [from_date, to_date])
#     elif from_date:
#         range_filters["posting_date"] = (">=", from_date)
#     elif to_date:
#         range_filters["posting_date"] = ("<=", to_date)

#     range_entries = frappe.get_all(
#         "Stock Ledger Entry",
#         filters=range_filters,
#         fields=[
#             "item_code", "warehouse", "batch_no",
#             "actual_qty", "qty_after_transaction",
#             "valuation_rate", "stock_value", "stock_value_difference",
#             "voucher_type",
#         ],
#         order_by="posting_date asc, posting_time asc",
#         limit=0,
#     )

#     # ── Step 3: Calculate per (item, warehouse, batch) ───────────────────────
#     movement = defaultdict(lambda: {
#         "in_qty":              0.0,
#         "in_value":            0.0,
#         "out_qty":             0.0,
#         "out_value":           0.0,
#         "last_qty_after":      0.0,
#         "last_valuation_rate": 0.0,
#         "last_stock_value":    0.0,
#     })

#     for e in range_entries:
#         key      = (e["item_code"], e["warehouse"], e["batch_no"] or "")
#         m        = movement[key]
#         val_diff = e["stock_value_difference"] or 0

#         m["last_qty_after"]      = e["qty_after_transaction"]
#         m["last_valuation_rate"] = e["valuation_rate"] or 0
#         m["last_stock_value"]    = e["stock_value"] or 0

#         if e["actual_qty"] > 0:
#             m["in_qty"]    += e["actual_qty"]
#             m["in_value"]  += val_diff
#         else:
#             m["out_qty"]   += abs(e["actual_qty"])
#             m["out_value"] += abs(val_diff)

#     # ── Step 4: Fetch name, item_group, stock_uom from Item doctype ──────────
#     all_item_codes = list({key[0] for key in set(opening_map.keys()) | set(movement.keys())})

#     item_details_map = {}
#     if all_item_codes:
#         item_details = frappe.get_all(
#             "Item",
#             filters=[["item_code", "in", all_item_codes]],
#             fields=["item_code", "name", "item_group", "stock_uom"],
#             limit=0,
#         )
#         for item in item_details:
#             item_details_map[item["item_code"]] = {
#                 "name":       item["name"],
#                 "item_group": item["item_group"],
#                 "stock_uom":  item["stock_uom"],
#             }

#     # ── Step 5: Build final result ────────────────────────────────────────────
#     all_keys = set(opening_map.keys()) | set(movement.keys())
#     result   = []

#     for (code, wh, batch) in sorted(all_keys):
#         o = opening_map.get((code, wh, batch), {
#             "opening_qty":    0.0,
#             "opening_value":  0.0,
#             "valuation_rate": 0.0,
#         })
#         m = movement.get((code, wh, batch), {
#             "in_qty":              0.0,
#             "in_value":            0.0,
#             "out_qty":             0.0,
#             "out_value":           0.0,
#             "last_valuation_rate": 0.0,
#             "last_stock_value":    0.0,
#         })
#         item_info = item_details_map.get(code, {
#             "name":       "",
#             "item_group": "",
#             "stock_uom":  "",
#         })

#         if item_group and item_info.get("item_group") != item_group:
#             continue

#         opening_qty   = o["opening_qty"]
#         opening_value = o["opening_value"]
#         in_qty        = m["in_qty"]
#         in_value      = round(m["in_value"],  2)
#         out_qty       = m["out_qty"]
#         out_value     = round(m["out_value"], 2)
#         bal_qty       = opening_qty + in_qty - out_qty
#         val_rate      = m["last_valuation_rate"] or o["valuation_rate"]
#         bal_val       = round(bal_qty * val_rate, 2)

#         result.append({
#             "item_code":      code,
#             "name":           item_info.get("name", ""),
#             "item_group":     item_info.get("item_group", ""),
#             "warehouse":      wh,
#             "stock_uom":      item_info.get("stock_uom", ""),
#             "batch_no":       batch or None,
#             "opening_qty":    opening_qty,
#             "opening_value":  opening_value,
#             "in_qty":         in_qty,
#             "in_value":       in_value,
#             "out_qty":        out_qty,
#             "out_value":      out_value,
#             "bal_qty":        bal_qty,
#             "bal_val":        bal_val,
#             "valuation_rate": val_rate,
#         })

#     # ── Step 6: Pagination ────────────────────────────────────────────────────
#     total_records = len(result)
#     total_pages   = max(1, -(-total_records // page_size))
#     start         = (page - 1) * page_size
#     end           = start + page_size

#     return {
#         "data": result[start:end],
#         "pagination": {
#             "page":          page,
#             "page_size":     page_size,
#             "total_records": total_records,
#             "total_pages":   total_pages,
#             "has_next":      page < total_pages,
#             "has_prev":      page > 1,
#         }
#     }


# @frappe.whitelist()
# def get_stock_balance(
#     from_date=None,
#     to_date=None,
#     warehouse=None,
#     item_code=None,
#     item_group=None,
#     batch_no=None,
#     page=1,
#     page_size=20,
# ):
#     """
#     Custom Stock Balance API
#     GET /api/method/custom_stock_api.api.stock.get_stock_balance
#         ?from_date=2025-12-01                   (optional)
#         &from_date=2025-12-01                   (optional)
#         &to_date=2026-03-06                     (optional)
#         &warehouse=Finished Goods - RI          (optional)
#         &item_code=ITEM-001                     (optional)
#         &item_group=raw material                (optional)
#         &batch_no=BATCH-001                     (optional)
#         &page=1                                 (optional, default 1)
#         &page_size=20                           (optional, default 20)
#     """

#     page      = int(page)
#     page_size = int(page_size)

#     # ── Helper: build base filters ───────────────────────────────────────────
#     def base_filters():
#         f = {
#             "company":      frappe.defaults.get_global_default("company"),
#             "docstatus":    1,
#             "is_cancelled": 0,
#         }
#         if warehouse:  f["warehouse"]  = warehouse
#         if item_code:  f["item_code"]  = item_code
#         if batch_no:   f["batch_no"]   = batch_no
#         return f

#     # ── Step 1: Opening qty (SLE before from_date) ───────────────────────────
#     opening_map = {}

#     if from_date:
#         opening_filters = base_filters()
#         opening_filters["posting_date"] = ("<", from_date)

#         opening_entries = frappe.get_all(
#             "Stock Ledger Entry",
#             filters=opening_filters,
#             fields=[
#                 "item_code", "warehouse", "batch_no",
#                 "qty_after_transaction", "valuation_rate", "stock_value"
#             ],
#             order_by="posting_date asc, posting_time asc",
#             limit=0,
#         )

#         for e in opening_entries:
#             key = (e["item_code"], e["warehouse"], e["batch_no"] or "")
#             opening_map[key] = {
#                 "opening_qty":    e["qty_after_transaction"],
#                 "opening_value":  round(e["stock_value"] or 0, 2),
#                 "valuation_rate": e["valuation_rate"] or 0,
#             }

#     # ── Step 2: Movement entries ─────────────────────────────────────────────
#     range_filters = base_filters()

#     if from_date and to_date:
#         range_filters["posting_date"] = ("between", [from_date, to_date])
#     elif from_date:
#         range_filters["posting_date"] = (">=", from_date)
#     elif to_date:
#         range_filters["posting_date"] = ("<=", to_date)

#     range_entries = frappe.get_all(
#         "Stock Ledger Entry",
#         filters=range_filters,
#         fields=[
#             "item_code", "warehouse", "batch_no",
#             "actual_qty", "qty_after_transaction",
#             "valuation_rate", "stock_value", "stock_value_difference",
#             "voucher_type",
#         ],
#         order_by="posting_date asc, posting_time asc",
#         limit=0,
#     )

#     # ── Step 3: Calculate per (item, warehouse, batch) ───────────────────────
#     movement = defaultdict(lambda: {
#         "in_qty":              0.0,
#         "in_value":            0.0,
#         "out_qty":             0.0,
#         "out_value":           0.0,
#         "buy_value":           0.0,   # ← total incoming stock value
#         "sell_value":          0.0,   # ← total outgoing stock value
#         "last_qty_after":      0.0,
#         "last_valuation_rate": 0.0,
#         "last_stock_value":    0.0,
#     })

#     for e in range_entries:
#         key      = (e["item_code"], e["warehouse"], e["batch_no"] or "")
#         m        = movement[key]
#         val_diff = e["stock_value_difference"] or 0

#         m["last_qty_after"]      = e["qty_after_transaction"]
#         m["last_valuation_rate"] = e["valuation_rate"] or 0
#         m["last_stock_value"]    = e["stock_value"] or 0

#         if e["actual_qty"] > 0:
#             # Incoming — Purchase Receipt, Material Receipt etc.
#             m["in_qty"]    += e["actual_qty"]
#             m["in_value"]  += val_diff
#             m["buy_value"] += val_diff           # ← buy value
#         else:
#             # Outgoing — Delivery Note, Material Issue etc.
#             m["out_qty"]    += abs(e["actual_qty"])
#             m["out_value"]  += abs(val_diff)
#             m["sell_value"] += abs(val_diff)     # ← sell value

#     # ── Step 4: Fetch name, item_group, stock_uom from Item doctype ──────────
#     all_item_codes = list({key[0] for key in set(opening_map.keys()) | set(movement.keys())})

#     item_details_map = {}
#     if all_item_codes:
#         item_details = frappe.get_all(
#             "Item",
#             filters=[["item_code", "in", all_item_codes]],
#             fields=["item_code", "name", "item_group", "stock_uom"],
#             limit=0,
#         )
#         for item in item_details:
#             item_details_map[item["item_code"]] = {
#                 "name":       item["name"],
#                 "item_group": item["item_group"],
#                 "stock_uom":  item["stock_uom"],
#             }

#     # ── Step 5: Build final result ────────────────────────────────────────────
#     all_keys = set(opening_map.keys()) | set(movement.keys())
#     result   = []

#     for (code, wh, batch) in sorted(all_keys):
#         o = opening_map.get((code, wh, batch), {
#             "opening_qty":    0.0,
#             "opening_value":  0.0,
#             "valuation_rate": 0.0,
#         })
#         m = movement.get((code, wh, batch), {
#             "in_qty":              0.0,
#             "in_value":            0.0,
#             "out_qty":             0.0,
#             "out_value":           0.0,
#             "buy_value":           0.0,
#             "sell_value":          0.0,
#             "last_valuation_rate": 0.0,
#             "last_stock_value":    0.0,
#         })
#         item_info = item_details_map.get(code, {
#             "name":       "",
#             "item_group": "",
#             "stock_uom":  "",
#         })

#         if item_group and item_info.get("item_group") != item_group:
#             continue

#         opening_qty   = o["opening_qty"]
#         opening_value = o["opening_value"]
#         in_qty        = m["in_qty"]
#         in_value      = round(m["in_value"],   2)
#         out_qty       = m["out_qty"]
#         out_value     = round(m["out_value"],  2)
#         buy_value     = round(m["buy_value"],  2)
#         sell_value    = round(m["sell_value"], 2)
#         bal_qty       = opening_qty + in_qty - out_qty
#         val_rate      = m["last_valuation_rate"] or o["valuation_rate"]
#         bal_val       = round(bal_qty * val_rate, 2)

#         result.append({
#             "item_code":      code,
#             "name":           item_info.get("name",       ""),
#             "item_group":     item_info.get("item_group", ""),
#             "warehouse":      wh,
#             "stock_uom":      item_info.get("stock_uom",  ""),
#             "batch_no":       batch or None,
#             "opening_qty":    opening_qty,
#             "opening_value":  opening_value,
#             "in_qty":         in_qty,
#             "in_value":       in_value,
#             "out_qty":        out_qty,
#             "out_value":      out_value,
#             "bal_qty":        bal_qty,
#             "bal_val":        bal_val,
#             "valuation_rate": val_rate,
#             "buy_value":      buy_value,    # ← total value of all incoming stock
#             "sell_value":     sell_value,   # ← total value of all outgoing stock
#         })

#     # ── Step 6: Pagination ────────────────────────────────────────────────────
#     total_records = len(result)
#     total_pages   = max(1, -(-total_records // page_size))
#     start         = (page - 1) * page_size
#     end           = start + page_size

#     return {
#         "data": result[start:end],
#         "pagination": {
#             "page":          page,
#             "page_size":     page_size,
#             "total_records": total_records,
#             "total_pages":   total_pages,
#             "has_next":      page < total_pages,
#             "has_prev":      page > 1,
#         }
#     }



@frappe.whitelist()
def get_stock_balance(
    from_date=None,
    to_date=None,
    warehouse=None,
    item_code=None,
    item_group=None,
    batch_no=None,
    page=1,
    page_size=20,
):
    page      = int(page)
    page_size = int(page_size)

    # ── Helper: build base filters ───────────────────────────────────────────
    def base_filters():
        f = {
            "company":      frappe.defaults.get_global_default("company"),
            "docstatus":    1,
            "is_cancelled": 0,
        }
        if warehouse:  f["warehouse"]  = warehouse
        if item_code:  f["item_code"]  = item_code
        if batch_no:   f["batch_no"]   = batch_no
        return f

    # ── Step 1: Opening qty (SLE before from_date) ───────────────────────────
    opening_map = {}

    if from_date:
        opening_filters = base_filters()
        opening_filters["posting_date"] = ("<", from_date)

        opening_entries = frappe.get_all(
            "Stock Ledger Entry",
            filters=opening_filters,
            fields=[
                "item_code", "warehouse", "batch_no",
                "qty_after_transaction", "valuation_rate", "stock_value"
            ],
            order_by="posting_date asc, posting_time asc",
            limit=0,
        )

        for e in opening_entries:
            key = (e["item_code"], e["warehouse"], e["batch_no"] or "")
            opening_map[key] = {
                "opening_qty":    e["qty_after_transaction"],
                "opening_value":  round(e["stock_value"] or 0, 2),
                "valuation_rate": e["valuation_rate"] or 0,
            }

    # ── Step 2: Movement entries ─────────────────────────────────────────────
    range_filters = base_filters()

    if from_date and to_date:
        range_filters["posting_date"] = ("between", [from_date, to_date])
    elif from_date:
        range_filters["posting_date"] = (">=", from_date)
    elif to_date:
        range_filters["posting_date"] = ("<=", to_date)

    range_entries = frappe.get_all(
        "Stock Ledger Entry",
        filters=range_filters,
        fields=[
            "item_code", "warehouse", "batch_no",
            "actual_qty", "qty_after_transaction",
            "valuation_rate", "stock_value", "stock_value_difference",
            "voucher_type",
        ],
        order_by="posting_date asc, posting_time asc",
        limit=0,
    )

    # ── Step 3: Calculate per (item, warehouse, batch) ───────────────────────
    movement = defaultdict(lambda: {
        "in_qty":              0.0,
        "in_value":            0.0,
        "out_qty":             0.0,
        "out_value":           0.0,
        "buy_value":           0.0,
        "sell_value":          0.0,
        "last_qty_after":      0.0,
        "last_valuation_rate": 0.0,
        "last_stock_value":    0.0,
    })

    for e in range_entries:
        key      = (e["item_code"], e["warehouse"], e["batch_no"] or "")
        m        = movement[key]
        val_diff = e["stock_value_difference"] or 0

        m["last_qty_after"]      = e["qty_after_transaction"]
        m["last_valuation_rate"] = e["valuation_rate"] or 0
        m["last_stock_value"]    = e["stock_value"] or 0

        if e["actual_qty"] > 0:
            m["in_qty"]    += e["actual_qty"]
            m["in_value"]  += val_diff
            m["buy_value"] += val_diff
        else:
            m["out_qty"]    += abs(e["actual_qty"])
            m["out_value"]  += abs(val_diff)
            m["sell_value"] += abs(val_diff)

    # ── Step 4: Fetch item_name, item_group, stock_uom from Item doctype ─────
    all_item_codes = list({key[0] for key in set(opening_map.keys()) | set(movement.keys())})

    item_details_map = {}
    if all_item_codes:
        item_details = frappe.get_all(
            "Item",
            filters=[["item_code", "in", all_item_codes]],
            fields=["item_code", "item_name", "item_group", "stock_uom"],  # ← item_name field
            limit=0,
        )
        for item in item_details:
            item_details_map[item["item_code"]] = {
                "item_name":  item["item_name"],   # ← actual name like "dfetyde"
                "item_group": item["item_group"],
                "stock_uom":  item["stock_uom"],
            }

    # ── Step 5: Group by (item_code, warehouse) → collect batch_no as list ───
    all_keys  = set(opening_map.keys()) | set(movement.keys())

    # key: (item_code, warehouse) → item row
    items_map = {}

    for (code, wh, batch) in sorted(all_keys):
        o = opening_map.get((code, wh, batch), {
            "opening_qty":    0.0,
            "opening_value":  0.0,
            "valuation_rate": 0.0,
        })
        m = movement.get((code, wh, batch), {
            "in_qty":              0.0,
            "in_value":            0.0,
            "out_qty":             0.0,
            "out_value":           0.0,
            "buy_value":           0.0,
            "sell_value":          0.0,
            "last_valuation_rate": 0.0,
            "last_stock_value":    0.0,
        })
        item_info = item_details_map.get(code, {
            "item_name":  "",
            "item_group": "",
            "stock_uom":  "",
        })

        if item_group and item_info.get("item_group") != item_group:
            continue

        item_key = (code, wh)

        if item_key not in items_map:
            # initialize item row
            items_map[item_key] = {
                "item_code":      code,
                "item_name":      item_info.get("item_name", ""),  # ← actual item name
                "item_group":     item_info.get("item_group", ""),
                "warehouse":      wh,
                "stock_uom":      item_info.get("stock_uom", ""),
                "batch_no":       [],     # ← start as empty list
                "opening_qty":    0.0,
                "opening_value":  0.0,
                "in_qty":         0.0,
                "in_value":       0.0,
                "out_qty":        0.0,
                "out_value":      0.0,
                "bal_qty":        0.0,
                "bal_val":        0.0,
                "valuation_rate": 0.0,
                "buy_value":      0.0,
                "sell_value":     0.0,
            }

        row = items_map[item_key]

        # collect batch_no into list
        if batch:
            row["batch_no"].append(batch)

        # accumulate totals across all batches
        opening_qty   = o["opening_qty"]
        opening_value = o["opening_value"]
        in_qty        = m["in_qty"]
        in_value      = m["in_value"]
        out_qty       = m["out_qty"]
        out_value     = m["out_value"]
        buy_value     = m["buy_value"]
        sell_value    = m["sell_value"]
        bal_qty       = opening_qty + in_qty - out_qty
        val_rate      = m["last_valuation_rate"] or o["valuation_rate"]
        bal_val       = bal_qty * val_rate

        row["opening_qty"]    += opening_qty
        row["opening_value"]  += opening_value
        row["in_qty"]         += in_qty
        row["in_value"]       += in_value
        row["out_qty"]        += out_qty
        row["out_value"]      += out_value
        row["bal_qty"]        += bal_qty
        row["buy_value"]      += buy_value
        row["sell_value"]     += sell_value
        row["valuation_rate"]  = val_rate   # use latest
        row["bal_val"]         = round(row["bal_qty"] * val_rate, 2)

    # round final values
    result = []
    for row in items_map.values():
        row["opening_value"] = round(row["opening_value"], 2)
        row["in_value"]      = round(row["in_value"],      2)
        row["out_value"]     = round(row["out_value"],     2)
        row["buy_value"]     = round(row["buy_value"],     2)
        row["sell_value"]    = round(row["sell_value"],    2)
        # if no batches, set null
        if not row["batch_no"]:
            row["batch_no"] = None
        result.append(row)

    # ── Step 6: Pagination ────────────────────────────────────────────────────
    total_records = len(result)
    total_pages   = max(1, -(-total_records // page_size))
    start         = (page - 1) * page_size
    end           = start + page_size

    return {
        "data": result[start:end],
        "pagination": {
            "page":          page,
            "page_size":     page_size,
            "total_records": total_records,
            "total_pages":   total_pages,
            "has_next":      page < total_pages,
            "has_prev":      page > 1,
        }
    }


import frappe


@frappe.whitelist()
def get_batch_wise_stock_report(
    from_date=None,
    to_date=None,
    warehouse=None,
    item_code=None,
    item_group=None,
    batch_no=None,
    page=1,
    page_size=20,
):
    """
    Batch-Wise Stock Report — Item once, batches nested inside
    GET /api/method/custom_stock_api.api.stock.get_batch_wise_stock_report
        ?company=UDVELL THERAPEUTICS PVT LTD    (required)
        &from_date=2025-12-01                   (optional)
        &to_date=2026-03-06                     (optional)
        &warehouse=Finished Goods - RI          (optional)
        &item_code=ITEM-001                     (optional)
        &item_group=raw material                (optional)
        &batch_no=BATCH-001                     (optional)
        &page=1                                 (optional, default 1)
        &page_size=20                           (optional, default 20)
    """

    page      = int(page)
    page_size = int(page_size)

    # ── Step 1: Fetch all batches ─────────────────────────────────────────────
    batch_filters = [["disabled", "=", 0]]
    if item_code: batch_filters.append(["item", "=", item_code])
    if batch_no:  batch_filters.append(["name", "=", batch_no])

    all_batches = frappe.get_all(
        "Batch",
        filters=batch_filters,
        fields=[
            "name as batch_no",
            "item as item_code",
            "expiry_date",
            "manufacturing_date",
        ],
        limit=0,
    )

    if not all_batches:
        return {
            "data": [],
            "pagination": {
                "page": page, "page_size": page_size,
                "total_records": 0, "total_pages": 0,
                "has_next": False, "has_prev": False,
            }
        }

    # ── Step 2: Fetch item details ────────────────────────────────────────────
    all_item_codes = list({b["item_code"] for b in all_batches})

    item_details_map = {}
    if all_item_codes:
        items = frappe.get_all(
            "Item",
            filters=[["item_code", "in", all_item_codes]],
            fields=["item_code", "item_name", "item_group", "stock_uom"],
            limit=0,
        )
        for item in items:
            item_details_map[item["item_code"]] = {
                "item_name":  item["item_name"],
                "item_group": item["item_group"],
                "stock_uom":  item["stock_uom"],
            }

    # apply item_group filter
    if item_group:
        all_batches = [
            b for b in all_batches
            if item_details_map.get(b["item_code"], {}).get("item_group") == item_group
        ]

    # ── Step 3: SLE helper ────────────────────────────────────────────────────
    def get_sle(extra_filters):
        f = {
            "company":      frappe.defaults.get_global_default("company"),
            "docstatus":    1,
            "is_cancelled": 0,
        }
        if warehouse: f["warehouse"] = warehouse
        f.update(extra_filters)
        return frappe.get_all(
            "Stock Ledger Entry",
            filters=f,
            fields=[
                "item_code", "batch_no", "warehouse",
                "actual_qty", "qty_after_transaction",
                "valuation_rate", "stock_value", "stock_value_difference",
            ],
            order_by="posting_date asc, posting_time asc",
            limit=0,
        )

    # ── Step 4: Opening SLE (before from_date) ────────────────────────────────
    opening_map = {}  # (item_code, batch_no, warehouse) → opening data

    if from_date:
        for e in get_sle({"posting_date": ("<", from_date)}):
            key = (e["item_code"], e["batch_no"] or "", e["warehouse"])
            opening_map[key] = {
                "opening_qty":    e["qty_after_transaction"],
                "opening_value":  round(e["stock_value"] or 0, 2),
                "valuation_rate": e["valuation_rate"] or 0,
            }

    # ── Step 5: Movement SLE (within date range) ──────────────────────────────
    date_filter = {}
    if from_date and to_date:
        date_filter["posting_date"] = ("between", [from_date, to_date])
    elif from_date:
        date_filter["posting_date"] = (">=", from_date)
    elif to_date:
        date_filter["posting_date"] = ("<=", to_date)

    movement_map = {}  # (item_code, batch_no, warehouse) → movement data

    for e in get_sle(date_filter):
        key      = (e["item_code"], e["batch_no"] or "", e["warehouse"])
        val_diff = e["stock_value_difference"] or 0

        if key not in movement_map:
            movement_map[key] = {
                "in_qty":              0.0,
                "in_value":            0.0,
                "out_qty":             0.0,
                "out_value":           0.0,
                "buy_value":           0.0,
                "sell_value":          0.0,
                "last_valuation_rate": 0.0,
                "last_stock_value":    0.0,
                "warehouse":           e["warehouse"],
            }

        m = movement_map[key]
        m["last_valuation_rate"] = e["valuation_rate"] or 0
        m["last_stock_value"]    = e["stock_value"] or 0
        m["warehouse"]           = e["warehouse"]

        if e["actual_qty"] > 0:
            m["in_qty"]    += e["actual_qty"]
            m["in_value"]  += val_diff
            m["buy_value"] += val_diff
        else:
            m["out_qty"]    += abs(e["actual_qty"])
            m["out_value"]  += abs(val_diff)
            m["sell_value"] += abs(val_diff)

    # ── Step 6: Group batches under each item ─────────────────────────────────
    # items_map: item_code → item row with batches list
    items_map = {}

    for b in all_batches:
        code  = b["item_code"]
        batch = b["batch_no"]

        item_info = item_details_map.get(code, {
            "item_name": "", "item_group": "", "stock_uom": "",
        })

        # find warehouse for this batch
        wh = warehouse or ""
        if not wh:
            for k in movement_map:
                if k[0] == code and k[1] == batch:
                    wh = k[2]
                    break
        if not wh:
            for k in opening_map:
                if k[0] == code and k[1] == batch:
                    wh = k[2]
                    break

        key = (code, batch, wh)

        o = opening_map.get(key, {
            "opening_qty":    0.0,
            "opening_value":  0.0,
            "valuation_rate": 0.0,
        })
        m = movement_map.get(key, {
            "in_qty":              0.0,
            "in_value":            0.0,
            "out_qty":             0.0,
            "out_value":           0.0,
            "buy_value":           0.0,
            "sell_value":          0.0,
            "last_valuation_rate": 0.0,
            "last_stock_value":    0.0,
        })

        opening_qty   = o["opening_qty"]
        opening_value = o["opening_value"]
        in_qty        = m["in_qty"]
        in_value      = round(m["in_value"],   2)
        out_qty       = m["out_qty"]
        out_value     = round(m["out_value"],  2)
        buy_value     = round(m["buy_value"],  2)
        sell_value    = round(m["sell_value"], 2)
        bal_qty       = opening_qty + in_qty - out_qty
        val_rate      = m["last_valuation_rate"] or o["valuation_rate"]
        bal_val       = round(bal_qty * val_rate, 2)

        # batch row — all batch level data
        batch_row = {
            "batch_no":           batch,
            "expiry_date":        b.get("expiry_date"),
            "manufacturing_date": b.get("manufacturing_date"),
            "warehouse":          wh,
            "opening_qty":        opening_qty,
            "opening_value":      opening_value,
            "in_qty":             in_qty,
            "in_value":           in_value,
            "out_qty":            out_qty,
            "out_value":          out_value,
            "bal_qty":            bal_qty,
            "bal_val":            bal_val,
            "valuation_rate":     val_rate,
            "buy_value":          buy_value,
            "sell_value":         sell_value,
        }

        if code not in items_map:
            # create item row first time — item fields only once
            items_map[code] = {
                "item_code":  code,
                "item_name":  item_info.get("item_name",  ""),
                "item_group": item_info.get("item_group", ""),
                "stock_uom":  item_info.get("stock_uom",  ""),
                # item level totals
                "total_opening_qty":   0.0,
                "total_opening_value": 0.0,
                "total_in_qty":        0.0,
                "total_in_value":      0.0,
                "total_out_qty":       0.0,
                "total_out_value":     0.0,
                "total_bal_qty":       0.0,
                "total_bal_val":       0.0,
                "total_buy_value":     0.0,
                "total_sell_value":    0.0,
                # nested batches
                "batches": [],
            }

        row = items_map[code]
        row["batches"].append(batch_row)

        # accumulate item level totals
        row["total_opening_qty"]   += opening_qty
        row["total_opening_value"] += opening_value
        row["total_in_qty"]        += in_qty
        row["total_in_value"]      += in_value
        row["total_out_qty"]       += out_qty
        row["total_out_value"]     += out_value
        row["total_bal_qty"]       += bal_qty
        row["total_bal_val"]       += bal_val
        row["total_buy_value"]     += buy_value
        row["total_sell_value"]    += sell_value

    # round item totals
    result = []
    for row in items_map.values():
        row["total_opening_value"] = round(row["total_opening_value"], 2)
        row["total_in_value"]      = round(row["total_in_value"],      2)
        row["total_out_value"]     = round(row["total_out_value"],     2)
        row["total_bal_val"]       = round(row["total_bal_val"],       2)
        row["total_buy_value"]     = round(row["total_buy_value"],     2)
        row["total_sell_value"]    = round(row["total_sell_value"],    2)
        result.append(row)

    # ── Step 7: Pagination (item level) ──────────────────────────────────────
    total_records = len(result)
    total_pages   = max(1, -(-total_records // page_size))
    start         = (page - 1) * page_size
    end           = start + page_size

    return {
        "data": result[start:end],
        "pagination": {
            "page":          page,
            "page_size":     page_size,
            "total_records": total_records,
            "total_pages":   total_pages,
            "has_next":      page < total_pages,
            "has_prev":      page > 1,
        }
    }