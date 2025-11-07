from erpnext.zra_client.generic_api import send_response
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
        return send_response(status="fail", message="Quantity Unit Code is required. (qtyUnitCd)")

    if not frappe.db.exists("UOM", uom_name):
        uom_doc = frappe.get_doc({
            "doctype": "UOM",
            "uom_name": uom_name,
            "must_be_whole_number": 1
        })
        uom_doc.insert(ignore_permissions=True)
        frappe.db.commit()


@frappe.whitelist(allow_guest=False)
def create_item_api():
    item_name = (frappe.form_dict.get("item_name") or "").strip()
    item_group = (frappe.form_dict.get("item_group") or "").strip()
    qtyUnitCd = (frappe.form_dict.get("qtyUnitCd") or "").strip()
    custom_itemclscd = (frappe.form_dict.get("itemClassCd") or "").strip()
    custom_itemtycd = (frappe.form_dict.get("itemtycd") or "").strip()
    custom_orgnnatcd = (frappe.form_dict.get("itemOriginCountryCd") or "").strip()
    custom_pkgunitcd = (frappe.form_dict.get("itemPackageUnitCd") or "").strip()
    custom_svcchargeyn = (frappe.form_dict.get("svcChargeYn") or "").strip()
    custom_isrcaplcbyn = (frappe.form_dict.get("isrcAplcbYn") or "").strip()
    standard_rate = (frappe.form_dict.get("price") or "").strip()
    vatCatCd  = (frappe.form_dict.get("vatCatCd") or "").strip()


    required_fields = {
        "item_name": item_name,
        "item_group": item_group,
        "qtyUnitCd": qtyUnitCd,
        "itemClassCd": custom_itemclscd,
        "itemtycd": custom_itemtycd,
        "itemOriginCountryCd": custom_orgnnatcd,
        "itemPackageUnitCd": custom_pkgunitcd,
        "svcChargeYn": custom_svcchargeyn,
        "isrcAplcbYn": custom_isrcaplcbyn,
        "price": standard_rate,
        "vatCatCd": vatCatCd 
    }

    for field, value in required_fields.items():
        if not value:
            return send_response(
                status="fail",
                message=f"{field} is required",
                status_code=400,
                http_status=400
            )

    item_code = generate_item_code_random(custom_orgnnatcd, custom_itemtycd, custom_pkgunitcd, qtyUnitCd)

    ensure_uom_exists(qtyUnitCd)
    if frappe.db.exists("Item", {"item_name": item_name}):
        return send_response(
            status="fail",
            message=f"Item '{item_name}' already exists",
            status_code=400,
            http_status=400
        )

    try:
        PAYLOAD = {
            "tpin": ZRA_CLIENT_INSTANCE.get_tpin(),
            "bhfId": ZRA_CLIENT_INSTANCE.get_branch_code(),
            "itemCd": item_code,
            "itemClsCd": custom_itemclscd,
            "itemTyCd": custom_itemtycd,
            "itemNm": item_name,
            "orgnNatCd": custom_orgnnatcd,
            "pkgUnitCd": custom_pkgunitcd,
            "qtyUnitCd": qtyUnitCd,
            "dftPrc": standard_rate,
            "vatCatCd": vatCatCd,
            "svcChargeYn": custom_svcchargeyn,
            "sftyQty": 0,
            "isrcAplcbYn": custom_isrcaplcbyn,
            "useYn": "Y",
            "regrNm": frappe.session.user,
            "regrId": frappe.session.user,
            "modrNm": frappe.session.user,
            "modrId": frappe.session.user
        }

        result = ZRA_CLIENT_INSTANCE.create_item_zra_client(PAYLOAD)
        data = result.json()
        print(data)
        if data.get("resultCd") != "000":
            return send_response(
                status="error",
                message=data.get("resultMsg", "Item Sync Failed"),
                status_code=400,
                http_status=400
            )

        item = frappe.get_doc({
            "doctype": "Item",
            "item_name": item_name,
            "item_code": item_code,
            "item_group": item_group,
            "stock_uom": qtyUnitCd,
            "custom_itemclscd": custom_itemclscd,
            "custom_itemtycd": custom_itemtycd,
            "custom_orgnnatcd": custom_orgnnatcd,
            "custom_pkgunitcd": custom_pkgunitcd,
            "custom_svcchargeyn": custom_svcchargeyn,
            "custom_isrcaplcbyn": custom_isrcaplcbyn,
            "is_stock_item": 1,
            "standard_rate": standard_rate,
            "custom_vattycd": vatCatCd 
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
        items = frappe.get_all(
            "Item",
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
                "custom_vattycd",
            ],
            filters={"disabled": 0},  
            order_by="creation desc"
        )

        return send_response(
            status="success",
            message=f"{len(items)} items fetched successfully",
            data=items,
            status_code=200,
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
    item_code = (frappe.form_dict.get("item_code") or "").strip()
    if not item_code:
        return send_response(
            status="fail",
            message="item_code is required",
            status_code=400,
            http_status=400
        )

    try:
        item = frappe.get_all(
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
                "custom_vattycd",
            ],
            limit_page_length=1
        )

        if not item:
            return send_response(
                status="fail",
                message=f"Item with code '{item_code}' not found",
                status_code=404,
                http_status=404
            )

        return send_response(
            status="success",
            message=f"Item '{item_code}' fetched successfully",
            data=item[0],
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
def delete_item_by_code_api():
    item_code = frappe.local.request.args.get("item_code")
    if not item_code:
        return send_response(
            status="fail",
            message="item_code is required",
            status_code=400,
            http_status=400
        )

    try:
        item = frappe.get_doc("Item", {"item_code": item_code})
    except frappe.DoesNotExistError:
        return send_response(
            status="fail",
            message=f"Item with code '{item_code}' does not exist",
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

    item_code = frappe.local.request.args.get("item_code")
    if not item_code:
        return send_response(
            status="fail",
            message="item_code is required",
            status_code=400,
            http_status=400
        )

    try:
        item = frappe.get_doc("Item", {"item_code": item_code})
    except frappe.DoesNotExistError:
        return send_response(
            status="fail",
            message=f"Item '{item_code}' does not exist",
            status_code=404,
            http_status=404
        )

    try:
        payload = frappe.local.request.get_data(as_text=True)
        data = json.loads(payload) if payload else {}
    except Exception:
        return send_response(
            status="fail",
            message="Invalid JSON payload",
            status_code=400,
            http_status=400
        )

    updated_fields = {}
    allowed_fields = [
        "item_name",
        "item_group",
        "vatCatCd",
        "isrcAplcbYn",
        "svcChargeYn",
        "itemClassCd",
        "price"
    ]

    for field in allowed_fields:
        if field in data:
            setattr(item, field, data[field])
            updated_fields[field] = data[field]
            print(f"{field} = {data[field]}")

    if not updated_fields:
        return send_response(
            status="fail",
            message="No valid fields provided for update. Allowed fields are: "
                    "item_name, item_group, vatCatCd, isrcAplcbYn, svcChargeYn, itemClassCd, price",
            status_code=400,
            http_status=400
        )

    if "vatCatCd" in updated_fields:
        item.custom_vattycd = updated_fields["vatCatCd"]
    if "isrcAplcbYn" in updated_fields:
        item.custom_isrcaplcbyn = updated_fields["isrcAplcbYn"]
    if "svcChargeYn" in updated_fields:
        item.custom_svcchargeyn = updated_fields["svcChargeYn"]
    if "itemClassCd" in updated_fields:
        item.custom_itemclscd = updated_fields["itemClassCd"]
    if "price" in updated_fields:
        item.standard_rate = updated_fields["price"]

    try:
        PAYLOAD = {
            "tpin": ZRA_CLIENT_INSTANCE.get_tpin(),
            "bhfId": ZRA_CLIENT_INSTANCE.get_branch_code(),
            "itemCd": item.item_code,
            "itemClsCd": item.custom_itemclscd,
            "itemTyCd": item.custom_itemtycd,
            "itemNm": item.item_name,
            "orgnNatCd": item.custom_orgnnatcd,
            "pkgUnitCd": item.custom_pkgunitcd,
            "qtyUnitCd": item.stock_uom,
            "dftPrc": float(item.standard_rate or 0),
            "vatCatCd": item.custom_vattycd or "A",
            "svcChargeYn": item.custom_svcchargeyn or "N",
            "sftyQty": 0,
            "isrcAplcbYn": item.custom_isrcaplcbyn or "N",
            "useYn": "Y",
            "regrNm": frappe.session.user,
            "regrId": frappe.session.user,
            "modrNm": frappe.session.user,
            "modrId": frappe.session.user
        }

        print(json.dumps(PAYLOAD, indent=4))

        result = ZRA_CLIENT_INSTANCE.update_item_zra_client(PAYLOAD)
        data = result.json()
        print(data)

        if data.get("resultCd") != "000":
            return send_response(
                status="error",
                message=data.get("resultMsg", "Item Update Sync Failed"),
                status_code=400,
                http_status=400
            )

        item.save(ignore_permissions=True)
        frappe.db.commit()

        return send_response(
            status="success",
            message=f"Item '{item_code}' updated successfully",
            status_code=200,
            http_status=200
        )

    except Exception as e:
        frappe.log_error(str(e), "ERPNext Update Item Error")
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
        item_groups = frappe.get_all(
            "Item Group",
            fields=["name", "item_group_name"],
            order_by="item_group_name asc"
        )

        return send_response(
            status="success",
            message=f"{len(item_groups)} item groups fetched successfully",
            data=item_groups,
            status_code=200,
            http_status=200
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
def create_item_group_api():
    item_group_name = (frappe.form_dict.get("item_group_name") or "").strip()
    parent_item_group = (frappe.form_dict.get("parent_item_group") or "All Item Groups").strip()
    is_group = frappe.form_dict.get("is_group")

    if not item_group_name:
        return send_response(
            status="fail",
            message="item_group_name is required",
            status_code=400,
            http_status=400
        )
    if isinstance(is_group, str):
        is_group = is_group.lower() in ["true", "1", "yes"]

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
        # Check if Item Group exists
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