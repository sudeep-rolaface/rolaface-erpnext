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
    
    
@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_suppliers():
    
    data = frappe.form_dict
    page = data.get("page", 1)
    page_size = data.get("page_size", 10)
    status = data.get("status")
    supplier_id = data.get("supplierId")
    page = int(page)
    page_size = int(page_size)
    start = (page - 1) * page_size


    filters = {}

    if status:
        filters["custom_status"] = status

    if supplier_id:
        filters["custom_supplier_id"] = supplier_id


    total = frappe.db.count("Supplier", filters=filters)

    total_pages = (total + page_size - 1) // page_size
    has_next = page < total_pages
    has_prev = page > 1
    suppliers = frappe.get_all(
        "Supplier",
        filters=filters,
        fields=[
            "custom_supplier_id",
            "custom_status",
            "supplier_name",
            "tax_id",
            "default_currency",
            "mobile_no",
            "email_id",
            "custom_supplier_code",
        ],
        limit_start=start,
        limit_page_length=page_size,
        order_by="creation desc"
    )
    for i in suppliers:
        i["supplierId"] = i.pop("custom_supplier_id")
        i["supplierCode"] = i.pop("custom_supplier_code")
        i["supplierName"] = i.pop("supplier_name")
        i["currency"] = i.pop("default_currency")
        i["emailId"] = i.pop("email_id")
        i["phoneNo"] = i.pop("mobile_no")
        i["tpin"] = i.pop("tax_id")
        i["status"] = i.pop("custom_status")

    send_response(
        status="success",
        message="Suppliers fetched successfully",
        data={
            "suppliers": suppliers,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": total_pages,
                "has_next": has_next,
                "has_prev": has_prev
            }
        },
        status_code=200,
        http_status=200
    )


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_supplier_details_id():
    
    data = frappe.form_dict
    custom_supplier_id = data.get("supplierId")
    
    if not custom_supplier_id:
        return send_response(
            status="error",
            message="Supplier ID is required",
            data={},
            status_code=400,
            http_status=400
        )
        
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
        "supplierName": supplier.name,
        "supplierCode": supplier.custom_supplier_code,
        "supplierId": supplier.custom_supplier_id,
        "bankAccount": supplier.custom_bank_account,
        "accountHolde": supplier.custom_suppliers_account_holder_name,
        "dateOfAddition": supplier.custom_supplier_date_of_addition,
        "openingBalance": supplier.custom_supplier_opening_balance,
        "paymentTerms": supplier.custom_supplier_payment_terms,
        "branchAddress": supplier.custom_supplier_bank_address,
        "alternateNo": supplier.custom_supplier_alternate_no,
        "postalCode": supplier.custom_supplier_postal_code,
        "swiftCode": supplier.custom_supplier_swift_code,
        "sortCode": supplier.custom_supplier_sort_code,
        "district": supplier.custom_supplier_district,
        "province": supplier.custom_supplier_province,
        "supplierCode": supplier.custom_supplier_code,
        "accountNumber": supplier.custom_account_no,
        "city": supplier.custom_supplier_city,
        "currency": supplier.default_currency,
        "contactPerson": supplier.supplier_primary_contact,
        "billingAddressLine1": supplier.custom_supplier_address_line_2,
        "billingAddressLine2": supplier.custom_supplier_address_line_1,
        "mobile_no": supplier.mobile_no,
        "emailId": supplier.email_id,
        "country": supplier.country,
        "tpin": supplier.tax_id,
        "status": supplier.custom_status
    }
    return send_response(
        status="success",
        message="Supplier details fetched successfully",
        data=supplier_details,
        status_code=200,
        http_status=200
    )

    
@frappe.whitelist(allow_guest=False, methods=["POST"])
def create_supplier():
    data = frappe.form_dict

    custom_suppliers_account_holder_name = data.get("accountHolder")
    custom_supplier_date_of_addition = data.get("dateOfAddition")
    custom_supplier_opening_balance = data.get("openingBalance")
    custom_supplier_payment_terms = data.get("paymentTerms")
    custom_supplier_bank_address = data.get("branchAddress")
    custom_supplier_alternate_no = data.get("alternateNo")
    custom_supplier_postal_code = data.get("billingPostalCode")
    custom_supplier_swift_code = data.get("swiftCode")
    custom_supplier_sort_code = data.get("sortCode")
    supplier_primary_contact = data.get("contactPerson")
    custom_supplier_address_line_1 = data.get("billingAddressLine1")
    custom_supplier_address_line_2 = data.get("billingAddressLine2")
    custom_supplier_district = data.get("district")
    custom_supplier_province = data.get("province")
    custom_supplier_code = data.get("supplierCode")
    custom_account_no = data.get("accountNumber")
    custom_supplier_city = data.get("billingCity")
    default_currency = data.get("currency")
    supplier_name = data.get("supplierName")
    tax_id = data.get("tpin")
    mobile_no = data.get("phoneNo")
    email_id = data.get("emailId")
    bankAccount = data.get("bankAccount")
    country = data.get("billingCountry")
    status = data.get("status", "Active")

    if not supplier_name:
        return send_response(status="fail", message="supplierName is required", status_code=400, http_status=400)

    if not tax_id:
        return send_response(status="fail", message="Supplier TPIN is required", status_code=400, http_status=400)
    
    if tax_id and len(tax_id) != 10:
        return send_response(
            status="fail",
            message="Supplier TPIN must be exactly 10 characters long",
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
            "custom_bank_account": bankAccount,
            "country": country,
            "tax_id": tax_id,
            "custom_status": status
        })

        supplier.insert()
        frappe.db.commit()

        return send_response(
            status="success",
            message="Supplier created successfully",
            data={},
            status_code=201,
            http_status=201
        )

    except Exception as e:
        return send_response(
            status="error",
            message=f"Error creating supplier: {str(e)}",
            data={},
            status_code=500,
            http_status=500
        )



@frappe.whitelist(allow_guest=False, methods=["PATCH"])
def update_supplier():
    data = frappe.form_dict

    supplier_id = data.get("supplierId")
    tax_id = data.get("tpin")
    email_id = data.get("emailId")
    supplier_name_input = data.get("supplierName")

    if not supplier_id:
        return send_response(
            status="fail",
            message="supplierId is required",
            status_code=400,
            http_status=400
        )

    supplier_name = frappe.db.get_value(
        "Supplier",
        {"custom_supplier_id": supplier_id},
        "name"
    )

    if not supplier_name:
        return send_response(
            status="fail",
            message="Supplier not found",
            status_code=404,
            http_status=404
        )

    supplier = frappe.get_doc("Supplier", supplier_name)

    if tax_id:
        if len(tax_id) != 10:
            return send_response(
                status="fail",
                message="Supplier TPIN must be exactly 10 characters long",
                status_code=400,
                http_status=400
            )

        if not tax_id.isalnum():
            return send_response(
                status="fail",
                message="Supplier TPIN must be alphanumeric",
                status_code=400,
                http_status=400
            )

        if tax_id != supplier.tax_id and frappe.db.exists(
            "Supplier", {"tax_id": tax_id}
        ):
            return send_response(
                status="fail",
                message=f"Supplier with TPIN '{tax_id}' already exists",
                status_code=400,
                http_status=400
            )

    if email_id:
        if "@" not in email_id or "." not in email_id:
            return send_response(
                status="fail",
                message="Invalid email format",
                status_code=400,
                http_status=400
            )

        if email_id != supplier.email_id and frappe.db.exists(
            "Supplier", {"email_id": email_id}
        ):
            return send_response(
                status="fail",
                message=f"Supplier with email '{email_id}' already exists",
                status_code=400,
                http_status=400
            )

    if supplier_name_input:
        if supplier_name_input != supplier.supplier_name and frappe.db.exists(
            "Supplier", {"supplier_name": supplier_name_input}
        ):
            return send_response(
                status="fail",
                message=f"Supplier with name '{supplier_name_input}' already exists",
                status_code=400,
                http_status=400
            )


    field_map = {
        "supplierName": "supplier_name",
        "accountHolder": "custom_suppliers_account_holder_name",
        "dateOfAddition": "custom_supplier_date_of_addition",
        "openingBalance": "custom_supplier_opening_balance",
        "paymentTerms": "custom_supplier_payment_terms",
        "branchAddress": "custom_supplier_bank_address",
        "alternateNo": "custom_supplier_alternate_no",
        "billingPostalCode": "custom_supplier_postal_code",
        "swiftCode": "custom_supplier_swift_code",
        "sortCode": "custom_supplier_sort_code",
        "contactPerson": "custom_supplier_contact_name",
        "billingAddressLine1": "custom_supplier_address_line_1",
        "billingAddressLine2": "custom_supplier_address_line_2",
        "district": "custom_supplier_district",
        "province": "custom_supplier_province",
        "supplierCode": "custom_supplier_code",
        "accountNumber": "custom_account_no",
        "billingCity": "custom_supplier_city",
        "currency": "default_currency",
        "phoneNo": "mobile_no",
        "emailId": "email_id",
        "bankAccount": "custom_bank_account",
        "billingCountry": "country",
        "status": "custom_status"
    }

    for payload_key, doc_field in field_map.items():
        value = data.get(payload_key)
        if value not in (None, ""):
            supplier.set(doc_field, value)

    if tax_id:
        supplier.set("tax_id", tax_id)

    try:
        supplier.save()
        frappe.db.commit()

        return send_response(
            status="success",
            message="Supplier updated successfully",
            data=[],
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



@frappe.whitelist(allow_guest=False, methods=["DELETE"])
def delete_supplier():
    data = frappe.form_dict
    custom_supplier_id = data.get("supplierId")

    if not custom_supplier_id:
        return send_response(
            status="error",
            message="supplierId is required",
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
            data={"supplierId": custom_supplier_id},
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

    