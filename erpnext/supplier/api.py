from erpnext.zra_client.generic_api import send_response
import frappe

def get_next_custom_supplier_id():
    last = frappe.db.sql(
        """
        SELECT custom_supplier_id
        FROM `tabSupplier`
        WHERE custom_supplier_id IS NOT NULL AND custom_supplier_id != ''
        ORDER BY CAST(custom_supplier_id AS UNSIGNED) DESC
        LIMIT 1
        """,
        as_dict=True
    )

    if last:
        return str(int(last[0].custom_supplier_id) + 1)
    else:
        return "1"

@frappe.whitelist()
def get_suppliers():
    suppliers = frappe.get_all(
        "Supplier",
        fields=["custom_supplier_id", "supplier_name", "tax_id", "default_currency", "country", "mobile_no", "email_id"],
    )
    
    for i in suppliers:
        i['supplier_tpin'] = i.pop('tax_id')
    
    send_response(
        status="success",
        message="Suppliers fetched successfully",
        data=suppliers,
        status_code=200,
        http_status=200
    )

@frappe.whitelist()
def get_supplier_details_id(custom_supplier_id):
    supplier = frappe.db.get_value(
        "Supplier",
        {"custom_supplier_id": custom_supplier_id},
        "name"
    )
    
    if not custom_supplier_id:
        return send_response(
            status="error",
            message="Custom Supplier ID is required",
            data={},
            status_code=400,
            http_status=400
        )
    if not supplier:
        return send_response(
            status="error",
            message="Supplier not found",
            data={},
            status_code=404,
            http_status=404
        )

    supplier = frappe.get_doc("Supplier", supplier)
    supplier_details = {
        "supplier_name": supplier.name,
        "custom_supplier_id": supplier.custom_supplier_id,
        "custom_suppliers_account_holder_name": supplier.custom_suppliers_account_holder_name,
        "custom_supplier_date_of_addition": supplier.custom_supplier_date_of_addition,
        "custom_supplier_opening_balance": supplier.custom_supplier_opening_balance,
        "custom_supplier_payment_terms": supplier.custom_supplier_payment_terms,
        "custom_supplier_bank_address": supplier.custom_supplier_bank_address,
        "custom_supplier_alternate_no": supplier.custom_supplier_alternate_no,
        "custom_supplier_postal_code": supplier.custom_supplier_postal_code,
        "custom_supplier_swift_code": supplier.custom_supplier_swift_code,
        "custom_supplier_sort_code": supplier.custom_supplier_sort_code,
        "custom_supplier_district": supplier.custom_supplier_district,
        "custom_supplier_province": supplier.custom_supplier_province,
        "custom_supplier_code": supplier.custom_supplier_code,
        "custom_account_no": supplier.custom_account_no,
        "custom_supplier_city": supplier.custom_supplier_city,
        "default_currency": supplier.default_currency,
        "supplier_primary_contact": supplier.supplier_primary_contact,
        "custom_supplier_address_line_2": supplier.custom_supplier_address_line_2,
        "custom_supplier_address_line_1": supplier.custom_supplier_address_line_1,
        "mobile_no": supplier.mobile_no,
        "email_id": supplier.email_id,
        "country": supplier.country,
        "supplier_tpin": supplier.tax_id,
    }
    return send_response(
        status="success",
        message="Supplier details fetched successfully",
        data=supplier_details,
        status_code=200,
        http_status=200
    )

    
@frappe.whitelist()
def create_supplier():
    data = frappe.form_dict

    custom_suppliers_account_holder_name = data.get("custom_suppliers_account_holder_name")
    custom_supplier_date_of_addition = data.get("custom_supplier_date_of_addition")
    custom_supplier_opening_balance = data.get("custom_supplier_opening_balance")
    custom_supplier_payment_terms = data.get("custom_supplier_payment_terms")
    custom_supplier_bank_address = data.get("custom_supplier_bank_address")
    custom_supplier_alternate_no = data.get("custom_supplier_alternate_no")
    custom_supplier_postal_code = data.get("custom_supplier_postal_code")
    custom_supplier_swift_code = data.get("custom_supplier_swift_code")
    custom_supplier_sort_code = data.get("custom_supplier_sort_code")
    supplier_primary_contact = data.get("supplier_primary_contact")
    custom_supplier_address_line_1 = data.get("custom_supplier_address_line_1")
    custom_supplier_address_line_2 = data.get("custom_supplier_address_line_2")
    custom_supplier_district = data.get("custom_supplier_district")
    custom_supplier_province = data.get("custom_supplier_province")
    custom_supplier_code = data.get("custom_supplier_code")
    custom_account_no = data.get("custom_account_no")
    custom_supplier_city = data.get("custom_supplier_city")
    default_currency = data.get("default_currency")
    supplier_name = data.get("supplier_name")
    tax_id = data.get("supplier_tpin")
    mobile_no = data.get("mobile_no")
    email_id = data.get("email_id")
    country = data.get("country")

    if not supplier_name:
        return send_response("fail", "supplier_name is required", 400, 400)

    if not tax_id:
        return send_response("fail", "Supplier TPIN is required", 400, 400)
    
    if tax_id and len(tax_id) != 10:
        return send_response(
            status="fail",
            message="Supplier TPIN must be exactly 11 characters long",
            status_code=400,
            http_status=400
        )
        
    if tax_id and not tax_id.isalnum():
        return send_response(
            status="fail",
            message= "Supplier TPIN must be alphanumeric",
            status_code=400,
            http_status=400
        )
        
    

    if not email_id:
        return send_response(
            status="fail", 
            message="email_id is required", 
            status_code=400, 
            http_status= 400
        )

    if frappe.db.exists("Supplier", {"tax_id": tax_id}):
        return send_response(
            status="fail",
            message=f"Supplier with TPIN '{tax_id}' already exists",
            status_code=400,
            http_status=400
        )

    if "@" not in email_id or "." not in email_id:
        return send_response(
            status="fail",
            message="Invalid email format",
            status_code=400,
            http_status=400
        )

    if frappe.db.exists("Supplier", {"email_id": email_id}):
        return send_response(
            status="fail",
            message=f"Supplier with email '{email_id}' already exists",
            status_code=400,
            http_status=400
        )

    if frappe.db.exists("Supplier", {"supplier_name": supplier_name}):
        return send_response(
            status="fail",
            message=f"Supplier with name '{supplier_name}' already exists",
            status_code=400,
            http_status=400
        )

    supplier_id = get_next_custom_supplier_id()

    try:
        supplier = frappe.get_doc({
            "doctype": "Supplier",
            "supplier_name": supplier_name,
            "custom_suppliers_account_holder_name": custom_suppliers_account_holder_name,
            "custom_supplier_date_of_addition": custom_supplier_date_of_addition,
            "custom_supplier_opening_balance": custom_supplier_opening_balance,
            "custom_supplier_payment_terms": custom_supplier_payment_terms,
            "custom_supplier_bank_address": custom_supplier_bank_address,
            "custom_supplier_alternate_no": custom_supplier_alternate_no,
            "custom_supplier_postal_code": custom_supplier_postal_code,
            "custom_supplier_swift_code": custom_supplier_swift_code,
            "custom_supplier_sort_code": custom_supplier_sort_code,
            "custom_supplier_contact_name": supplier_primary_contact,
            "custom_supplier_address_line_1": custom_supplier_address_line_1,
            "custom_supplier_address_line_2": custom_supplier_address_line_2,
            "custom_supplier_district": custom_supplier_district,
            "custom_supplier_province": custom_supplier_province,
            "custom_supplier_code": custom_supplier_code,
            "custom_account_no": custom_account_no,
            "custom_supplier_city": custom_supplier_city,
            "default_currency": default_currency,
            "custom_supplier_id": supplier_id,
            "mobile_no": mobile_no,
            "email_id": email_id,
            "country": country,
            "tax_id": tax_id
        })

        supplier.insert()
        frappe.db.commit()

        return send_response(
            "success",
            "Supplier created successfully",
            {"supplier_name": supplier.name},
            201,
            201
        )

    except Exception as e:
        return send_response(
            "error",
            f"Error creating supplier: {str(e)}",
            {},
            500,
            500
        )

@frappe.whitelist()
def update_supplier():
    data = frappe.form_dict
    custom_supplier_id = data.get("custom_supplier_id")
    supplier_tpin = data.get("supplier_tpin") 

    if not custom_supplier_id:
        return send_response(
            status="error",
            message="Custom Supplier ID is required",
            data={},
            status_code=400,
            http_status=400
        )

    supplier_name = frappe.db.get_value(
        "Supplier",
        {"custom_supplier_id": custom_supplier_id},
        "name"
    )

    if not supplier_name:
        return send_response(
            status="error",
            message="Supplier not found",
            data={},
            status_code=404,
            http_status=404
        )

    try:
        supplier = frappe.get_doc("Supplier", supplier_name)

        fields_to_update = [
            "custom_suppliers_account_holder_name",
            "custom_supplier_date_of_addition",
            "custom_supplier_opening_balance",
            "custom_supplier_payment_terms",
            "custom_supplier_bank_address",
            "custom_supplier_alternate_no",
            "custom_supplier_postal_code",
            "custom_supplier_swift_code",
            "custom_supplier_sort_code",
            "custom_supplier_district",
            "custom_supplier_province",
            "custom_supplier_code",
            "custom_account_no",
            "custom_supplier_city",
            "default_currency",
            "custom_supplier_address_line_2",
            "custom_supplier_address_line_1",
            "supplier_primary_contact",
            "supplier_primary_address",
            "mobile_no",
            "email_id",
            "country",
            "supplier_name",
        ]

    
        for field in fields_to_update:
            if field in data and data.get(field) not in (None, ""):
                supplier.set(field, data.get(field))
        if supplier_tpin:
            supplier.set("tax_id", supplier_tpin)

        supplier.save()
        frappe.db.commit()

        return send_response(
            status="success",
            message="Supplier updated successfully",
            data={"supplier_name": supplier.name},
            status_code=200,
            http_status=200
        )

    except Exception as e:
        return send_response(
            status="error",
            message=f"Error updating supplier: {str(e)}",
            data={},
            status_code=500,
            http_status=500
        )


@frappe.whitelist()
def delete_supplier():
    data = frappe.form_dict
    custom_supplier_id = data.get("custom_supplier_id")

    if not custom_supplier_id:
        return send_response(
            status="error",
            message="Custom Supplier ID is required",
            data={},
            status_code=400,
            http_status=400
        )

    supplier_name = frappe.db.get_value(
        "Supplier",
        {"custom_supplier_id": custom_supplier_id},
        "name"
    )

    if not supplier_name:
        return send_response(
            status="error",
            message="Supplier not found",
            data={},
            status_code=404,
            http_status=404
        )

    try:
        frappe.delete_doc("Supplier", supplier_name, force=True)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Supplier deleted successfully",
            data={"custom_supplier_id": custom_supplier_id},
            status_code=200,
            http_status=200
        )

    except Exception as e:
        return send_response(
            status="error",
            message=f"Error deleting supplier: {str(e)}",
            data={},
            status_code=500,
            http_status=500
        )

    