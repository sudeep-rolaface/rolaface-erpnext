from erpnext.zra_client.generic_api import send_response
from datetime import datetime, date
from frappe import _
import frappe



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
        country = data.get("country")
        domain = data.get("domain")
        currency = data.get("currency")
        tax_id = data.get("customer_tpin")
        phone_no = data.get("phone_no")
        email = data.get("email")
        parent_company = data.get("parent_company")
        custom_company_registration_number = data.get("custom_company_registration_number")
        custom_date_of_incoporation = data.get("custom_date_of_incoporation")
        isGroup = None

        if not custom_company_registration_number:
            send_response(
                status="fail",
                message="Company Registration Number must not be empty (custom_company_registration_number).",
                status_code=400,
                http_status=400
            )
        if len(custom_company_registration_number) != 10:
            send_response(
                status="fail",
                message="Company Registration Number must be exactly 10 characters long",
                status_code=400,
                http_status=400
            )
            return
        


        if not custom_date_of_incoporation:
            send_response(
                status="fail",
                message="Date of Incorporation must not be empty (custom_date_of_incoporation).",
                status_code=400,
                http_status=400
            )
            return

        is_valid = validate_company_registration_number(custom_company_registration_number)
        if not is_valid:
            return
        

        if not validate_date(custom_date_of_incoporation):
            return


        if parent_company:
            if not validate_parent_company(parent_company):
                return

            isGroup == 1
        if not tax_id:
            send_response(
                status="fail",
                message="Company TPIN is required (customer_tpin)",
                status_code=400,
                http_status=400
            )
            return 

        if not phone_no:
            send_response(
                status="fail",
                message="Company mobile number is required (phone_no)",
                status_code=400,
                http_status=400
            )
            return

        if not email:
            send_response(
                status="fail",
                message="Company email address is required (email)",
                status_code=400,
                http_status=400
            )
            return



        if not currency:
            send_response(
                status="fail",
                message="The company currency is required and cannot be empty.(currency)",
                status_code=400,
                http_status=400
            )
            return

        if not country:
            send_response(
                status="fail",
                message="The company country is required and cannot be empty.(country)",
                status_code=400,
                http_status=400
            )
            return

        if not domain:
            send_response(
                status="fail",
                message="Company domain is required (domain)",
                status_code=400,
                http_status=400
            )
            return

        if not company_name:
            send_response(
                status="fail", 
                message="Company name is required", 
                status_code=400, 
                http_status=400
            )
            return

        if frappe.db.exists("Company", {"company_name": company_name}):
            send_response(
                status="fail", 
                message="Company already exists", 
                status_code=400, 
                http_status=400
                )
            return

        company = frappe.get_doc({
            "doctype": "Company",
            "default_currency": currency,
            "company_name": company_name,
            "country": country,
            "domain": domain,
            "tax_id": tax_id,
            "email": email,
            "phone_no": phone_no,
            "parent_company": parent_company,
            "is_group": isGroup,
            "custom_company_registration_number": custom_company_registration_number,
            "custom_date_of_incoporation": custom_date_of_incoporation
        })
        company.insert(ignore_permissions=True)
        frappe.db.commit()

        return send_response(
            status="success", 
            message="Company created successfully",
            status_code=201,
            http_status=201
            )

    except Exception as e:
        send_response(
            status="fail",
            message=str(e), 
            status_code=500,
            http_status=500
        )
        return


@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_companies_api():
    try:
        companies = frappe.get_all("Company", fields=["company_name", "country", "domain"])
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
        name = frappe.form_dict.get("company_name")
        if not name:
            return send_response(
                status="fail",
                message="Company name is required (name)",
                status_code=400,
                http_status=400
            )

        company = frappe.get_doc("Company", name)

        data = {
            "company_name": company.company_name,
            "email": company.email,
            "customer_tpin": company.tax_id,
            "phone_no": company.phone_no,
            "currency": company.default_currency,
            "country": company.country,
            "domain": company.domain
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

