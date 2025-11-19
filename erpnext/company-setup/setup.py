from erpnext.zra_client.generic_api import send_response
from datetime import datetime, date
from frappe import _
import frappe


def get_next_custom_company_id():
    last = frappe.db.sql(
        """
        SELECT custom_company_id
        FROM `tabCompany`
        WHERE custom_company_id IS NOT NULL AND custom_company_id != ''
        ORDER BY CAST(custom_company_id AS UNSIGNED) DESC
        LIMIT 1
        """,
        as_dict=True
    )

    if last:
        return str(int(last[0].custom_company_id) + 1)
    else:
        return "1"


def validate_parent_company(parent_company):
    if frappe.db.exists("Company", parent_company):
        return True
    else:
        send_response(
            status="fail",
            message=f"Parent Company '{parent_company}' not found.",
            status_code=400,
            http_status=400
        )
        return False

def validate_company_registration_number(company_registration_number):
    if frappe.db.exists("Company", {"custom_company_registration_number": company_registration_number}):
        send_response(
            status="fail",
            message=f"Company with Registration Number '{company_registration_number}' already exists",
            status_code=400,
            http_status=400
        )
        return False
    return True

def validate_date(custom_date_of_incoporation):
    try:
        incorporation_date = datetime.strptime(custom_date_of_incoporation, "%d-%m-%Y").date()
    except ValueError:
        send_response(
            status="fail",
            message="Date of Incorporation must be in DD-MM-YYYY format",
            status_code=400,
            http_status=400
        )
        return False
    if incorporation_date > date.today():
        send_response(
            status="fail",
            message="Date of Incorporation cannot be in the future",
            status_code=400,
            http_status=400
        )
        return False

    return True

@frappe.whitelist(allow_guest=False, methods=["POST"])
def create_company_api():
    try:
        data = frappe.form_dict
        company_name = data.get("company_name")
        currency = data.get("currency")

        country = data.get("country")
        domain = data.get("domain")
        tax_id = data.get("company_tpin")
        phone_no = data.get("phone_no")
        email = data.get("email")
        custom_company_status = data.get("custom_company_status")
        custom_company_registration_number = data.get("custom_company_registration_number")
        custom_date_of_incoporation = data.get("custom_date_of_incoporation")
        custom_company_type = data.get("custom_company_type")
        custom_company_industry_type = data.get("custom_company_industry_type")
        custom_financial_year_begins = data.get("custom_financial_year_begins")
        custom_alternate_number = data.get("custom_alternate_number")
        custom_company_phone_number = data.get("custom_company_phone_number")
        custom_address_line_1 = data.get("custom_address_line_1")
        custom_address_line_2 = data.get("custom_address_line_2")
        custom_district = data.get("custom_district")
        custom_city = data.get("custom_city")
        custom_province = data.get("custom_province")
        custom_postal_code = data.get("custom_postal_code")
        custom_time_zone = data.get("custom_time_zone")
        custom_swift_code = data.get("custom_swift_code")

        if not company_name:
            return send_response(status="fail", message="Company name is required", status_code=400, http_status=400)

        if frappe.db.exists("Company", {"company_name": company_name}):
            return send_response(status="fail", message="Company already exists", status_code=400, http_status=400)
        
        if not tax_id:
            return send_response(status="fail", message="Company TPIN is required", status_code=400, http_status=400)
        
        if frappe.db.exists("Company", {"tax_id": tax_id}):
            return send_response(status="fail", message="Company with this TPIN already exists", status_code=400, http_status=400)
        
        if not email:
            return send_response(status="fail", message="Email is required", status_code=400, http_status=400)
        
        if not email.count("@") == 1 or not email.count(".") >= 1:
            return send_response(status="fail", message="Invalid email format", status_code=400, http_status=400)
        
        if frappe.db.exists("Company", {"email": email}):
            return send_response(status="fail", message="Company with this email already exists", status_code=400, http_status=400)
        

        next_id = get_next_custom_company_id()

        company = frappe.get_doc({
            "doctype": "Company",
            "default_currency": currency,
            "company_name": company_name,
            "country": country,
            "domain": domain,
            "tax_id": tax_id,
            "email": email,
            "custom_company_status": custom_company_status,
            "phone_no": phone_no,
            "custom_company_id": next_id,
            "custom_company_registration_number": custom_company_registration_number,
            "custom_financial_year_begins": custom_financial_year_begins,
            "custom_company_phone_number": custom_company_phone_number,
            "custom_address_line_1": custom_address_line_1,
            "custom_address_line_2": custom_address_line_2,
            "custom_company_type": custom_company_type,
            "custom_province": custom_province,
            "custom_district": custom_district,
            "custom_postal_code": custom_postal_code,
            "custom_time_zone": custom_time_zone,
            "custom_city": custom_city,
            "custom_alternate_number": custom_alternate_number,
            "custom_company_industry_type": custom_company_industry_type,
            "custom_date_of_incoporation": custom_date_of_incoporation
        })

        company.insert(ignore_permissions=True)
        frappe.db.commit()

        return send_response(
            status="success",
            message="Company created successfully",
            data={
                "custom_company_id": company.custom_company_id
            },
            status_code=201,
            http_status=201
        )

    except Exception as e:
        return send_response(
            status="fail",
            message=str(e),
            status_code=500,
            http_status=500
        )


@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_companies_api():
    try:
        companies = frappe.get_all(
            "Company", 
            fields=[
                "custom_company_id",
                "custom_company_registration_number",
                "custom_company_industry_type",
                "custom_company_status",
                "custom_district",
                "default_currency",
                "custom_province",
                "company_name",
                "custom_city",
                "phone_no",
                "country", 
                "tax_id",
                "email",                
                ])
        for company in companies:
            company["company_tpin"] = company.pop("tax_id")
        send_response(
            status="success",
            message="Company list retrieved", 
            data=companies,
            status_code=200,
            http_status=200
        )
        return
    except Exception as e:
        frappe.log_error(message=str(e), title="Get Companies API Error")
        send_response(
            status="fail", 
            message=str(e), 
            status_code=500,
            http_status=500
        )
        return



@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_company_api():
    try:
        id = frappe.form_dict.get("custom_company_id")
        if not id:
            return send_response(
                status="fail",
                message="Company id is required (id)",
                status_code=400,
                http_status=400
            )

        result = frappe.get_list("Company", filters={"custom_company_id": id}, fields=["name"])
        if not result:
            return send_response(status="fail", message="Company not found", status_code=404, http_status=404)

        company = frappe.get_doc("Company", result[0].name)


        data = {
            "default_currency": company.default_currency,
            "company_name": company.company_name,
            "country": company.country,
            "domain": company.domain,
            "company_tpin": company.tax_id,
            "email": company.email,
            "phone_no": company.phone_no,
            "custom_company_registration_number": company.custom_company_registration_number,
            "custom_financial_year_begins": company.custom_financial_year_begins,
            "custom_company_phone_number": company.custom_company_phone_number,
            "custom_address_line_1": company.custom_address_line_1,
            "custom_address_line_2": company.custom_address_line_2,
            "custom_company_type": company.custom_company_type,
            "custom_company_status": company.custom_company_status,
            "custom_province": company.custom_province,
            "custom_district": company.custom_district,
            "custom_postal_code": company.custom_postal_code,
            "custom_time_zone": company.custom_time_zone,
            "custom_city": company.custom_city,
            "custom_alternate_number": company.custom_alternate_number,
            "custom_company_industry_type": company.custom_company_industry_type,
            "custom_date_of_incoporation": company.custom_date_of_incoporation,
            "custom_account_number": company.custom_account_number,
            "custom_account_holder_name": company.custom_account_holder_name,
            "custom_bank_name": company.custom_bank_name,
            "custom_sort_code": company.custom_sort_code,
            "custom_swift_code": company.custom_swift_code_,
            "custom_currency": company.custom_currency,
            "custom_branch_address": company.custom_branch_address,
            "custom_date_of_addition": company.custom_date_of_addition,
            "custom_opening_balance": company.custom_opening_balance,
        }


        return send_response(
            status="success",
            message="Company retrieved successfully",
            data=data,
            status_code=200,
            http_status=200
        )

    except frappe.DoesNotExistError:
        return send_response(
            status="fail",
            message="Company not found",
            status_code=404,
            http_status=404
        )

    except Exception as e:
        frappe.log_error(message=str(e), title="Get Company API Error")
        return send_response(
            status="fail",
            message=str(e),
            status_code=500,
            http_status=500
        )

@frappe.whitelist(allow_guest=False, methods=["PUT"])
def update_accounts_company_info():
    data = frappe.form_dict
    custom_company_id = data.get("custom_company_id")
    
    if not custom_company_id:
        return send_response(
            status="fail",
            message="custom_company_id is required",
            status_code=400,
            http_status=400
        )
    
    result = frappe.get_list("Company", filters={"custom_company_id": custom_company_id}, fields=["name"])
    if not result:
        return send_response(
            status="fail",
            message="Company not found",
            status_code=404,
            http_status=404
        )
    
    company = frappe.get_doc("Company", result[0].name)
    fields_to_update = {
        "custom_account_number": data.get("custom_account_number"),
        "custom_account_holder_name": data.get("custom_account_holder_name"),
        "custom_bank_name": data.get("custom_bank_name"),
        "custom_sort_code": data.get("custom_sort_code"),
        "custom_swift_code_": data.get("custom_swift_code"),
        "custom_currency": data.get("custom_currency"),
        "custom_branch_address": data.get("custom_branch_address"),
        "custom_date_of_addition": data.get("custom_date_of_addition"),
        "custom_opening_balance": data.get("custom_opening_balance"),
    }
    
    for field, value in fields_to_update.items():
        if value is not None:
            company.set(field, value)
    
    company.save()
    
    return send_response(
        status="success",
        message="Company account info updated successfully",
        data={
            "company_name": company.company_name,
            "custom_company_id": company.custom_company_id
        },
        status_code=200
    )

    
    

    
@frappe.whitelist(allow_guest=False, methods=["PUT"])
def update_company_api():
    try:
        data = frappe.form_dict
        name = data.get("name")

        if not name:
            return send_response(status="fail", message=_("Company name is required for update"), status_code=400)

        company = frappe.get_doc("Company", name)

        if data.get("company_name"):
            company.company_name = data.get("company_name")
        if data.get("country"):
            company.country = data.get("country")
        if data.get("domain"):
            company.domain = data.get("domain")

        company.save(ignore_permissions=True)
        frappe.db.commit()

        return send_response(status="success", message=_("Company updated successfully"), data=company.as_dict())

    except frappe.DoesNotExistError:
        return send_response(status="fail", message=_("Company not found"), status_code=404)
    except Exception as e:
        frappe.log_error(message=str(e), title="Update Company API Error")
        return send_response(status="fail", message=str(e), status_code=500)
    

@frappe.whitelist(allow_guest=False, methods=["DELETE"])
def delete_company_api():
    try:
        name = frappe.form_dict.get("company_name")

        if not name:
            return send_response(status="fail", message=_("Company name is required for delete"), status_code=400)

        if not frappe.db.exists("Company", name):
            return send_response(status="fail", message=_("Company not found"), status_code=404)

        frappe.delete_doc("Company", name, ignore_permissions=True)
        frappe.db.commit()

        send_response(
            status="success", 
            message="Company deleted successfully",
            status_code=200,
            http_status=200
        )
        return
    

    except Exception as e:
        frappe.log_error(message=str(e), title="Delete Company API Error")
        send_response(
            status="fail", 
            message=str(e), 
            status_code=500,
            http_status=500
        )
        return



@frappe.whitelist(allow_guest=False, methods=["PUT"])
def update_company_info():
    try:
        data = frappe.form_dict
        custom_company_id = data.get("custom_company_id")
        if not custom_company_id:
           send_response(
                status="fail",
                message="custom_company_id is required",
                status_code=400,
                http_status=400
            )
           return  
 
        company = frappe.get_doc("Company", {"custom_company_id": custom_company_id})
        if not company:
            send_response(
                status="fail",
                message="Company not found",
                status_code=404,
                http_status=404
            ) 
            return
        
        unique_fields = {
            "company_tpin": "tax_id",
            "email": "email",
            "custom_company_registration_number": "custom_company_registration_number"
        }
        for key, frappe_field in unique_fields.items():
            if key in data:
                value = data[key]
                exists = frappe.db.exists("Company", {frappe_field: value, "name": ["!=", company.name]})
                if exists:
                    send_response(
                        status="fail",
                        message=f"Company with this {frappe_field.replace('_', ' ')} already exists",
                        status_code=400,
                        http_status=400
                    )
                    return
                
        field_map = {
            "company_tpin": "tax_id"
        }

        for key, value in data.items():
            if key == "custom_company_id":
                continue
            frappe_field = field_map.get(key, key)
            if hasattr(company, frappe_field):
                setattr(company, frappe_field, value)

        company.save()
        frappe.db.commit()
        send_response(
            status="success",
            message="Company information updated successfully",
            status_code=200,
            http_status=200
        )
        return

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "update_company_info API Error")
        send_response(
            status="fail",
            message=str(e),
            status_code=500,
            http_status=500
        )
        return
