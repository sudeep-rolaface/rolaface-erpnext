from erpnext.zra_client.generic_api import send_response
import frappe

# ---------------- CREATE FEATURE ----------------
@frappe.whitelist(allow_guest=False, methods=["POST"])
def create_feature_api():
    data = frappe._dict(frappe.local.form_dict)
    required_fields = ["key", "name", "tier", "category", "description"]

    for field in required_fields:
        if not data.get(field):
            return send_response(
                status="fail",
                message=f"'{field}' is required",
                status_code=400,
                http_status=400
            )

    # Check duplicate key
    if frappe.db.exists("ModuleFeature", {"key": data.key}):
        return send_response(
            status="fail",
            message="Feature with this key already exists",
            status_code=409,
            http_status=409
        )

    # Insert new document with 'title' as human-readable name
    doc = frappe.get_doc({
        "doctype": "ModuleFeature",
        "key": data.key,
        "title": data.name,  # human-readable name
        "description": data.description,
        "category": data.category,
        "tier": data.tier
    })
    doc.insert()
    frappe.db.commit()

    return send_response(
        status="success",
        message="Feature created successfully",
        data={"key": doc.key, "name": doc.title},
        status_code=201,
        http_status=201
    )


# ---------------- LIST FEATURES ----------------
@frappe.whitelist()
def list_features_api():
    features = frappe.get_all(
        "ModuleFeature",
        fields=["key", "title", "description", "category", "tier"],
        order_by="title asc"
    )

    # Map 'title' to 'name' for API response
    for f in features:
        f["name"] = f.pop("title")

    return send_response(
        status="success",
        message="All features have been successfully fetched",
        data=features,
        status_code=200,
        http_status=200
    )


# ---------------- GET SINGLE FEATURE ----------------
@frappe.whitelist()
def get_feature_api():
    key = (frappe.form_dict.get("key") or "").strip()
    if not key:
        return send_response(
            status="fail",
            message="Key is required",
            status_code=400,
            http_status=400
        )

    doc_name = frappe.db.exists("ModuleFeature", {"key": key})
    if not doc_name:
        return send_response(
            status="fail",
            message="Feature not found",
            status_code=404,
            http_status=404
        )

    doc = frappe.get_doc("ModuleFeature", doc_name)

    feature_data = {
        "key": doc.key,
        "name": doc.title,
        "description": doc.description,
        "category": doc.category,
        "tier": doc.tier
    }

    return send_response(
        status="success",
        message="Feature fetched successfully",
        data=feature_data,
        status_code=200,
        http_status=200
    )


# ---------------- UPDATE FEATURE ----------------
@frappe.whitelist(allow_guest=False, methods=["PUT"])
def update_feature_api():
    data = frappe._dict(frappe.local.form_dict)

    if not data.get("key"):
        return send_response(
            status="fail",
            message="Key is required",
            status_code=400,
            http_status=400
        )

    doc_name = frappe.db.exists("ModuleFeature", {"key": data.key})
    if not doc_name:
        return send_response(
            status="fail",
            message="Feature not found",
            status_code=404,
            http_status=404
        )

    doc = frappe.get_doc("ModuleFeature", doc_name)
    editable_fields = ["title", "description", "category", "tier"]

    for field in editable_fields:
        if data.get(field):
            doc.set(field, data.get(field))

    doc.save()
    frappe.db.commit()

    updated_data = {
        "key": doc.key,
        "name": doc.title,
        "description": doc.description,
        "category": doc.category,
        "tier": doc.tier
    }

    return send_response(
        status="success",
        message="Feature updated successfully",
        data=updated_data,
        status_code=200,
        http_status=200
    )


@frappe.whitelist(allow_guest=False, methods=["DELETE"])
def delete_feature_api():
    data = frappe._dict(frappe.local.form_dict)
    key = data.get("key")

    if not key:
        return send_response(
            status="fail",
            message="Key is required",
            status_code=400,
            http_status=400
        )

    doc_name = frappe.db.exists("ModuleFeature", {"key": key})
    if not doc_name:
        return send_response(
            status="fail",
            message="Feature not found",
            status_code=404,
            http_status=404
        )

    frappe.delete_doc("ModuleFeature", doc_name)
    frappe.db.commit()

    return send_response(
        status="success",
        message="Feature deleted successfully",
        data={"key": key},
        status_code=200,
        http_status=200
    )
