import frappe
from frappe import _

DOCTYPE = "Packaging Unit"

@frappe.whitelist(allow_guest=True)
def get_all_packaging_units():
    data = frappe.get_all(
        DOCTYPE,
        fields=["code", "code_name", "code_description"],
        order_by="code asc"
    )
    return {"status": "success", "data": data}


# @frappe.whitelist(allow_guest=True)
# def get_packaging_unit(code, standard=None):
#     filters = {"code": code}
#     if standard:
#         filters["standard"] = standard

#     doc = frappe.db.get_value(
#         "Packaging Unit",
#         filters,
#         ["code", "code_name", "code_description", "standard"],
#         as_dict=True
#     )
#     if not doc:
#         frappe.throw(_("Code '{0}' not found").format(code), frappe.DoesNotExistError)
#     return {"status": "success", "data": doc}


@frappe.whitelist(allow_guest=True)
def get_packaging_unit(code):
    doc = frappe.db.get_value(
        "Packaging Unit",
        {"code": code, "standard": "GLOBAL"},
        ["code", "code_name", "code_description"],
        as_dict=True
    )
    if not doc:
        frappe.throw(_("Code '{0}' not found").format(code), frappe.DoesNotExistError)
    return {"status": "success", "data": doc}

@frappe.whitelist(allow_guest=False)
def create_packaging_unit(code, code_name, code_description=None):
    if frappe.db.exists(DOCTYPE, {"code": code}):
        frappe.throw(_("Code '{0}' already exists").format(code))
    doc = frappe.get_doc({"doctype": DOCTYPE, "code": code, "code_name": code_name, "code_description": code_description})
    doc.insert(ignore_permissions=False)
    frappe.db.commit()
    return {"status": "success", "message": "Created", "name": doc.name}


@frappe.whitelist(allow_guest=False)
def update_packaging_unit(code, code_name=None, code_description=None):
    name = frappe.db.get_value(DOCTYPE, {"code": code}, "name")
    if not name:
        frappe.throw(_("Code '{0}' not found").format(code))
    doc = frappe.get_doc(DOCTYPE, name)
    if code_name: doc.code_name = code_name
    if code_description is not None: doc.code_description = code_description
    doc.save(ignore_permissions=False)
    frappe.db.commit()
    return {"status": "success", "message": "Updated"}


@frappe.whitelist(allow_guest=False)
def delete_packaging_unit(code):
    name = frappe.db.get_value(DOCTYPE, {"code": code}, "name")
    if not name:
        frappe.throw(_("Code '{0}' not found").format(code))
    frappe.delete_doc(DOCTYPE, name, ignore_permissions=False)
    frappe.db.commit()
    return {"status": "success", "message": "Deleted"}
