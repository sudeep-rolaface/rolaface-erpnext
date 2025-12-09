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
    custom_itemtycd = data.get("itemTypeCode") or 0
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
    custom_non_export_tax = data.get("nonExportTax") or ""
    custom_non_export_code = data.get("nonExportCode") or ""
    custom_non_export_name = data.get("nonExportName") or ""
    custom_non_export_description = data.get("nonExportDescription") or ""
    custom_non_export_tax_perct = data.get("nonExportTaxPerct") or 0
    custom_export_tax = data.get("exportTax") or ""
    custom_export_code = data.get("exportCode") or ""
    custom_export_name = data.get("exportName") or ""
    custom_export_description = data.get("exportDescription") or ""
    custom_export_tax_perct = data.get("exportTaxPerct") or 0
    custom_local_purchase_order_tax = data.get("localPurchaseOrderTax") or ""
    custom_local_purchase_order_code = data.get("localPurchaseOrderCode") or ""
    custom_local_purchase_order_name = data.get("localPurchaseOrderName") or ""
    custom_local_purchase_order_description = data.get("localPurchaseOrderDescription") or ""
    custom_local_purchase_order_perct = data.get("localPurchaseOrderPerct") or 0
    custom_dimension_unit = data.get("dimensionUnit") or ""
    custom_weight = data.get("weightUnit") or 0
    custom_valuation = data.get("valuationMethod") or ""
    custom_is_track_inventory = data.get("custom_is_track_inventory") or False
    custom_tracking_method = data.get("trackingMethod") or "None"
    custom_reorder_level = data.get("reorderLevel") or 0
    custom_min_stock_level = data.get("minStockLevel") or 0
    custom_max_stock_level = data.get("maxStockLevel") or 0
    custom_sales_account = data.get("salesAccount") or ""
    custom_purchase_account = data.get("purchaseAccount") or ""
    custom_tax_preference = data.get("taxPreference") or ""



    if not custom_selling_price:
        return send_response(
            status="fail",
            message="custom_selling_price is required",
            status_code=400,
            http_status=400
        )

    provided_codes = [bool(custom_non_export_code), bool(custom_local_purchase_order_code), bool(custom_export_code)]
    if provided_codes.count(True) != 1:
        return send_response(
            status="fail",
            message="Exactly one of custom_non_export_code, custom_local_purchase_order_code, or custom_export_code must be provided.",
            status_code=400,
            http_status=400
        )
    if custom_non_export_code and custom_non_export_code not in ["A", "B", "C3", "D", "E"]:
        return send_response(
            status="fail",
            message="custom_non_export_code must be one of A, B, C3, D, E",
            status_code=400,
            http_status=400
        )
    if custom_local_purchase_order_code and custom_local_purchase_order_code != "C1":
        return send_response(
            status="fail",
            message="custom_local_purchase_order_code must be C1",
            status_code=400,
            http_status=400
        )
    if custom_export_code and custom_export_code != "C2":
        return send_response(
            status="fail",
            message="custom_export_code must be C2",
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
        "vatCatCd": custom_non_export_code,
        "svcChargeYn": custom_svcchargeyn,
        "sftyQty": 0,
        "isrcAplcbYn": custom_isrcaplcbyn,
        "useYn": "Y",
        "regrNm": frappe.session.user,
        "regrId": frappe.session.user,
        "modrNm": frappe.session.user,
        "modrId": frappe.session.user
    }

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
            "custom_non_export_tax": custom_non_export_tax,
            "custom_non_export_code": custom_non_export_code,
            "custom_non_export_name": custom_non_export_name,
            "custom_non_export_description": custom_non_export_description,
            "custom_non_export_tax_perct": custom_non_export_tax_perct,
            "custom_export_tax": custom_export_tax,
            "custom_export_code": custom_export_code,
            "custom_export_name": custom_export_name,
            "custom_export_description": custom_export_description,
            "custom_export_tax_perct": custom_export_tax_perct,
            "custom_local_purchase_order_tax": custom_local_purchase_order_tax,
            "custom_local_purchase_order_code": custom_local_purchase_order_code,
            "custom_local_purchase_order_name": custom_local_purchase_order_name,
            "custom_local_purchase_order_description": custom_local_purchase_order_description,
            "custom_local_purchase_order_perct": custom_local_purchase_order_perct,
            "custom_dimension": custom_dimension_unit,
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

        all_items = frappe.get_all(
            "Item",
            fields=[
                "item_code",
                "item_name",
                "item_group",
                "stock_uom",
                "standard_rate",
                "custom_itemclscd",
                "custom_vendor"
            ],
            filters={"disabled": 0},  
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
                "custom_non_export_tax",
                "custom_non_export_code",
                "custom_non_export_name",
                "custom_non_export_description",
                "custom_non_export_tax_perct",
                "custom_export_tax",
                "custom_export_code",
                "custom_export_name",
                "custom_export_description",
                "custom_export_tax_perct",
                "custom_local_purchase_order_tax",
                "custom_local_purchase_order_code",
                "custom_local_purchase_order_name",
                "custom_local_purchase_order_description",
                "custom_local_purchase_order_perct",
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
            "buyingPrice": it.pop("custom_buying_price", 0),
            "unitOfMeasureCd": it.pop("stock_uom", "U"),
            "description": "",
            "sku": it.pop("custom_suk", ""),
            "taxPreference": it.pop("custom_tax_preference", ""),
            "preferredVendor": it.pop("custom_vendor", ""),
            "salesAccount": it.pop("custom_sales_account", ""),
            "purchaseAccount": it.pop("custom_purchase_account", ""),
            "nonExportTax": it.pop("custom_non_export_tax", ""),
            "nonExportCode": it.pop("custom_non_export_code", ""),
            "nonExportName": it.pop("custom_non_export_name", ""),
            "nonExportDescription": it.pop("custom_non_export_description", ""),
            "nonExportTaxPerct": it.pop("custom_non_export_tax_perct", ""),
            "exportTax": it.pop("custom_export_tax", ""),
            "exportCode": it.pop("custom_export_code", ""),
            "exportName": it.pop("custom_export_name", ""),
            "exportDescription": it.pop("custom_export_description", ""),
            "exportTaxPerct": it.pop("custom_export_tax_perct", ""),
            "localPurchaseOrderTax": it.pop("custom_local_purchase_order_tax", ""),
            "localPurchaseOrderCode": it.pop("custom_local_purchase_order_code", ""),
            "localPurchaseOrderName": it.pop("custom_local_purchase_order_name", ""),
            "localPurchaseOrderDescription": it.pop("custom_local_purchase_order_description", ""),
            "localPurchaseOrderPerct": it.pop("custom_local_purchase_order_perct", ""),
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
    tax_non_export = {
        "tax": data.get("nonExportTax"),
        "code": data.get("nonExportCode"),
        "name": data.get("nonExportName"),
        "description": data.get("nonExportDescription"),
        "percentage": data.get("nonExportTaxPerct")
    }
    tax_export = {
        "tax": data.get("exportTax"),
        "code": data.get("exportCode"),
        "name": data.get("exportName"),
        "description": data.get("exportDescription"),
        "percentage": data.get("exportTaxPerct")
    }
    tax_local_po = {
        "tax": data.get("localPurchaseOrderTax"),
        "code": data.get("localPurchaseOrderCode"),
        "name": data.get("localPurchaseOrderName"),
        "description": data.get("localPurchaseOrderDescription"),
        "percentage": data.get("localPurchaseOrderPerct")
    }
    provided_codes = [
        bool(tax_non_export["code"]),
        bool(tax_export["code"]),
        bool(tax_local_po["code"])
    ]
    if provided_codes.count(True) > 1:
        return send_response(
            status="fail",
            message="Exactly one of nonExportCode, localPurchaseOrderCode or exportCode must be provided.",
            status_code=400,
            http_status=400
        )

    if tax_non_export["code"]:
        active_tax = tax_non_export
        tax_export = {k: "" for k in tax_export}
        tax_local_po = {k: "" for k in tax_local_po}
    elif tax_export["code"]:
        active_tax = tax_export
        tax_non_export = {k: "" for k in tax_non_export}
        tax_local_po = {k: "" for k in tax_local_po}
    elif tax_local_po["code"]:
        active_tax = tax_local_po
        tax_non_export = {k: "" for k in tax_non_export}
        tax_export = {k: "" for k in tax_export}
    else:
        # Keep existing values if nothing provided
        tax_non_export["code"] = item.custom_non_export_code
        tax_non_export["tax"] = item.custom_non_export_tax
        tax_non_export["name"] = item.custom_non_export_name
        tax_non_export["description"] = item.custom_non_export_description
        tax_non_export["percentage"] = item.custom_non_export_tax_perct

        tax_export["code"] = item.custom_export_code
        tax_export["tax"] = item.custom_export_tax
        tax_export["name"] = item.custom_export_name
        tax_export["description"] = item.custom_export_description
        tax_export["percentage"] = item.custom_export_tax_perct

        tax_local_po["code"] = item.custom_local_purchase_order_code
        tax_local_po["tax"] = item.custom_local_purchase_order_tax
        tax_local_po["name"] = item.custom_local_purchase_order_name
        tax_local_po["description"] = item.custom_local_purchase_order_description
        tax_local_po["percentage"] = item.custom_local_purchase_order_perct

    # Validate codes
    if tax_non_export["code"] and tax_non_export["code"] not in ["A", "B", "C3", "D", "E"]:
        return send_response(status="fail", message="Invalid nonExportCode (allowed A,B,C3,D,E)", status_code=400, http_status=400)
    if tax_local_po["code"] and tax_local_po["code"] != "C1":
        return send_response(status="fail", message="localPurchaseOrderCode must be C1", status_code=400, http_status=400)
    if tax_export["code"] and tax_export["code"] != "C2":
        return send_response(status="fail", message="exportCode must be C2", status_code=400, http_status=400)

    # Ensure UOM and group exist
    ensure_uom_exists(unit_of_measure_cd)
    exists = check_if_group_exists(item_group)
    if exists is not True:
        return exists  

    # Create brand if not exists
    if brand and not frappe.db.exists("Brand", brand):
        try:
            frappe.get_doc({"doctype": "Brand", "brand": brand}).insert(ignore_permissions=True)
        except Exception as e:
            return send_response(status="fail", message=f"Failed to create brand '{brand}'", data={"error": str(e)}, status_code=500)

    # ---------------- Update ZRA ----------------
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
        "vatCatCd": tax_non_export["code"] or tax_local_po["code"] or tax_export["code"],
        "svcChargeYn": custom_svcchargeyn,
        "isrcAplcbYn": custom_isrcaplcbyn,
        "useYn": "Y",
        "regrNm": frappe.session.user,
        "regrId": frappe.session.user,
        "modrNm": frappe.session.user,
        "modrId": frappe.session.user
    }

    # try:
    #     zra_response = ZRA_CLIENT_INSTANCE.update_item_zra_client(PAYLOAD)
    #     zra_json = zra_response.json()
    #     if zra_json.get("resultCd") != "000":
    #         return send_response(status="fail", message=zra_json.get("resultMsg", "Item update failed on ZRA side"), status_code=400, http_status=400)
    # except Exception as e:
    #     frappe.log_error(message=str(e), title="Update Item ZRA Error")
    #     return send_response(status="fail", message="Failed to sync item with ZRA", data={"error": str(e)}, status_code=500, http_status=500)

    # # ---------------- Update ERPNext ----------------
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
            "custom_is_track_inventory": custom_is_track_inventory,
            "custom_tracking_method": custom_tracking_method,
            "custom_sales_account": custom_sales_account,
            "custom_purchase_account": custom_purchase_account,
            "custom_reorder_level": custom_reorder_level,
            "custom_min_stock_level": custom_min_stock_level,
            "custom_max_stock_level": custom_max_stock_level,
            "custom_tax_preference": custom_tax_preference,
            "custom_non_export_code": tax_non_export["code"],
            "custom_non_export_name": tax_non_export["name"],
            "custom_non_export_description": tax_non_export["description"],
            "custom_non_export_tax": tax_non_export["tax"],
            "custom_non_export_tax_perct": tax_non_export["percentage"],
            "custom_export_code": tax_export["code"],
            "custom_export_name": tax_export["name"],
            "custom_export_description": tax_export["description"],
            "custom_export_tax": tax_export["tax"],
            "custom_export_tax_perct": tax_export["percentage"],
            "custom_local_purchase_order_code": tax_local_po["code"],
            "custom_local_purchase_order_name": tax_local_po["name"],
            "custom_local_purchase_order_description": tax_local_po["description"],
            "custom_local_purchase_order_tax": tax_local_po["tax"],
            "custom_local_purchase_order_perct": tax_local_po["percentage"],
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
            order_by="item_group_name asc"
        )

        total_groups = len(all_groups)

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
        custom_id = args.get("custom_id")
        name = args.get("name")

        if not custom_id and not name:
            return send_response(
                status="fail",
                message="Provide either 'custom_id' or 'name'.",
                status_code=400,
                http_status=400
            )

        if custom_id:
            item_group_name = frappe.db.get_value(
                "Item Group", 
                {"custom_id": custom_id}, 
                "name"
            )
            if not item_group_name:
                return send_response(
                    status="fail",
                    message=f"Item Group with custom_id '{custom_id}' not found.",
                    status_code=404,
                    http_status=404
                )
        else:
            if not frappe.db.exists("Item Group", name):
                return send_response(
                    status="fail",
                    message=f"Item Group '{name}' not found.",
                    status_code=404,
                    http_status=404
                )
            item_group_name = name


        doc = frappe.get_doc("Item Group", item_group_name)
        filtered_data = {
            "name": doc.name,
            "item_group_name": doc.item_group_name,
            "custom_id": doc.custom_id,
            "custom_description": doc.custom_description,
            "custom_unit_of_measurement": doc.custom_unit_of_measurement,
            "custom_selling_price": doc.custom_selling_price,
            "custom_sales_account": doc.custom_sales_account
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
    item_group_name = (frappe.form_dict.get("item_group_name") or "").strip()
    parent_item_group = (frappe.form_dict.get("parent_item_group") or "All Item Groups").strip()
    is_group = frappe.form_dict.get("is_group")
    custom_id = data.get("custom_id")
    custom_description = data.get("custom_description")
    custom_sales_account = data.get("custom_sales_account")
    custom_selling_price = data.get("custom_selling_price")
    custom_unit_of_measurement = data.get("custom_unit_of_measurement")
    
    
    if not custom_id:
        return send_response(
            status="fail",
            message="custom_id is required",
            status_code=400,
            http_status=400
        )
    
    if not custom_description:
        return send_response(
            status="fail",
            message="custom_description is required",
            status_code=400,
            http_status=400
        )
    if not custom_sales_account:
        return send_response(
            status="fail",
            message="custom_sales_account is required",
            status_code=400,
            http_status=400
        )
    if not custom_selling_price:
        return send_response(
            status="fail",
            message="custom_selling_price is required",
            status_code=400,
            http_status=400
        )
    if not custom_unit_of_measurement:
        return send_response(
            status="fail",
            message="custom_unit_of_measurement is required",
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
            message=f"custom_id '{custom_id}' is already used. Enter a unique ID.",
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
    current_group_name = (frappe.form_dict.get("current_group_name") or "").strip()
    new_group_name = (frappe.form_dict.get("new_group_name") or "").strip()

    if not current_group_name:
        return send_response(
            status="fail",
            message="Current Item Group Name is required.",
            status_code=400,
            http_status=400
        )

    if not new_group_name:
        return send_response(
            status="fail",
            message="New Group Name is required.",
            status_code=400,
            http_status=400
        )

    try:
        if not frappe.db.exists("Item Group", current_group_name):
            return send_response(
                status="fail",
                message=f"Item Group '{current_group_name}' does not exist.",
                status_code=404,
                http_status=404
            )

        frappe.rename_doc(
            doctype="Item Group",
            old=current_group_name,
            new=new_group_name,
            merge=False
        )

        item_group = frappe.get_doc("Item Group", new_group_name)

        data = item_group.as_dict()
        data.pop("_server_messages", None)  

        return send_response(
            status="success",
            message=f"Item Group renamed to '{new_group_name}' successfully.",
            status_code=200,
        )

    except Exception as e:
        return send_response(
            status="error",
            message=f"Failed to update Item Group: {str(e)}",
            status_code=500
        )
        



@frappe.whitelist(allow_guest=False)
def delete_item_group():
    item_group_name = (frappe.form_dict.get("item_group_name") or "").strip()

    if not item_group_name:
        send_response(
            status=400,
            message="Item Group Name Not Found.",
            status_code=400,
            http_status=400
        )
        return
    try:
        if not frappe.db.exists("Item Group", item_group_name):
            return send_response(
                status="fail",
                message=f"Item Group '{item_group_name}' does not exist.",
                status_code=404,
                http_status=404
            )
        frappe.delete_doc("Item Group", item_group_name, force=True)
        frappe.db.commit()

        return send_response(
            status="success",
            message=f"Item Group '{item_group_name}' deleted successfully.",
            status_code=200
        )
    except frappe.LinkExistsError:
        return send_response(
            status="fail",
            message=f"Cannot delete Item Group '{item_group_name}' because it is linked to other documents.",
            status_code=409
        )
    except Exception as e:
        return send_response(
            status="error",
            message=f"Failed to delete Item Group: {str(e)}",
            status_code=500
        )
        
        
        
