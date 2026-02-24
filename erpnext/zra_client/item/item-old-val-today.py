from erpnext.zra_client.generic_api import send_response, send_response_list
from erpnext.zra_client.main import ZRAClient
from frappe import _
import random
import frappe
import json
import time
import uuid

ZRA_CLIENT_INSTANCE = ZRAClient()


def generate_item_code_random(country_code, product_type, pkg_unit, qty_unit):
    random_id = random.randint(1, 99999)
    random_id_str = str(random_id).zfill(5)
    item_code = f"{country_code}{product_type}{pkg_unit}{qty_unit}{random_id_str}"
    return item_code


def generate_group_id():
    """Auto-generate a unique ID for item groups."""
    timestamp = str(int(time.time()))[-6:]
    random_part = random.randint(100, 999)
    return f"GRP-{timestamp}-{random_part}"


def ensure_uom_exists(uom_name):
    if not uom_name:
        return send_response(status="fail", message="Quantity Unit Code is required. (unitOfMeasureCd)")

    if not frappe.db.exists("UOM", uom_name):
        uom_doc = frappe.get_doc({
            "doctype": "UOM",
            "uom_name": uom_name,
            "must_be_whole_number": 1
        })
        uom_doc.insert(ignore_permissions=True)
        frappe.db.commit()

        
def check_if_group_exists(group_name):
    group = frappe.db.exists("Item Group", group_name)
    
    if not group:
        return send_response(
            status="fail",
            message=f"Item Group '{group_name}' does not exist.",
            status_code=400,
            http_status=400
        )
    
    return True


def is_zra_sync_enabled():
    try:
        settings = frappe.get_single("ZRA Settings")
        return settings.get("enable_zra_sync", False)
    except:
        pass
    
    return frappe.conf.get("enable_zra_sync", False)


def sync_item_with_zra(payload, is_update=False):
    try:
        if is_update:
            result = ZRA_CLIENT_INSTANCE.update_item_zra_client(payload)
        else:
            result = ZRA_CLIENT_INSTANCE.create_item_zra_client(payload)
        
        response_data = result.json()
        
        if response_data.get("resultCd") != "000":
            error_msg = response_data.get("resultMsg", "Item Sync Failed")
            return False, error_msg
        
        return True, "ZRA sync successful"
    
    except Exception as e:
        frappe.log_error(message=str(e), title="ZRA Sync Error")
        return False, f"ZRA sync failed: {str(e)}"


@frappe.whitelist(allow_guest=False)
def create_item_api():
    data = frappe.form_dict
    print(data)

    item_name = (data.get("itemName") or "").strip()
    item_group = (data.get("itemGroup") or "").strip()
    unit_of_measure_cd = (data.get("unitOfMeasureCd") or "Nos").strip()
    custom_itemclscd = (data.get("itemClassCode") or "").strip()
    custom_itemtycd = data.get("itemTypeCode")
    custom_orgnnatcd = (data.get("originNationCode") or "").strip()
    custom_pkgunitcd = (data.get("packagingUnitCode") or "").strip()
    custom_svcchargeyn = (data.get("svcCharge") or "").strip()
    custom_isrcaplcbyn = (data.get("ins") or "").strip()
    brand = (data.get("brand") or "").strip()
    custom_selling_price = data.get("sellingPrice") or 0
    custom_purchase_amount = data.get("purchaseAmount") or 0
    custom_buying_price = data.get("buyingPrice") or 0
    custom_sku = data.get("sku") or ""
    custom_kg = data.get("weightUnit") or 0
    custom_vendor = data.get("preferredVendor") or ""
    custom_weight = data.get("weight") or 0
    custom_valuation = data.get("valuationMethod") or ""
    custom_is_track_inventory = data.get("custom_is_track_inventory") or False
    custom_tracking_method = data.get("trackingMethod") or "None"
    custom_reorder_level = data.get("reorderLevel") or 0
    custom_min_stock_level = data.get("minStockLevel") or 0
    custom_max_stock_level = data.get("maxStockLevel") or 0
    custom_sales_account = data.get("salesAccount") or ""
    custom_purchase_account = data.get("purchaseAccount") or ""
    custom_tax_preference = data.get("taxPreference") or ""
    custom_dimensionlength = data.get("dimensionLength") or ""
    custom_dimensionwidth = data.get("dimensionWidth") or ""
    custom_dimensionheight = data.get("dimensionHeight") or ""
    taxType = data.get("taxType")
    taxCode = data.get("taxCode")
    taxName = data.get("taxName")
    taxDescription = data.get("taxDescription")
    taxPerct = data.get("taxPerct")
    taxCategory = data.get("taxCategory")
    
    force_zra_sync = data.get("forceZraSync", False)
    zra_will_sync = is_zra_sync_enabled() or force_zra_sync
    
    if not item_name:
        return send_response(status="fail", message="Item name is required", status_code=400, http_status=400)
    
    if not item_group:
        return send_response(status="fail", message="Item group is required", status_code=400, http_status=400)
    
    if zra_will_sync:
        if not taxCategory:
            return send_response(status="error", message="taxCategory is required when ZRA sync is enabled", status_code=400, http_status=400)
        
        allowed_categories = ZRA_CLIENT_INSTANCE.getTaxCategory()
        if taxCategory not in allowed_categories:
            return send_response(status="error", message=f'taxCategory must be one of {allowed_categories}', status_code=400, http_status=400)
        
        if not custom_orgnnatcd:
            return send_response(status="fail", message="Item origin code is required when ZRA sync is enabled", status_code=400, http_status=400)
            
        if not custom_pkgunitcd:
            return send_response(status="fail", message="Item packaging unit code is required when ZRA sync is enabled", status_code=400, http_status=400)
            
        if not custom_itemclscd:
            return send_response(status="fail", message="Item classification code is required when ZRA sync is enabled", status_code=400, http_status=400)
        
        if not custom_itemtycd:
            return send_response(status="fail", message="Item type code is required when ZRA sync is enabled", status_code=400, http_status=400)
            
        if not taxCode:
            return send_response(status="fail", message="taxCode is required when ZRA sync is enabled", status_code=400, http_status=400)

        if taxCode not in ["A", "C1", "C2"]:
            return send_response(status="fail", message="taxCode must be one of A, C1, C2", status_code=400, http_status=400)
        
        if not custom_svcchargeyn:
            return send_response(status="fail", message="Service charge flag is required when ZRA sync is enabled", status_code=400, http_status=400)
        
        if not custom_isrcaplcbyn:
            return send_response(status="fail", message="Insurance applicable flag is required when ZRA sync is enabled", status_code=400, http_status=400)
    
    if not custom_selling_price:
        return send_response(status="fail", message="Selling price is required", status_code=400, http_status=400)

    if zra_will_sync:
        item_code = generate_item_code_random(custom_orgnnatcd, custom_itemtycd, custom_pkgunitcd, unit_of_measure_cd)
    else:
        timestamp = str(int(time.time()))[-6:]
        random_id = random.randint(1000, 9999)
        item_code = f"ITM-{timestamp}-{random_id}"
    
    ensure_uom_exists(unit_of_measure_cd)

    if frappe.db.exists("Item", {"item_name": item_name}):
        return send_response(status="fail", message=f"Item '{item_name}' already exists", status_code=400, http_status=400)

    itemGroup = check_if_group_exists(item_group)
    if not itemGroup:
        return send_response(status="fail", message=f"Item group '{item_group}' does not exist", status_code=400, http_status=400)

    zra_enabled = is_zra_sync_enabled() or force_zra_sync
    zra_sync_message = None
    
    if zra_enabled:
        PAYLOAD = {
            "tpin": ZRA_CLIENT_INSTANCE.get_tpin(),
            "bhfId": ZRA_CLIENT_INSTANCE.get_branch_code(),
            "itemCd": item_code,
            "itemClsCd": custom_itemclscd,
            "itemTyCd": custom_itemtycd,
            "itemNm": item_name,
            "orgnNatCd": custom_orgnnatcd,
            "pkgUnitCd": custom_pkgunitcd,
            "qtyUnitCd": unit_of_measure_cd,
            "dftPrc": custom_selling_price,
            "vatCatCd": taxCode,
            "svcChargeYn": custom_svcchargeyn,
            "sftyQty": 0,
            "isrcAplcbYn": custom_isrcaplcbyn,
            "useYn": "Y",
            "regrNm": frappe.session.user,
            "regrId": frappe.session.user,
            "modrNm": frappe.session.user,
            "modrId": frappe.session.user
        }

        print(json.dumps(PAYLOAD, indent=4))

        zra_success, zra_message = sync_item_with_zra(PAYLOAD, is_update=False)
        
        if not zra_success:
            zra_sync_message = f"Warning: ZRA sync failed - {zra_message}"
            frappe.log_error(message=zra_message, title="ZRA Sync Failed")
        else:
            zra_sync_message = "Item synced with ZRA successfully"
    else:
        zra_sync_message = "ZRA sync is disabled - item created locally only"

    try:
        if brand:
            if not frappe.db.exists("Brand", brand):
                try:
                    frappe.get_doc({"doctype": "Brand", "brand": brand}).insert(ignore_permissions=True)
                except Exception as e:
                    return send_response(status="fail", message=f"Failed to create brand '{brand}'", data={"error": str(e)}, status_code=500, http_status=500)

        item = frappe.get_doc({
            "doctype": "Item",
            "item_name": item_name,
            "item_code": item_code,
            "item_group": item_group,
            "stock_uom": unit_of_measure_cd,
            "custom_itemclscd": custom_itemclscd or "",
            "custom_itemtycd": custom_itemtycd or "",
            "custom_orgnnatcd": custom_orgnnatcd or "",
            "custom_pkgunitcd": custom_pkgunitcd or "",
            "custom_svcchargeyn": custom_svcchargeyn or "N",
            "custom_isrcaplcbyn": custom_isrcaplcbyn or "N",
            "is_stock_item": 1,
            "brand": brand,
            "standard_rate": custom_selling_price,
            "custom_purchase_amount": custom_purchase_amount,
            "custom_buying_price": custom_buying_price,
            "custom_suk": custom_sku,
            "custom_kg": custom_kg,
            "custom_vendor": custom_vendor,
            "custom_tax_type": taxType or "",
            "custom_tax_code": taxCode or "",
            "custom_tax_name": taxName or "",
            "custom_tax_description": taxDescription or "",
            "custom_tax_perct": taxPerct or 0,
            "custom_weight": custom_weight,
            "custom_valuation": custom_valuation,
            "custom_is_track_inventory": custom_is_track_inventory,
            "custom_tracking_method": custom_tracking_method,
            "custom_reorder_level": custom_reorder_level,
            "custom_min_stock_level": custom_min_stock_level,
            "custom_max_stock_level": custom_max_stock_level,
            "custom_sales_account": custom_sales_account,
            "custom_purchase_account": custom_purchase_account,
            "custom_tax_preference": custom_tax_preference,
            "custom_dimensionlength": custom_dimensionlength,
            "custom_dimensionwidth": custom_dimensionwidth,
            "custom_dimensionheight": custom_dimensionheight,
            "custom_tax_category": taxCategory or "",
        })
        item.insert(ignore_permissions=True)
        frappe.db.commit()

        success_message = f"Item '{item_name}' created successfully"
        if zra_sync_message:
            success_message += f". {zra_sync_message}"

        return send_response(status="success", message=success_message, status_code=201, http_status=201)

    except Exception as e:
        frappe.log_error(message=str(e), title="Create Item API Error")
        return send_response(status="fail", message="Failed to create item", data={"error": str(e)}, status_code=500, http_status=500)


# @frappe.whitelist(allow_guest=False)
# def get_all_items_api():
#     try:
#         args = frappe.request.args

#         page = args.get("page")
#         if not page:
#             return send_response(status="error", message="'page' parameter is required.", data=None, status_code=400, http_status=400)

#         try:
#             page = int(page)
#             if page < 1:
#                 raise ValueError
#         except ValueError:
#             return send_response(status="error", message="'page' must be a positive integer.", data=None, status_code=400, http_status=400)

#         page_size = args.get("page_size")
#         if not page_size:
#             return send_response(status="error", message="'page_size' parameter is required.", data=None, status_code=400, http_status=400)

#         try:
#             page_size = int(page_size)
#             if page_size < 1:
#                 raise ValueError
#         except ValueError:
#             return send_response(status="error", message="'page_size' must be a positive integer.", data=None, status_code=400, http_status=400)

#         start = (page - 1) * page_size
#         end = start + page_size

#         tax_category = args.get("taxCategory")
#         filters = {"disabled": 0}
#         if tax_category:
#             filters["custom_tax_category"] = tax_category

#         all_items = frappe.get_all(
#             "Item",
#             fields=[
#                 "item_code", "item_name", "item_group", "stock_uom",
#                 "standard_rate", "custom_itemclscd", "custom_vendor",
#                 "custom_tax_category", "custom_min_stock_level", "custom_max_stock_level",
#             ],
#             filters=filters,
#             order_by="creation desc"
#         )

#         total_items = len(all_items)

#         if total_items == 0:
#             return send_response(status="success", message="No items found.", data=[], status_code=200, http_status=200)

#         items = all_items[start:end]
#         for it in items:
#             it["id"] = it.pop("item_code")
#             it["itemName"] = it.pop("item_name")
#             it["itemGroup"] = it.pop("item_group")
#             it["itemClassCode"] = it.pop("custom_itemclscd")
#             it["unitOfMeasureCd"] = it.pop("stock_uom")
#             it["sellingPrice"] = it.pop("standard_rate")
#             it["preferredVendor"] = it.pop("custom_vendor")
#             it["minStockLevel"] = it.pop("custom_min_stock_level")
#             it["maxStockLevel"] = it.pop("custom_max_stock_level")
#             it["taxCategory"] = it.pop("custom_tax_category")

#         total_pages = (total_items + page_size - 1) // page_size

#         response_data = {
#             "success": True,
#             "message": "Items retrieved successfully",
#             "data": items,
#             "pagination": {
#                 "page": page,
#                 "page_size": page_size,
#                 "total": total_items,
#                 "total_pages": total_pages,
#                 "has_next": page < total_pages,
#                 "has_prev": page > 1
#             }
#         }

#         return send_response_list(status="success", message="Items retrieved successfully", status_code=200, data=response_data, http_status=200)

#     except Exception as e:
#         frappe.log_error(message=str(e), title="Get All Items API Error")
#         return send_response(status="fail", message="Failed to fetch items", data={"error": str(e)}, status_code=500, http_status=500)



@frappe.whitelist(allow_guest=False)
def get_all_items_api():
    try:
        args = frappe.request.args

        page = args.get("page")
        if not page:
            return send_response(status="error", message="'page' parameter is required.", data=None, status_code=400, http_status=400)
        try:
            page = int(page)
            if page < 1:
                raise ValueError
        except ValueError:
            return send_response(status="error", message="'page' must be a positive integer.", data=None, status_code=400, http_status=400)

        page_size = args.get("page_size")
        if not page_size:
            return send_response(status="error", message="'page_size' parameter is required.", data=None, status_code=400, http_status=400)
        try:
            page_size = int(page_size)
            if page_size < 1:
                raise ValueError
        except ValueError:
            return send_response(status="error", message="'page_size' must be a positive integer.", data=None, status_code=400, http_status=400)

        start = (page - 1) * page_size
        end = start + page_size

        # ── Filters ───────────────────────────────────────────────────────────
        tax_category = args.get("taxCategory")
        item_group   = args.get("itemGroup")
        search       = args.get("search")

        filters = {"disabled": 0}
        if tax_category:
            filters["custom_tax_category"] = tax_category
        if item_group:
            filters["item_group"] = item_group

        # ── Fetch all matching items ───────────────────────────────────────────
        all_items = frappe.get_all(
            "Item",
            fields=[
                # Core
                "item_code", "item_name", "item_group", "stock_uom",
                "standard_rate", "custom_buying_price", "brand", "description",
                # Classification
                "custom_itemclscd", "custom_itemtycd", "custom_orgnnatcd", "custom_pkgunitcd",
                "custom_svcchargeyn", "custom_isrcaplcbyn",
                # Physical
                "custom_suk", "custom_weight", "custom_kg",
                "custom_dimensionlength", "custom_dimensionwidth", "custom_dimensionheight",
                # Vendor
                "custom_vendor", "custom_sales_account", "custom_purchase_account",
                # Tax
                "custom_tax_category", "custom_tax_preference", "custom_tax_type",
                "custom_tax_code", "custom_tax_name", "custom_tax_perct",
                # Inventory
                "custom_valuation", "custom_tracking_method",
                "custom_reorder_level", "custom_min_stock_level", "custom_max_stock_level",
                # Batch
                "has_batch_no", "has_expiry_date", "shelf_life_in_days",
            ],
            filters=filters,
            order_by="creation desc"
        )

        # ── Optional search filter (item_name contains) ───────────────────────
        if search:
            search_lower = search.lower()
            all_items = [
                it for it in all_items
                if search_lower in (it.get("item_name") or "").lower()
                or search_lower in (it.get("item_code") or "").lower()
            ]

        total_items = len(all_items)

        if total_items == 0:
            return send_response(status="success", message="No items found.", data=[], status_code=200, http_status=200)

        # ── Paginate ──────────────────────────────────────────────────────────
        paged_items = all_items[start:end]

        # ── Reshape each item ─────────────────────────────────────────────────
        formatted = []
        for it in paged_items:
            formatted.append({
                # Core
                "id":               it.get("item_code", ""),
                "itemName":         it.get("item_name", ""),
                "itemGroup":        it.get("item_group", ""),
                "itemClassCode":    it.get("custom_itemclscd", ""),
                "itemTypeCode":     it.get("custom_itemtycd", ""),
                "originNationCode": it.get("custom_orgnnatcd", ""),
                "packagingUnitCode":it.get("custom_pkgunitcd", ""),
                "svcCharge":        it.get("custom_svcchargeyn", "N"),
                "ins":              it.get("custom_isrcaplcbyn", "N"),
                "unitOfMeasureCd":  it.get("stock_uom", ""),
                "sellingPrice":     it.get("standard_rate", 0),
                "buyingPrice":      it.get("custom_buying_price", 0),
                "sku":              it.get("custom_suk", ""),
                "brand":            it.get("brand", ""),
                "description":      it.get("description", ""),
                "weight":           it.get("custom_weight", ""),
                "weightUnit":       it.get("custom_kg", ""),
                "dimensionLength":  it.get("custom_dimensionlength", ""),
                "dimensionWidth":   it.get("custom_dimensionwidth", ""),
                "dimensionHeight":  it.get("custom_dimensionheight", ""),

                # Vendor
                "vendorInfo": {
                    "preferredVendor":  it.get("custom_vendor", ""),
                    "salesAccount":     it.get("custom_sales_account", ""),
                    "purchaseAccount":  it.get("custom_purchase_account", ""),
                },

                # Tax
                "taxInfo": {
                    "taxCategory":   it.get("custom_tax_category", ""),
                    "taxPreference": it.get("custom_tax_preference", ""),
                    "taxType":       it.get("custom_tax_type", ""),
                    "taxCode":       it.get("custom_tax_code", ""),
                    "taxName":       it.get("custom_tax_name", ""),
                    "taxPerct":      it.get("custom_tax_perct", 0),
                },

                # Inventory
                "inventoryInfo": {
                    "valuationMethod": it.get("custom_valuation", ""),
                    "trackingMethod":  it.get("custom_tracking_method", "None"),
                    "reorderLevel":    it.get("custom_reorder_level", 0),
                    "minStockLevel":   it.get("custom_min_stock_level", 0),
                    "maxStockLevel":   it.get("custom_max_stock_level", 0),
                },

                # Batch (summary flags only for list view)
                "batchInfo": {
                    "has_batch_no":    bool(it.get("has_batch_no", False)),
                    "has_expiry_date": bool(it.get("has_expiry_date", False)),
                    "shelfLifeInDays": it.get("shelf_life_in_days", 0),
                },
            })

        total_pages = (total_items + page_size - 1) // page_size

        response_data = {
            "data": formatted,
            "pagination": {
                "page":        page,
                "page_size":   page_size,
                "total":       total_items,
                "total_pages": total_pages,
                "has_next":    page < total_pages,
                "has_prev":    page > 1
            }
        }

        return send_response_list(
            status="success",
            message="Items retrieved successfully",
            status_code=200,
            data=response_data,
            http_status=200
        )

    except Exception as e:
        frappe.log_error(message=str(e), title="Get All Items API Error")
        return send_response(status="fail", message="Failed to fetch items", data={"error": str(e)}, status_code=500, http_status=500)


# @frappe.whitelist(allow_guest=False)
# def get_item_by_id_api():
#     item_code = (frappe.form_dict.get("id") or "").strip()
#     if not item_code:
#         return send_response(status="fail", message="item_code is required", status_code=400, http_status=400)

#     try:
#         items = frappe.get_all(
#             "Item",
#             filters={"item_code": item_code},
#             fields=[
#                 "name", "item_code", "item_name", "item_group", "stock_uom",
#                 "standard_rate", "custom_itemclscd", "custom_itemtycd",
#                 "custom_orgnnatcd", "custom_pkgunitcd", "custom_svcchargeyn",
#                 "custom_isrcaplcbyn", "custom_selling_price", "custom_purchase_amount",
#                 "standard_rate", "custom_buying_price", "custom_suk", "custom_vendor",
#                 "custom_tax_type", "custom_tax_code", "custom_tax_name",
#                 "custom_tax_description", "custom_tax_perct", "custom_dimension",
#                 "custom_weight", "custom_valuation", "custom_is_track_inventory",
#                 "custom_tracking_method", "custom_reorder_level", "custom_min_stock_level",
#                 "custom_max_stock_level", "custom_sales_account", "custom_purchase_account",
#                 "brand", "custom_kg", "description", "custom_tax_preference",
#                 "custom_dimensionlength", "custom_dimensionwidth", "custom_dimensionheight",
#                 "custom_tax_category",
#             ],
#             limit_page_length=1
#         )

#         if not items:
#             return send_response(status="fail", message=f"Item with code '{item_code}' not found", status_code=404, http_status=404)

#         it = items[0]
#         data = {
#             "id": it.pop("item_code", ""),
#             "itemName": it.pop("item_name", ""),
#             "itemGroup": it.pop("item_group", ""),
#             "itemClassCode": it.pop("custom_itemclscd", ""),
#             "itemTypeCode": it.pop("custom_itemtycd", 0),
#             "originNationCode": it.pop("custom_orgnnatcd", ""),
#             "packagingUnitCode": it.pop("custom_pkgunitcd", ""),
#             "svcCharge": it.pop("custom_svcchargeyn", "Y"),
#             "ins": it.pop("custom_isrcaplcbyn", "Y"),
#             "sellingPrice": it.pop("standard_rate", 0),
#             "buyingPrice": int(it.pop("custom_buying_price", 0)),
#             "unitOfMeasureCd": it.pop("stock_uom", "U"),
#             "sku": it.pop("custom_suk", ""),
#             "taxPreference": it.pop("custom_tax_preference", ""),
#             "preferredVendor": it.pop("custom_vendor", ""),
#             "salesAccount": it.pop("custom_sales_account", ""),
#             "purchaseAccount": it.pop("custom_purchase_account", ""),
#             "taxType": it.pop("custom_tax_type"),
#             "taxCode": it.pop("custom_tax_code"),
#             "taxName": it.pop("custom_tax_name"),
#             "taxDescription": it.pop("custom_tax_description"),
#             "taxPerct": it.pop("custom_tax_perct"),
#             "dimensionUnit": it.pop("custom_dimension", ""),
#             "weight": it.pop("custom_weight", ""),
#             "valuationMethod": it.pop("custom_valuation", ""),
#             "trackingMethod": it.pop("custom_tracking_method", "None"),
#             "reorderLevel": it.pop("custom_reorder_level", 0),
#             "minStockLevel": it.pop("custom_min_stock_level", 0),
#             "maxStockLevel": it.pop("custom_max_stock_level", 0),
#             "brand": it.pop("brand", ""),
#             "description": it.pop("description", ""),
#             "weightUnit": it.pop("custom_kg", ""),
#             "dimensionLength": it.pop("custom_dimensionlength", ""),
#             "dimensionWidth": it.pop("custom_dimensionwidth", ""),
#             "dimensionHeight": it.pop("custom_dimensionheight", ""),
#             "taxCategory": it.pop("custom_tax_category", ""),
#         }

#         return send_response(status="success", message=f"Item '{item_code}' fetched successfully", data=data, status_code=200, http_status=200)

#     except Exception as e:
#         frappe.log_error(message=str(e), title="Get Item By ID API Error")
#         return send_response(status="fail", message="Failed to fetch item", data={"error": str(e)}, status_code=500, http_status=500)


@frappe.whitelist(allow_guest=False)
def get_item_by_id_api():
    item_code = (frappe.form_dict.get("id") or "").strip()
    if not item_code:
        return send_response(status="fail", message="item_code is required", status_code=400, http_status=400)

    try:
        items = frappe.get_all(
            "Item",
            filters={"item_code": item_code},
            fields=[
                # Core
                "name", "item_code", "item_name", "item_group", "stock_uom",
                "standard_rate", "description", "brand",
                # ZRA / Classification
                "custom_itemclscd", "custom_itemtycd", "custom_orgnnatcd",
                "custom_pkgunitcd", "custom_svcchargeyn", "custom_isrcaplcbyn",
                # Pricing
                "custom_purchase_amount", "custom_buying_price",
                # Physical
                "custom_suk", "custom_kg", "custom_weight", "custom_dimension",
                "custom_dimensionlength", "custom_dimensionwidth", "custom_dimensionheight",
                # Valuation / Tracking
                "custom_valuation", "custom_is_track_inventory", "custom_tracking_method",
                "custom_reorder_level", "custom_min_stock_level", "custom_max_stock_level",
                # Accounts
                "custom_vendor", "custom_sales_account", "custom_purchase_account",
                # Tax
                "custom_tax_type", "custom_tax_code", "custom_tax_name",
                "custom_tax_description", "custom_tax_perct", "custom_tax_preference",
                "custom_tax_category",
                # Batch
                "has_batch_no", "create_new_batch", "batch_number_series",
                "has_expiry_date", "shelf_life_in_days", "end_of_life",
                # Custom batch fields
                "custom_batch_no", "custom_manufacturing_date",
            ],
            limit_page_length=1
        )

        if not items:
            return send_response(
                status="fail",
                message=f"Item with code '{item_code}' not found",
                status_code=404,
                http_status=404
            )

        it = items[0]

        data = {
            # ── Core ──────────────────────────────────────────────────────────
            "id":               it.get("item_code", ""),
            "itemName":         it.get("item_name", ""),
            "itemGroup":        it.get("item_group", ""),
            "itemClassCode":    it.get("custom_itemclscd", ""),
            "itemTypeCode":     it.get("custom_itemtycd", ""),
            "originNationCode": it.get("custom_orgnnatcd", ""),
            "packagingUnitCode":it.get("custom_pkgunitcd", ""),
            "svcCharge":        it.get("custom_svcchargeyn", "N"),
            "ins":              it.get("custom_isrcaplcbyn", "N"),
            "unitOfMeasureCd":  it.get("stock_uom", ""),
            "sellingPrice":     it.get("standard_rate", 0),
            "buyingPrice":      it.get("custom_buying_price", 0),
            "sku":              it.get("custom_suk", ""),
            "description":      it.get("description", ""),
            "brand":            it.get("brand", ""),
            "weight":           it.get("custom_weight", ""),
            "weightUnit":       it.get("custom_kg", ""),
            "dimensionUnit":    it.get("custom_dimension", ""),
            "dimensionLength":  it.get("custom_dimensionlength", ""),
            "dimensionWidth":   it.get("custom_dimensionwidth", ""),
            "dimensionHeight":  it.get("custom_dimensionheight", ""),

            # ── Vendor / Accounts ─────────────────────────────────────────────
            "vendorInfo": {
                "preferredVendor":  it.get("custom_vendor", ""),
                "salesAccount":     it.get("custom_sales_account", ""),
                "purchaseAccount":  it.get("custom_purchase_account", ""),
            },

            # ── Tax ───────────────────────────────────────────────────────────
            "taxInfo": {
                "taxCategory":    it.get("custom_tax_category", ""),
                "taxPreference":  it.get("custom_tax_preference", ""),
                "taxType":        it.get("custom_tax_type", ""),
                "taxCode":        it.get("custom_tax_code", ""),
                "taxName":        it.get("custom_tax_name", ""),
                "taxDescription": it.get("custom_tax_description", ""),
                "taxPerct":       it.get("custom_tax_perct", 0),
            },

            # ── Inventory ─────────────────────────────────────────────────────
            "inventoryInfo": {
                "valuationMethod":  it.get("custom_valuation", ""),
                "trackingMethod":   it.get("custom_tracking_method", "None"),
                "reorderLevel":     it.get("custom_reorder_level", 0),
                "minStockLevel":    it.get("custom_min_stock_level", 0),
                "maxStockLevel":    it.get("custom_max_stock_level", 0),
            },

            # ── Batch ─────────────────────────────────────────────────────────
            "batchInfo": {
                "has_batch_no":        bool(it.get("has_batch_no", False)),
                "create_new_batch":    bool(it.get("create_new_batch", False)),
                "batchNo":             it.get("custom_batch_no", ""),
                "has_expiry_date":     bool(it.get("has_expiry_date", False)),
                "shelfLifeInDays":     it.get("shelf_life_in_days", 0),
                "endOfLife":           str(it.get("end_of_life", "")) if it.get("end_of_life") else "",
                "manufacturingDate":   str(it.get("custom_manufacturing_date", "")) if it.get("custom_manufacturing_date") else "",
            },
        }

        return send_response(
            status="success",
            message=f"Item '{item_code}' fetched successfully",
            data=data,
            status_code=200,
            http_status=200
        )

    except Exception as e:
        frappe.log_error(message=str(e), title="Get Item By ID API Error")
        return send_response(
            status="fail",
            message="Failed to fetch item",
            data={"error": str(e)},
            status_code=500,
            http_status=500
        )


@frappe.whitelist(allow_guest=False, methods=["DELETE"])
def delete_item_by_id():
    item_code = frappe.local.request.args.get("id")
    if not item_code:
        return send_response(status="fail", message="item id is required", status_code=400, http_status=400)

    try:
        item = frappe.get_doc("Item", {"item_code": item_code})
    except frappe.DoesNotExistError:
        return send_response(status="fail", message=f"Item with id '{item_code}' does not exist", status_code=404, http_status=404)

    try:
        item.delete()
        frappe.db.commit()
        return send_response(status="success", message=f"Item '{item_code}' deleted successfully", status_code=200, http_status=200)
    except Exception as e:
        frappe.log_error(message=str(e), title="Delete Item API Error")
        return send_response(status="fail", message="Failed to delete item", status_code=500, http_status=500)


# @frappe.whitelist(allow_guest=False, methods=["PUT"])
# def update_item_api():
#     data = frappe.form_dict

#     item_code = (data.get("id") or "").strip()
#     if not item_code:
#         return send_response(status="fail", message="Item ID (item_code) is required", status_code=400, http_status=400)

#     if not frappe.db.exists("Item", {"item_code": item_code}):
#         return send_response(status="fail", message=f"Item with code '{item_code}' does not exist", status_code=404, http_status=404)

#     item = frappe.get_doc("Item", {"item_code": item_code})
#     item_name = (data.get("itemName") or item.item_name).strip()
#     item_group = (data.get("itemGroup") or item.item_group).strip()
#     unit_of_measure_cd = (data.get("unitOfMeasureCd") or item.stock_uom).strip()
#     description = (data.get("description") or item.description).strip()
#     brand = (data.get("brand") or item.brand or "").strip()
#     custom_itemclscd = (data.get("itemClassCode") or item.custom_itemclscd).strip()
#     custom_itemtycd = data.get("itemTypeCode") or item.custom_itemtycd
#     custom_orgnnatcd = (data.get("originNationCode") or item.custom_orgnnatcd).strip()
#     custom_pkgunitcd = (data.get("packagingUnitCode") or item.custom_pkgunitcd).strip()
#     custom_svcchargeyn = (data.get("svcCharge") or item.custom_svcchargeyn).strip()
#     custom_isrcaplcbyn = (data.get("ins") or item.custom_isrcaplcbyn).strip()
#     custom_selling_price = data.get("sellingPrice") or item.standard_rate
#     custom_buying_price = data.get("buyingPrice") or item.custom_buying_price
#     custom_sku = data.get("sku") or item.custom_suk
#     custom_dimension_unit = data.get("dimensionUnit") or item.custom_dimension
#     custom_weight = data.get("weight") or item.custom_weight
#     custom_valuation = data.get("valuationMethod") or item.custom_valuation
#     custom_vendor = data.get("preferredVendor") or item.custom_vendor
#     custom_kg = data.get("weightUnit") or item.custom_kg
#     custom_is_track_inventory = data.get("custom_is_track_inventory") or item.custom_is_track_inventory
#     custom_tracking_method = (data.get("trackingMethod") or item.custom_tracking_method).strip()
#     custom_sales_account = (data.get("salesAccount") or item.custom_sales_account).strip()
#     custom_purchase_account = (data.get("purchaseAccount") or item.custom_purchase_account).strip()
#     custom_min_stock_level = (data.get("minStockLevel") or item.custom_min_stock_level)
#     custom_max_stock_level = (data.get("maxStockLevel") or item.custom_max_stock_level)
#     custom_reorder_level = (data.get("reorderLevel") or item.custom_reorder_level)
#     custom_tax_preference = (data.get("taxPreference") or item.custom_tax_preference).strip()
#     custom_dimensionlength = data.get("dimensionLength") or item.custom_dimensionlength
#     custom_dimensionwidth = data.get("dimensionWidth") or item.custom_dimensionwidth
#     custom_dimensionheight = data.get("dimensionHeight") or item.custom_dimensionheight
#     taxType = data.get("taxType") or item.custom_tax_type
#     taxCode = data.get("taxCode") or item.custom_tax_code
#     taxName = data.get("taxName") or item.custom_tax_name
#     taxDescription = data.get("taxDescription") or item.custom_tax_description
#     taxPerct = data.get("taxPerct") or item.custom_tax_perct
#     taxCategory = data.get("taxCategory") or item.custom_tax_category

#     force_zra_sync = data.get("forceZraSync", False)
#     zra_will_sync = is_zra_sync_enabled() or force_zra_sync

#     if zra_will_sync:
#         if taxCode and taxCode not in ["A", "C1", "C2"]:
#             return send_response(status="fail", message="taxCode must be one of A, C1, C2", status_code=400, http_status=400)
        
#         allowed_categories = ZRA_CLIENT_INSTANCE.getTaxCategory()
#         if taxCategory and taxCategory not in allowed_categories:
#             return send_response(status="error", message=f"taxCategory must be one of {allowed_categories}", status_code=400, http_status=400)

#     ensure_uom_exists(unit_of_measure_cd)
#     exists = check_if_group_exists(item_group)
#     if exists is not True:
#         return exists

#     if brand and not frappe.db.exists("Brand", brand):
#         try:
#             frappe.get_doc({"doctype": "Brand", "brand": brand}).insert(ignore_permissions=True)
#         except Exception as e:
#             return send_response(status="fail", message=f"Failed to create brand '{brand}'", data={"error": str(e)}, status_code=500)

#     zra_sync_message = None

#     if zra_will_sync:
#         PAYLOAD = {
#             "tpin": ZRA_CLIENT_INSTANCE.get_tpin(),
#             "bhfId": ZRA_CLIENT_INSTANCE.get_branch_code(),
#             "itemCd": item_code,
#             "itemClsCd": custom_itemclscd,
#             "itemTyCd": custom_itemtycd,
#             "itemNm": item_name,
#             "orgnNatCd": custom_orgnnatcd,
#             "pkgUnitCd": custom_pkgunitcd,
#             "qtyUnitCd": unit_of_measure_cd,
#             "dftPrc": custom_selling_price,
#             "vatCatCd": taxCode,
#             "svcChargeYn": custom_svcchargeyn,
#             "isrcAplcbYn": custom_isrcaplcbyn,
#             "useYn": "Y",
#             "regrNm": frappe.session.user,
#             "regrId": frappe.session.user,
#             "modrNm": frappe.session.user,
#             "modrId": frappe.session.user
#         }
#         print(json.dumps(PAYLOAD, indent=4))

#         zra_success, zra_message = sync_item_with_zra(PAYLOAD, is_update=True)

#         if not zra_success:
#             zra_sync_message = f"Warning: ZRA sync failed - {zra_message}"
#             frappe.log_error(message=zra_message, title="ZRA Update Sync Failed")
#         else:
#             zra_sync_message = "Item synced with ZRA successfully"
#     else:
#         zra_sync_message = "ZRA sync is disabled - item updated locally only"

#     try:
#         item.update({
#             "item_name": item_name,
#             "item_group": item_group,
#             "stock_uom": unit_of_measure_cd,
#             "brand": brand,
#             "description": description,
#             "custom_itemclscd": custom_itemclscd or "",
#             "custom_itemtycd": custom_itemtycd or "",
#             "custom_orgnnatcd": custom_orgnnatcd or "",
#             "custom_pkgunitcd": custom_pkgunitcd or "",
#             "custom_svcchargeyn": custom_svcchargeyn or "N",
#             "custom_isrcaplcbyn": custom_isrcaplcbyn or "N",
#             "standard_rate": custom_selling_price,
#             "custom_buying_price": custom_buying_price,
#             "custom_suk": custom_sku,
#             "custom_dimension": custom_dimension_unit,
#             "custom_weight": custom_weight,
#             "custom_valuation": custom_valuation,
#             "custom_vendor": custom_vendor,
#             "custom_kg": custom_kg,
#             "custom_tax_type": taxType or "",
#             "custom_tax_code": taxCode or "",
#             "custom_tax_name": taxName or "",
#             "custom_tax_description": taxDescription or "",
#             "custom_tax_perct": taxPerct or 0,
#             "custom_is_track_inventory": custom_is_track_inventory,
#             "custom_tracking_method": custom_tracking_method,
#             "custom_sales_account": custom_sales_account,
#             "custom_purchase_account": custom_purchase_account,
#             "custom_reorder_level": custom_reorder_level,
#             "custom_min_stock_level": custom_min_stock_level,
#             "custom_max_stock_level": custom_max_stock_level,
#             "custom_tax_preference": custom_tax_preference,
#             "custom_dimensionlength": custom_dimensionlength,
#             "custom_dimensionwidth": custom_dimensionwidth,
#             "custom_dimensionheight": custom_dimensionheight,
#             "custom_tax_category": taxCategory or ""
#         })

#         item.save(ignore_permissions=True)
#         frappe.db.commit()

#         success_message = f"Item '{item_name}' updated successfully"
#         if zra_sync_message:
#             success_message += f". {zra_sync_message}"

#         return send_response(status="success", message=success_message, status_code=200, http_status=200)

#     except Exception as e:
#         frappe.log_error(message=str(e), title="Update Item ERP Error")
#         return send_response(status="fail", message="Failed to update item in ERPNext", data={"error": str(e)}, status_code=500, http_status=500)


@frappe.whitelist(allow_guest=False, methods=["PUT"])
def update_item_api():
    data = frappe.form_dict

    item_code = (data.get("id") or "").strip()
    if not item_code:
        return send_response(status="fail", message="Item ID (item_code) is required", status_code=400, http_status=400)

    if not frappe.db.exists("Item", {"item_code": item_code}):
        return send_response(status="fail", message=f"Item with code '{item_code}' does not exist", status_code=404, http_status=404)

    item = frappe.get_doc("Item", {"item_code": item_code})

    # ── Parse nested objects (support both flat and nested payloads) ──────────
    vendor_info      = data.get("vendorInfo") or {}
    tax_info         = data.get("taxInfo") or {}
    inventory_info   = data.get("inventoryInfo") or {}
    batch_info       = data.get("batchInfo") or {}

    # If the request comes as JSON string (frappe.form_dict flattens JSON body),
    # parse them manually
    if isinstance(vendor_info, str):
        vendor_info = json.loads(vendor_info)
    if isinstance(tax_info, str):
        tax_info = json.loads(tax_info)
    if isinstance(inventory_info, str):
        inventory_info = json.loads(inventory_info)
    if isinstance(batch_info, str):
        batch_info = json.loads(batch_info)

    # ── Core fields ───────────────────────────────────────────────────────────
    item_name           = (data.get("itemName")         or item.item_name).strip()
    item_group          = (data.get("itemGroup")         or item.item_group).strip()
    unit_of_measure_cd  = (data.get("unitOfMeasureCd")  or item.stock_uom).strip()
    description         = (data.get("description")      or item.description or "").strip()
    brand               = (data.get("brand")             or item.brand or "").strip()
    custom_itemclscd    = (data.get("itemClassCode")     or item.custom_itemclscd or "").strip()
    custom_itemtycd     = data.get("itemTypeCode")       or item.custom_itemtycd
    custom_orgnnatcd    = (data.get("originNationCode")  or item.custom_orgnnatcd or "").strip()
    custom_pkgunitcd    = (data.get("packagingUnitCode") or item.custom_pkgunitcd or "").strip()
    custom_svcchargeyn  = (data.get("svcCharge")         or item.custom_svcchargeyn or "N").strip()
    custom_isrcaplcbyn  = (data.get("ins")               or item.custom_isrcaplcbyn or "N").strip()
    custom_selling_price= data.get("sellingPrice")       or item.standard_rate
    custom_buying_price = data.get("buyingPrice")        or item.custom_buying_price
    custom_sku          = data.get("sku")                or item.custom_suk
    custom_dimension_unit = data.get("dimensionUnit")   or item.custom_dimension
    custom_weight       = data.get("weight")             or item.custom_weight
    custom_kg           = data.get("weightUnit")         or item.custom_kg
    custom_dimensionlength = data.get("dimensionLength") or item.custom_dimensionlength
    custom_dimensionwidth  = data.get("dimensionWidth")  or item.custom_dimensionwidth
    custom_dimensionheight = data.get("dimensionHeight") or item.custom_dimensionheight

    # ── Vendor info (nested preferred, flat fallback) ─────────────────────────
    custom_vendor           = vendor_info.get("preferredVendor")  or data.get("preferredVendor")  or item.custom_vendor or ""
    custom_sales_account    = vendor_info.get("salesAccount")     or data.get("salesAccount")     or item.custom_sales_account or ""
    custom_purchase_account = vendor_info.get("purchaseAccount")  or data.get("purchaseAccount")  or item.custom_purchase_account or ""

    # ── Tax info (nested preferred, flat fallback) ────────────────────────────
    taxCategory     = tax_info.get("taxCategory")    or data.get("taxCategory")    or item.custom_tax_category or ""
    custom_tax_pref = tax_info.get("taxPreference")  or data.get("taxPreference")  or item.custom_tax_preference or ""
    taxType         = tax_info.get("taxType")        or data.get("taxType")        or item.custom_tax_type or ""
    taxCode         = tax_info.get("taxCode")        or data.get("taxCode")        or item.custom_tax_code or ""
    taxName         = tax_info.get("taxName")        or data.get("taxName")        or item.custom_tax_name or ""
    taxDescription  = tax_info.get("taxDescription") or data.get("taxDescription") or item.custom_tax_description or ""
    taxPerct        = tax_info.get("taxPerct")       or data.get("taxPerct")       or item.custom_tax_perct or 0

    # ── Inventory info (nested preferred, flat fallback) ──────────────────────
    custom_valuation        = inventory_info.get("valuationMethod") or data.get("valuationMethod") or item.custom_valuation or ""
    custom_tracking_method  = (inventory_info.get("trackingMethod") or data.get("trackingMethod")  or item.custom_tracking_method or "None").strip()
    custom_reorder_level    = inventory_info.get("reorderLevel")    or data.get("reorderLevel")    or item.custom_reorder_level or 0
    custom_min_stock_level  = inventory_info.get("minStockLevel")   or data.get("minStockLevel")   or item.custom_min_stock_level or 0
    custom_max_stock_level  = inventory_info.get("maxStockLevel")   or data.get("maxStockLevel")   or item.custom_max_stock_level or 0

    # ── Batch info (nested preferred, flat fallback) ──────────────────────────
    has_batch_no        = batch_info.get("has_batch_no")        if "has_batch_no"        in batch_info else item.has_batch_no
    create_new_batch    = batch_info.get("create_new_batch")    if "create_new_batch"    in batch_info else item.create_new_batch
    custom_batch_no     = batch_info.get("batchNo")             or item.get("custom_batch_no") or ""
    has_expiry_date     = batch_info.get("has_expiry_date")     if "has_expiry_date"     in batch_info else item.has_expiry_date
    shelf_life_in_days  = batch_info.get("shelfLifeInDays")     or item.shelf_life_in_days or 0
    end_of_life         = batch_info.get("endOfLife")           or str(item.end_of_life) if item.end_of_life else ""
    custom_mfg_date     = batch_info.get("manufacturingDate")   or item.get("custom_manufacturing_date") or ""

    # ── ZRA sync validation ───────────────────────────────────────────────────
    force_zra_sync = data.get("forceZraSync", False)
    zra_will_sync = is_zra_sync_enabled() or force_zra_sync

    if zra_will_sync:
        if taxCode and taxCode not in ["A", "C1", "C2"]:
            return send_response(status="fail", message="taxCode must be one of A, C1, C2", status_code=400, http_status=400)

        allowed_categories = ZRA_CLIENT_INSTANCE.getTaxCategory()
        if taxCategory and taxCategory not in allowed_categories:
            return send_response(status="error", message=f"taxCategory must be one of {allowed_categories}", status_code=400, http_status=400)

    # ── Pre-save checks ───────────────────────────────────────────────────────
    ensure_uom_exists(unit_of_measure_cd)
    exists = check_if_group_exists(item_group)
    if exists is not True:
        return exists

    if brand and not frappe.db.exists("Brand", brand):
        try:
            frappe.get_doc({"doctype": "Brand", "brand": brand}).insert(ignore_permissions=True)
        except Exception as e:
            return send_response(status="fail", message=f"Failed to create brand '{brand}'", data={"error": str(e)}, status_code=500)

    # ── ZRA sync ──────────────────────────────────────────────────────────────
    zra_sync_message = None

    if zra_will_sync:
        PAYLOAD = {
            "tpin":         ZRA_CLIENT_INSTANCE.get_tpin(),
            "bhfId":        ZRA_CLIENT_INSTANCE.get_branch_code(),
            "itemCd":       item_code,
            "itemClsCd":    custom_itemclscd,
            "itemTyCd":     custom_itemtycd,
            "itemNm":       item_name,
            "orgnNatCd":    custom_orgnnatcd,
            "pkgUnitCd":    custom_pkgunitcd,
            "qtyUnitCd":    unit_of_measure_cd,
            "dftPrc":       custom_selling_price,
            "vatCatCd":     taxCode,
            "svcChargeYn":  custom_svcchargeyn,
            "isrcAplcbYn":  custom_isrcaplcbyn,
            "useYn":        "Y",
            "regrNm":       frappe.session.user,
            "regrId":       frappe.session.user,
            "modrNm":       frappe.session.user,
            "modrId":       frappe.session.user
        }
        print(json.dumps(PAYLOAD, indent=4))

        zra_success, zra_message = sync_item_with_zra(PAYLOAD, is_update=True)

        if not zra_success:
            zra_sync_message = f"Warning: ZRA sync failed - {zra_message}"
            frappe.log_error(message=zra_message, title="ZRA Update Sync Failed")
        else:
            zra_sync_message = "Item synced with ZRA successfully"
    else:
        zra_sync_message = "ZRA sync is disabled - item updated locally only"

    # ── Save to ERPNext ───────────────────────────────────────────────────────
    try:
        item.update({
            # Core
            "item_name":            item_name,
            "item_group":           item_group,
            "stock_uom":            unit_of_measure_cd,
            "brand":                brand,
            "description":          description,
            # ZRA
            "custom_itemclscd":     custom_itemclscd,
            "custom_itemtycd":      custom_itemtycd or "",
            "custom_orgnnatcd":     custom_orgnnatcd,
            "custom_pkgunitcd":     custom_pkgunitcd,
            "custom_svcchargeyn":   custom_svcchargeyn,
            "custom_isrcaplcbyn":   custom_isrcaplcbyn,
            # Pricing
            "standard_rate":        custom_selling_price,
            "custom_buying_price":  custom_buying_price,
            # Physical
            "custom_suk":           custom_sku,
            "custom_dimension":     custom_dimension_unit,
            "custom_weight":        custom_weight,
            "custom_kg":            custom_kg,
            "custom_dimensionlength": custom_dimensionlength,
            "custom_dimensionwidth":  custom_dimensionwidth,
            "custom_dimensionheight": custom_dimensionheight,
            # Vendor
            "custom_vendor":            custom_vendor,
            "custom_sales_account":     custom_sales_account,
            "custom_purchase_account":  custom_purchase_account,
            # Tax
            "custom_tax_type":          taxType,
            "custom_tax_code":          taxCode,
            "custom_tax_name":          taxName,
            "custom_tax_description":   taxDescription,
            "custom_tax_perct":         taxPerct or 0,
            "custom_tax_preference":    custom_tax_pref,
            "custom_tax_category":      taxCategory,
            # Inventory
            "custom_valuation":         custom_valuation,
            "custom_tracking_method":   custom_tracking_method,
            "custom_reorder_level":     custom_reorder_level,
            "custom_min_stock_level":   custom_min_stock_level,
            "custom_max_stock_level":   custom_max_stock_level,
            # Batch
            "has_batch_no":             1 if has_batch_no else 0,
            "create_new_batch":         1 if create_new_batch else 0,
            "has_expiry_date":          1 if has_expiry_date else 0,
            "shelf_life_in_days":       shelf_life_in_days,
            "end_of_life":              end_of_life or None,
            "custom_batch_no":          custom_batch_no,
            "custom_manufacturing_date": custom_mfg_date or None,
        })

        item.save(ignore_permissions=True)
        frappe.db.commit()

        success_message = f"Item '{item_name}' updated successfully"
        if zra_sync_message:
            success_message += f". {zra_sync_message}"

        return send_response(status="success", message=success_message, status_code=200, http_status=200)

    except Exception as e:
        frappe.log_error(message=str(e), title="Update Item ERP Error")
        return send_response(status="fail", message="Failed to update item in ERPNext", data={"error": str(e)}, status_code=500, http_status=500)


@frappe.whitelist(allow_guest=False)
def get_all_item_groups_api():
    try:
        args = frappe.request.args
        page = args.get("page")
        if not page:
            return send_response(status="error", message="'page' parameter is required.", data=None, status_code=400, http_status=400)
        try:
            page = int(page)
            if page < 1:
                raise ValueError
        except ValueError:
            return send_response(status="error", message="'page' must be a positive integer.", data=None, status_code=400, http_status=400)

        page_size = args.get("page_size")
        if not page_size:
            return send_response(status="error", message="'page_size' parameter is required.", data=None, status_code=400, http_status=400)
        try:
            page_size = int(page_size)
            if page_size < 1:
                raise ValueError
        except ValueError:
            return send_response(status="error", message="'page_size' must be a positive integer.", data=None, status_code=400, http_status=400)

        start = (page - 1) * page_size
        end = start + page_size

        all_groups = frappe.get_all(
            "Item Group",
            fields=[
                "custom_id", "item_group_name", "custom_description",
                "custom_unit_of_measurement", "custom_selling_price", "custom_sales_account"
            ],
            order_by="item_group_name asc",
            filters={"is_group": 0}
        )

        total_groups = len(all_groups)
        for group in all_groups:
            group["id"] = group.pop("custom_id")
            group["groupName"] = group.pop("item_group_name")
            group["description"] = group.pop("custom_description")
            group["unitOfMeasurement"] = group.pop("custom_unit_of_measurement")
            group["sellingPrice"] = group.pop("custom_selling_price")
            group["salesAccount"] = group.pop("custom_sales_account")

        if total_groups == 0:
            return send_response(status="success", message="No item groups found.", data=[], status_code=200, http_status=200)

        groups = all_groups[start:end]
        total_pages = (total_groups + page_size - 1) // page_size

        response_data = {
            "success": True,
            "message": "Item groups fetched successfully",
            "data": groups,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total_groups,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1
            }
        }

        return send_response_list(status="success", message="Item groups fetched successfully", status_code=200, http_status=200, data=response_data)

    except Exception as e:
        frappe.log_error(message=str(e), title="Get All Item Groups API Error")
        return send_response(status="fail", message="Failed to fetch item groups", data={"error": str(e)}, status_code=500, http_status=500)


@frappe.whitelist(allow_guest=False)
def get_item_group_by_id_api():
    try:
        args = frappe.request.args
        custom_id = (args.get("id") or "").strip()

        if not custom_id:
            return send_response(status="fail", message="'id' is required.", status_code=400, http_status=400)

        item_group_name = frappe.db.get_value("Item Group", {"custom_id": custom_id}, "name")

        if not item_group_name:
            return send_response(status="fail", message=f"Item Group with id '{custom_id}' not found.", status_code=404, http_status=404)

        doc = frappe.get_doc("Item Group", item_group_name)
        filtered_data = {
            "id": doc.custom_id,
            "groupName": doc.item_group_name,
            "description": doc.custom_description,
            "unitOfMeasurement": doc.custom_unit_of_measurement,
            "sellingPrice": doc.custom_selling_price,
            "salesAccount": doc.custom_sales_account,
        }

        return send_response(status="success", message="Item Group fetched successfully", data=filtered_data, status_code=200, http_status=200)

    except Exception as e:
        frappe.log_error(message=str(e), title="Get Item Group By ID Error")
        return send_response(status="error", message="Failed to fetch item group", data={"error": str(e)}, status_code=500, http_status=500)


@frappe.whitelist(allow_guest=False)
def create_item_group_api():
    data = frappe.form_dict
    item_group_name = (frappe.form_dict.get("groupName") or "").strip()
    is_group = frappe.form_dict.get("is_group")
    custom_description = data.get("description")
    custom_sales_account = data.get("salesAccount")
    custom_selling_price = data.get("sellingPrice")
    custom_unit_of_measurement = data.get("unitOfMeasurement")

    # ── Validation ────────────────────────────────────────────────────────────
    if not item_group_name:
        return send_response(status="fail", message="groupName is required", status_code=400, http_status=400)

    if not custom_description:
        return send_response(status="fail", message="description is required", status_code=400, http_status=400)

    if not custom_sales_account:
        return send_response(status="fail", message="salesAccount is required", status_code=400, http_status=400)

    if not custom_selling_price:
        return send_response(status="fail", message="sellingPrice is required", status_code=400, http_status=400)

    if not custom_unit_of_measurement:
        return send_response(status="fail", message="unitOfMeasurement is required", status_code=400, http_status=400)

    if frappe.db.exists("Item Group", {"item_group_name": item_group_name}):
        return send_response(status="fail", message=f"Item Group '{item_group_name}' already exists", status_code=409, http_status=409)

    if isinstance(is_group, str):
        is_group = is_group.lower() in ["true", "1", "yes"]

    # ── Auto-generate unique custom_id ────────────────────────────────────────
    custom_id = generate_group_id()
    # Ensure uniqueness (very unlikely collision but safe)
    while frappe.db.exists("Item Group", {"custom_id": custom_id}):
        custom_id = generate_group_id()

    try:
        item_group = frappe.get_doc({
            "doctype": "Item Group",
            "item_group_name": item_group_name,
            "custom_id": custom_id,
            "custom_description": custom_description,
            "custom_sales_account": custom_sales_account,
            "custom_selling_price": custom_selling_price,
            "custom_unit_of_measurement": custom_unit_of_measurement,
            "parent_item_group": "All Item Groups",
            "is_group": is_group or 0
        })
        item_group.insert(ignore_permissions=True)
        frappe.db.commit()

        return send_response(
            status="success",
            message=f"Item Group '{item_group_name}' created successfully",
            data={
                "id": custom_id,
                "name": item_group.name,
                "item_group_name": item_group.item_group_name,
                "parent_item_group": item_group.parent_item_group
            },
            status_code=201,
            http_status=201
        )

    except Exception as e:
        frappe.log_error(message=str(e), title="Create Item Group API Error")
        return send_response(status="fail", message="Failed to create item group", data={"error": str(e)}, status_code=500, http_status=500)


@frappe.whitelist(allow_guest=False)
def update_item_group_api():
    data = frappe.form_dict
    custom_id = (data.get("id") or "").strip()

    if not custom_id:
        return send_response(status="fail", message="id is required.", status_code=400)

    item_group_name = frappe.db.get_value("Item Group", {"custom_id": custom_id}, "name")

    if not item_group_name:
        return send_response(status="fail", message=f"No Item Group found with id '{custom_id}'.", status_code=404)

    try:
        item_group = frappe.get_doc("Item Group", item_group_name)
        new_group_name = (data.get("groupName") or "").strip()
        if new_group_name and new_group_name != item_group_name:
            frappe.rename_doc("Item Group", item_group_name, new_group_name)
            item_group = frappe.get_doc("Item Group", new_group_name)

        fields_to_update = {
            "custom_description": data.get("description"),
            "custom_sales_account": data.get("salesAccount"),
            "custom_selling_price": data.get("sellingPrice"),
            "custom_unit_of_measurement": data.get("unitOfMeasurement"),
        }

        for field, value in fields_to_update.items():
            if value:
                item_group.set(field, value)

        if data.get("is_group") is not None:
            is_group = data.get("is_group")
            if isinstance(is_group, str):
                is_group = is_group.lower() in ["true", "1", "yes"]
            item_group.is_group = is_group

        item_group.save(ignore_permissions=True)
        frappe.db.commit()

        return send_response(status="success", message=f"Item Group with id '{custom_id}' updated successfully.", status_code=200)

    except Exception as e:
        return send_response(status="error", message=f"Failed to update Item Group: {str(e)}", status_code=500)


@frappe.whitelist(allow_guest=False)
def delete_item_group():
    custom_id = (frappe.form_dict.get("id") or "").strip()

    if not custom_id:
        return send_response(status="fail", message="id is required.", status_code=400, http_status=400)

    item_group_name = frappe.db.get_value("Item Group", {"custom_id": custom_id}, "name")

    if not item_group_name:
        return send_response(status="fail", message=f"No Item Group found with id '{custom_id}'.", status_code=404, http_status=404)

    try:
        frappe.delete_doc("Item Group", item_group_name, force=True)
        frappe.db.commit()
        return send_response(status="success", message=f"Item Group with id '{custom_id}' deleted successfully.", status_code=200)

    except frappe.LinkExistsError:
        return send_response(status="fail", message=f"Cannot delete Item Group (id: '{custom_id}') because it is linked to other documents.", status_code=409)

    except Exception as e:
        return send_response(status="error", message=f"Failed to delete Item Group: {str(e)}", status_code=500)
