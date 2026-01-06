from erpnext.zra_client.generic_api import send_response, send_response_list
from erpnext.zra_client.main import ZRAClient
from frappe import _
import random
import frappe
import json

ZRA_CLIENT_INSTANCE = ZRAClient()


def generate_item_code_random(country_code, product_type, pkg_unit, qty_unit):
    random_id = random.randint(1, 99999)
    random_id_str = str(random_id).zfill(5)
    item_code = f"{country_code}{product_type}{pkg_unit}{qty_unit}{random_id_str}"
    return item_code


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
    
    
    
    
    if not taxCategory:
        return send_response(
            status="error",
            message="taxCategory is required",
            status_code=400,
            http_status=400
        )
    
    allowed_categories = ZRA_CLIENT_INSTANCE.getTaxCategory()
    if taxCategory not in allowed_categories:
        return send_response(
            status="error",
            message=f'taxCategory must be one of {allowed_categories}',
            status_code=400,
            http_status=400
        )
    
    if not item_name:
        return send_response(
            status="fail",
            message="Item name is required",
            status_code=400,
            http_status=400,
        )
        
    if not custom_orgnnatcd:
        return send_response(
            status="fail",
            message="Item origin code is required",
            status_code=400,
            http_status=400
        )
        
    if not custom_pkgunitcd:
        return send_response(
            status="fail",
            message="Item packaging unit code is required",
            status_code=400,
            http_status=400
        )
        
    if not custom_itemclscd:
        return send_response(
            status="fail",
            message="Item classification code is required",
            status_code=400,
            http_status=400
        )
    
    if not custom_itemtycd:
        return send_response(
            status="fail",
            message="item Type Code is required",
            status_code=400,
            http_status=400
        )

    if not custom_selling_price:
        return send_response(
            status="fail",
            message="selling price is required",
            status_code=400,
            http_status=400
        )
        
    if not taxCode:
        return send_response(
            status="fail",
            message="taxCode is required",
            status_code=400,
            http_status=400
        )

    if taxCode not in ["A","C1", "C2"]:
        return send_response(
            status="fail",
            message="taxCode must be one of A, C1, C2",
            status_code=400,
            http_status=400
        )
  

    required_fields = {
        "item_name": item_name,
        "item_group": item_group,
        "unit_of_measure_cd": unit_of_measure_cd,
        "custom_itemclscd": custom_itemclscd,
        "custom_itemtycd": custom_itemtycd,
        "custom_orgnnatcd": custom_orgnnatcd,
        "custom_pkgunitcd": custom_pkgunitcd,
        "custom_svcchargeyn": custom_svcchargeyn,
        "custom_isrcaplcbyn": custom_isrcaplcbyn,
        "custom_selling_price": custom_selling_price
    }
    for field, value in required_fields.items():
        if not value:
            return send_response(
                status="fail",
                message=f"{field} is required",
                status_code=400,
                http_status=400
            )

    item_code = generate_item_code_random(custom_orgnnatcd, custom_itemtycd, custom_pkgunitcd, unit_of_measure_cd)
    ensure_uom_exists(unit_of_measure_cd)

    if frappe.db.exists("Item", {"item_name": item_name}):
        return send_response(
            status="fail",
            message=f"Item '{item_name}' already exists",
            status_code=400,
            http_status=400
        )

 
    itemGroup = check_if_group_exists(item_group)
    if not itemGroup:
        return send_response(
            status="fail",
            message=f"Item group '{item_group}' does not exist",
            status_code=400,
            http_status=400
        )


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

    try:
        result = ZRA_CLIENT_INSTANCE.create_item_zra_client(PAYLOAD)
        print(result)
        response_data = result.json()
        print(response_data)
        if response_data.get("resultCd") != "000":
            return send_response(
                status="error",
                message=response_data.get("resultMsg", "Item Sync Failed"),
                status_code=400,
                http_status=400
            )

        if brand:
            if not frappe.db.exists("Brand", brand):
                try:
                    frappe.get_doc({"doctype": "Brand", "brand": brand}).insert(ignore_permissions=True)
                except Exception as e:
                    return send_response(
                        status="fail",
                        message=f"Failed to create brand '{brand}'",
                        data={"error": str(e)},
                        status_code=500,
                        http_status=500
                    )

        item = frappe.get_doc({
            "doctype": "Item",
            "item_name": item_name,
            "item_code": item_code,
            "item_group": item_group,
            "stock_uom": unit_of_measure_cd,
            "custom_itemclscd": custom_itemclscd,
            "custom_itemtycd": custom_itemtycd,
            "custom_orgnnatcd": custom_orgnnatcd,
            "custom_pkgunitcd": custom_pkgunitcd,
            "custom_svcchargeyn": custom_svcchargeyn,
            "custom_isrcaplcbyn": custom_isrcaplcbyn,
            "is_stock_item": 1,
            "brand": brand,
            "standard_rate": custom_selling_price,
            "custom_purchase_amount": custom_purchase_amount,
            "custom_buying_price": custom_buying_price,
            "custom_suk": custom_sku,
            "custom_kg": custom_kg,
            "custom_vendor": custom_vendor,
            "custom_tax_type": taxType,
            "custom_tax_code": taxCode,
            "custom_tax_name": taxName,
            "custom_tax_description": taxDescription,
            "custom_tax_perct": taxPerct,
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
            "custom_dimensionlength":custom_dimensionlength,
            "custom_dimensionwidth": custom_dimensionwidth,
            "custom_dimensionheight":custom_dimensionheight,
            "custom_tax_category": taxCategory,
        })
        item.insert(ignore_permissions=True)
        frappe.db.commit()

        return send_response(
            status="success",
            message=f"Item '{item_name}' created successfully",
            status_code=201,
            http_status=201
        )

    except Exception as e:
        frappe.log_error(message=str(e), title="Create Item API Error")
        return send_response(
            status="fail",
            message="Failed to create item",
            data={"error": str(e)},
            status_code=500,
            http_status=500
        )


@frappe.whitelist(allow_guest=False)
def get_all_items_api():
    try:
        args = frappe.request.args

        # --------------------
        # Pagination validation
        # --------------------
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
        end = start + page_size


        tax_category = args.get("taxCategory")

        filters = {"disabled": 0}
        if tax_category:
            filters["custom_tax_category"] = tax_category

        all_items = frappe.get_all(
            "Item",
            fields=[
                "item_code",
                "item_name",
                "item_group",
                "stock_uom",
                "standard_rate",
                "custom_itemclscd",
                "custom_vendor",
                "custom_tax_category",
                "custom_min_stock_level",
                "custom_max_stock_level",
            ],
            filters=filters,
            order_by="creation desc"
        )

        total_items = len(all_items)

        if total_items == 0:
            return send_response(
                status="success",
                message="No items found.",
                data=[],
                status_code=200,
                http_status=200
            )

        items = all_items[start:end]
        for it in items:
            it["id"] = it.pop("item_code")
            it["itemName"] = it.pop("item_name")
            it["itemGroup"] = it.pop("item_group")
            it["itemClassCode"] = it.pop("custom_itemclscd")
            it["unitOfMeasureCd"] = it.pop("stock_uom")
            it["sellingPrice"] = it.pop("standard_rate")
            it["preferredVendor"] = it.pop("custom_vendor")
            it["minStockLevel"] = it.pop("custom_min_stock_level")
            it["maxStockLevel"] = it.pop("custom_max_stock_level")
            it["taxCategory"] = it.pop("custom_tax_category")

        total_pages = (total_items + page_size - 1) // page_size

        response_data = {
            "success": True,
            "message": "Items retrieved successfully",
            "data": items,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total_items,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1
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
        return send_response(
            status="fail",
            message="Failed to fetch items",
            data={"error": str(e)},
            status_code=500,
            http_status=500
        )

@frappe.whitelist(allow_guest=False)
def get_item_by_id_api():
    item_code = (frappe.form_dict.get("id") or "").strip()
    if not item_code:
        return send_response(
            status="fail",
            message="item_code is required",
            status_code=400,
            http_status=400
        )

    try:
        items = frappe.get_all(
            "Item",
            filters={"item_code": item_code},
            fields=[
                "name",
                "item_code",
                "item_name",
                "item_group",
                "stock_uom",
                "standard_rate",
                "custom_itemclscd",
                "custom_itemtycd",
                "custom_orgnnatcd",
                "custom_pkgunitcd",
                "custom_svcchargeyn",
                "custom_isrcaplcbyn",
                "custom_selling_price",
                "custom_purchase_amount",
                "standard_rate",
                "custom_buying_price",
                "custom_suk",
                "custom_vendor",
                "custom_tax_type",
                "custom_tax_code",
                "custom_tax_name",
                "custom_tax_description",
                "custom_tax_perct",
                "custom_dimension",
                "custom_weight",
                "custom_valuation",
                "custom_is_track_inventory",
                "custom_tracking_method",
                "custom_reorder_level",
                "custom_min_stock_level",
                "custom_max_stock_level",
                "custom_sales_account",
                "custom_purchase_account",
                "brand",
                'custom_kg',
                "description",
                "custom_tax_preference",
                "custom_dimensionlength",
                "custom_dimensionwidth",
                "custom_dimensionheight",
                "custom_tax_category",
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
            "id": it.pop("item_code", ""),
            "itemName": it.pop("item_name", ""),
            "itemGroup": it.pop("item_group", ""),
            "itemClassCode": it.pop("custom_itemclscd", ""),
            "itemTypeCode": it.pop("custom_itemtycd", 0),
            "originNationCode": it.pop("custom_orgnnatcd", ""),
            "packagingUnitCode": it.pop("custom_pkgunitcd", ""),
            "svcCharge": it.pop("custom_svcchargeyn", "Y"),
            "ins": it.pop("custom_isrcaplcbyn", "Y"),
            "sellingPrice": it.pop("standard_rate", 0),
            "buyingPrice": int(it.pop("custom_buying_price", 0)),
            "unitOfMeasureCd": it.pop("stock_uom", "U"),
            "description": "",
            "sku": it.pop("custom_suk", ""),
            "taxPreference": it.pop("custom_tax_preference", ""),
            "preferredVendor": it.pop("custom_vendor", ""),
            "salesAccount": it.pop("custom_sales_account", ""),
            "purchaseAccount": it.pop("custom_purchase_account", ""),
            "taxType": it.pop("custom_tax_type"),
            "taxCode": it.pop("custom_tax_code"),
            "taxName": it.pop("custom_tax_name"),
            "taxDescription": it.pop("custom_tax_description"),
            "taxPerct": it.pop("custom_tax_perct"),
            "dimensionUnit": it.pop("custom_dimension", ""),
            "weight": it.pop("custom_weight", ""),
            "valuationMethod": it.pop("custom_valuation", ""),
            "trackingMethod": it.pop("custom_tracking_method", "None"),
            "reorderLevel": it.pop("custom_reorder_level", 0),
            "minStockLevel": it.pop("custom_min_stock_level", 0),
            "maxStockLevel": it.pop("custom_max_stock_level", 0),
            "brand": it.pop("brand", ""),
            "description": it.pop("description", ""),
            "weightUnit": it.pop("custom_kg", ""),
            "dimensionLength": it.pop("custom_dimensionlength", ""),
            "dimensionWidth":it.pop("custom_dimensionwidth", ""),
            "dimensionHeight":it.pop("custom_dimensionheight", ""),
            "taxCategory": it.pop("custom_tax_category", ""),
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
        return send_response(
            status="fail",
            message="item id is required",
            status_code=400,
            http_status=400
        )

    try:
        item = frappe.get_doc("Item", {"item_code": item_code})
    except frappe.DoesNotExistError:
        return send_response(
            status="fail",
            message=f"Item with id '{item_code}' does not exist",
            status_code=404,
            http_status=404
        )

    try:
        item.delete()
        frappe.db.commit()
        return send_response(
            status="success",
            message=f"Item '{item_code}' deleted successfully",
            status_code=200,
            http_status=200
        )
    except Exception as e:
        frappe.log_error(message=str(e), title="Delete Item API Error")
        return send_response(
            status="fail",
            message="Failed to delete item",
            status_code=500,
            http_status=500
        )


@frappe.whitelist(allow_guest=False, methods=["PUT"])
def update_item_api():
    data = frappe.form_dict

    item_code = (data.get("id") or "").strip()
    if not item_code:
        return send_response(
            status="fail",
            message="Item ID (item_code) is required",
            status_code=400,
            http_status=400
        )

    if not frappe.db.exists("Item", {"item_code": item_code}):
        return send_response(
            status="fail",
            message=f"Item with code '{item_code}' does not exist",
            status_code=404,
            http_status=404
        )

    item = frappe.get_doc("Item", {"item_code": item_code})
    item_name = (data.get("itemName") or item.item_name).strip()
    item_group = (data.get("itemGroup") or item.item_group).strip()
    unit_of_measure_cd = (data.get("unitOfMeasureCd") or item.stock_uom).strip()
    description = (data.get("description") or item.description).strip()
    brand = (data.get("brand") or item.brand or "").strip()
    custom_itemclscd = (data.get("itemClassCode") or item.custom_itemclscd).strip()
    custom_itemtycd = data.get("itemTypeCode") or item.custom_itemtycd
    custom_orgnnatcd = (data.get("originNationCode") or item.custom_orgnnatcd).strip()
    custom_pkgunitcd = (data.get("packagingUnitCode") or item.custom_pkgunitcd).strip()
    custom_svcchargeyn = (data.get("svcCharge") or item.custom_svcchargeyn).strip()
    custom_isrcaplcbyn = (data.get("ins") or item.custom_isrcaplcbyn).strip()
    custom_selling_price = data.get("sellingPrice") or item.standard_rate
    custom_buying_price = data.get("buyingPrice") or item.custom_buying_price
    custom_sku = data.get("sku") or item.custom_suk
    custom_dimension_unit = data.get("dimensionUnit") or item.custom_dimension
    custom_weight = data.get("weight") or item.custom_weight
    custom_valuation = data.get("valuationMethod") or item.custom_valuation
    custom_vendor = data.get("preferredVendor") or item.custom_vendor
    custom_kg = data.get("weightUnit") or item.custom_kg
    custom_is_track_inventory = data.get("custom_is_track_inventory") or item.custom_is_track_inventory
    custom_tracking_method = (data.get("trackingMethod") or item.custom_tracking_method).strip()
    custom_sales_account = (data.get("salesAccount") or item.custom_sales_account).strip()
    custom_purchase_account = (data.get("purchaseAccount") or item.custom_purchase_account).strip()
    custom_min_stock_level = (data.get("minStockLevel") or item.custom_min_stock_level).strip()
    custom_max_stock_level = (data.get("maxStockLevel") or item.custom_max_stock_level).strip()
    custom_reorder_level = (data.get("reorderLevel") or item.custom_reorder_level).strip()
    custom_tax_preference =(data.get("taxPreference") or item.custom_tax_preference).strip()
    custom_dimensionlength = data.get("dimensionLength") or item.custom_dimensionlength 
    custom_dimensionwidth = data.get("dimensionWidth") or item.custom_dimensionwidth 
    custom_dimensionheight = data.get("dimensionHeight") or item.custom_dimensionheight 
    taxType = data.get("taxType") or item.custom_tax_type
    taxCode = data.get("taxCode") or item.custom_tax_code
    taxName = data.get("taxName") or item.custom_tax_name
    taxDescription = data.get("taxDescription") or item.custom_tax_description
    taxPerct = data.get("taxPerct") or item.custom_tax_perct
    taxCategory = data.get("taxCategory") or item.custom_tax_category
    
    if taxCode not in ["A","C1", "C2"]:
        return send_response(
            status="fail",
            message="taxCode must be one of A, C1, C2",
            status_code=400,
            http_status=400
        )
    allowed_categories = ZRA_CLIENT_INSTANCE.getTaxCategory()
    if taxCategory not in ZRA_CLIENT_INSTANCE.getTaxCategory():
        return send_response(
            status="error",
            message=f"taxCategory must be one of {allowed_categories}",
            status_code=400,
            http_status=400
        )
    


    ensure_uom_exists(unit_of_measure_cd)
    exists = check_if_group_exists(item_group)
    if exists is not True:
        return exists  

    if brand and not frappe.db.exists("Brand", brand):
        try:
            frappe.get_doc({"doctype": "Brand", "brand": brand}).insert(ignore_permissions=True)
        except Exception as e:
            return send_response(status="fail", message=f"Failed to create brand '{brand}'", data={"error": str(e)}, status_code=500)
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
        "isrcAplcbYn": custom_isrcaplcbyn,
        "useYn": "Y",
        "regrNm": frappe.session.user,
        "regrId": frappe.session.user,
        "modrNm": frappe.session.user,
        "modrId": frappe.session.user
    }
    print(json.dumps(PAYLOAD, indent=4))
    try:
        zra_response = ZRA_CLIENT_INSTANCE.update_item_zra_client(PAYLOAD)
        zra_json = zra_response.json()
        if zra_json.get("resultCd") != "000":
            return send_response(status="fail", message=zra_json.get("resultMsg", "Item update failed on ZRA side"), status_code=400, http_status=400)
    except Exception as e:
        frappe.log_error(message=str(e), title="Update Item ZRA Error")
        return send_response(status="fail", message="Failed to sync item with ZRA", data={"error": str(e)}, status_code=500, http_status=500)
    try:
        item.update({
            "item_name": item_name,
            "item_group": item_group,
            "stock_uom": unit_of_measure_cd,
            "brand": brand,
            "description": description,
            "custom_itemclscd": custom_itemclscd,
            "custom_itemtycd": custom_itemtycd,
            "custom_orgnnatcd": custom_orgnnatcd,
            "custom_pkgunitcd": custom_pkgunitcd,
            "custom_svcchargeyn": custom_svcchargeyn,
            "custom_isrcaplcbyn": custom_isrcaplcbyn,
            "standard_rate": custom_selling_price,
            "custom_buying_price": custom_buying_price,
            "custom_suk": custom_sku,
            "custom_dimension": custom_dimension_unit,
            "custom_weight": custom_weight,
            "custom_valuation": custom_valuation,
            "custom_vendor": custom_vendor,
            "custom_kg": custom_kg,
            "custom_tax_type": taxType,
            "custom_tax_code": taxCode,
            "custom_tax_name": taxName,
            "custom_tax_description": taxDescription,
            "custom_tax_perct": taxPerct,
            "custom_is_track_inventory": custom_is_track_inventory,
            "custom_tracking_method": custom_tracking_method,
            "custom_sales_account": custom_sales_account,
            "custom_purchase_account": custom_purchase_account,
            "custom_reorder_level": custom_reorder_level,
            "custom_min_stock_level": custom_min_stock_level,
            "custom_max_stock_level": custom_max_stock_level,
            "custom_tax_preference": custom_tax_preference,
            "custom_dimensionlength":custom_dimensionlength,
            "custom_dimensionwidth": custom_dimensionwidth,
            "custom_dimensionheight":custom_dimensionheight,
            "custom_tax_category": taxCategory
        })

        item.save(ignore_permissions=True)
        frappe.db.commit()

        return send_response(
            status="success",
            message=f"Item '{item_name}' updated successfully",
            status_code=200,
            http_status=200
        )
    except Exception as e:
        frappe.log_error(message=str(e), title="Update Item ERP Error")
        return send_response(
            status="fail",
            message="Failed to update item in ERPNext",
            data={"error": str(e)},
            status_code=500,
            http_status=500
        )


@frappe.whitelist(allow_guest=False)
def get_all_item_groups_api():
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
        end = start + page_size
        all_groups = frappe.get_all(
            "Item Group",
            fields=[
                "custom_id",
                "item_group_name",
                "custom_description",
                "custom_unit_of_measurement",
                "custom_selling_price",
                "custom_sales_account"
            ],
            order_by="item_group_name asc",
            filters={
                "is_group": 0
            }
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
            return send_response(
                status="success",
                message="No item groups found.",
                data=[],
                status_code=200,
                http_status=200
            )

     
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

        return send_response_list(
            status="success",
            message="Item groups fetched successfully",
            status_code=200,
            http_status=200,
            data=response_data
        )

    except Exception as e:
        frappe.log_error(message=str(e), title="Get All Item Groups API Error")
        return send_response(
            status="fail",
            message="Failed to fetch item groups",
            data={"error": str(e)},
            status_code=500,
            http_status=500
        )
@frappe.whitelist(allow_guest=False)
def get_item_group_by_id_api():
    try:
        args = frappe.request.args
        custom_id = (args.get("id") or "").strip()

        if not custom_id:
            return send_response(
                status="fail",
                message="'id' is required.",
                status_code=400,
                http_status=400
            )

        item_group_name = frappe.db.get_value(
            "Item Group",
            {"custom_id": custom_id},
            "name"
        )

        if not item_group_name:
            return send_response(
                status="fail",
                message=f"Item Group with id '{custom_id}' not found.",
                status_code=404,
                http_status=404
            )

        doc = frappe.get_doc("Item Group", item_group_name)
        filtered_data = {
            "id": doc.custom_id,
            "groupName": doc.item_group_name,
            "description": doc.custom_description,
            "unitOfMeasurement": doc.custom_unit_of_measurement,
            "sellingPrice": doc.custom_selling_price,
            "salesAccount": doc.custom_sales_account,
        }

        return send_response(
            status="success",
            message="Item Group fetched successfully",
            data=filtered_data,
            status_code=200,
            http_status=200
        )

    except Exception as e:
        frappe.log_error(message=str(e), title="Get Item Group By ID Error")
        return send_response(
            status="error",
            message="Failed to fetch item group",
            data={"error": str(e)},
            status_code=500,
            http_status=500
        )


@frappe.whitelist(allow_guest=False)
def create_item_group_api():
    data = frappe.form_dict
    item_group_name = (frappe.form_dict.get("groupName") or "").strip()
    is_group = frappe.form_dict.get("is_group")
    custom_id = data.get("id")
    custom_description = data.get("description")
    custom_sales_account = data.get("salesAccount")
    custom_selling_price = data.get("sellingPrice")
    custom_unit_of_measurement = data.get("unitOfMeasurement")
    
    
    if not custom_id:
        return send_response(
            status="fail",
            message="id is required",
            status_code=400,
            http_status=400
        )
    
    if not custom_description:
        return send_response(
            status="fail",
            message="description is required",
            status_code=400,
            http_status=400
        )
    if not custom_sales_account:
        return send_response(
            status="fail",
            message="salesAccount is required",
            status_code=400,
            http_status=400
        )
    if not custom_selling_price:
        return send_response(
            status="fail",
            message="sellingPrice is required",
            status_code=400,
            http_status=400
        )
    if not custom_unit_of_measurement:
        return send_response(
            status="fail",
            message="unitOfMeasurement is required",
            status_code=400,
            http_status=400
        )
    

    if not item_group_name:
        return send_response(
            status="fail",
            message="item_group_name is required",
            status_code=400,
            http_status=400
        )
    if isinstance(is_group, str):
        is_group = is_group.lower() in ["true", "1", "yes"]

    if frappe.db.exists("Item Group", {"custom_id": custom_id}):
        return send_response(
            status="fail",
            message=f"id '{custom_id}' is already used. Enter a unique ID.",
            status_code=409,
            http_status=409
        )

    if frappe.db.exists("Item Group", {"item_group_name": item_group_name}):
        return send_response(
            status="fail",
            message=f"Item Group '{item_group_name}' already exists",
            status_code=409,
            http_status=409
        )

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
                "name": item_group.name,
                "item_group_name": item_group.item_group_name,
                "parent_item_group": item_group.parent_item_group
            },
            status_code=201,
            http_status=201
        )

    except Exception as e:
        frappe.log_error(message=str(e), title="Create Item Group API Error")
        return send_response(
            status="fail",
            message="Failed to create item group",
            data={"error": str(e)},
            status_code=500,
            http_status=500
        )

@frappe.whitelist(allow_guest=False)
def update_item_group_api():
    data = frappe.form_dict

    custom_id = (data.get("id") or "").strip()

    if not custom_id:
        return send_response(
            status="fail",
            message="id is required.",
            status_code=400
        )

    item_group_name = frappe.db.get_value("Item Group", {"custom_id": custom_id}, "name")

    if not item_group_name:
        return send_response(
            status="fail",
            message=f"No Item Group found with id '{custom_id}'.",
            status_code=404
        )

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

        return send_response(
            status="success",
            message=f"Item Group with id '{custom_id}' updated successfully.",
            status_code=200
        )

    except Exception as e:
        return send_response(
            status="error",
            message=f"Failed to update Item Group: {str(e)}",
            status_code=500
        )



@frappe.whitelist(allow_guest=False)
def delete_item_group():
    custom_id = (frappe.form_dict.get("id") or "").strip()

    if not custom_id:
        return send_response(
            status="fail",
            message="id is required.",
            status_code=400,
            http_status=400
        )

    item_group_name = frappe.db.get_value("Item Group", {"custom_id": custom_id}, "name")

    if not item_group_name:
        return send_response(
            status="fail",
            message=f"No Item Group found with id '{custom_id}'.",
            status_code=404,
            http_status=404
        )

    try:
        frappe.delete_doc("Item Group", item_group_name, force=True)
        frappe.db.commit()

        return send_response(
            status="success",
            message=f"Item Group with id '{custom_id}' deleted successfully.",
            status_code=200
        )

    except frappe.LinkExistsError:
        return send_response(
            status="fail",
            message=f"Cannot delete Item Group (id: '{custom_id}') because it is linked to other documents.",
            status_code=409
        )

    except Exception as e:
        return send_response(
            status="error",
            message=f"Failed to delete Item Group: {str(e)}",
            status_code=500
        )

        
