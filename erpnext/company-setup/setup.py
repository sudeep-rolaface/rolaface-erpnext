import random
import string
from erpnext.zra_client.generic_api import send_response, send_response_list
from datetime import datetime, date
from frappe import _
import frappe
import os
import uuid
from frappe.utils.file_manager import save_file
import os
import uuid
import frappe
import requests
import base64
from collections import defaultdict

SITE_URL = "http://erp.izyanehub.com:8081/"
def generate_random_id(length=8):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def get_accounting_setup(company_name):
    setup = {}

    def get_account(account_name):
        return frappe.db.get_value(
            "Account", {"company": company_name, "account_name": account_name}, "account_name"
        ) or ""

    def get_cost_center(cost_center_name):

        return frappe.db.get_value(
            "Cost Center", {"company": company_name, "cost_center_name": cost_center_name}, "cost_center_name"
        ) or ""

    chart_of_accounts = frappe.db.get_value(
        "Account", {"company": company_name, "is_group": 1, "parent_account": None}, "account_name"
    )
    setup["chartOfAccounts"] = chart_of_accounts or "Standard COA"
    setup["defaultExpenseGL"] = get_account("Default Expense")
    setup["fxGainLossAccount"] = get_account("FX Gain / Loss")
    setup["revaluationFrequency"] = get_account("Revaluation")
    setup["roundOffAccount"] = get_account("Round Off")
    setup["roundOffCostCenter"] = get_cost_center("Round Off")
    setup["depreciationAccount"] = get_account("Depreciation")
    setup["appreciationAccount"] = get_account("Appreciation")
    setup["defaultBankAccount"] = get_account("Default Bank Account")
    setup["defaultCashAccount"] = get_account("Default Cash Account")
    setup["defaultReceivableAccount"] = get_account("Debtors - ZI")
    setup["defaultPayableAccount"] = get_account("Creditors - ZI")
    setup["writeOffAccount"] = get_account("Write Off - ZI")
    setup["unrealizedProfitLossAccount"] = get_account("Unrealized Profit / Loss")
    setup["defaultIncomeAccount"] = get_account("Sales - ZI")
    setup["defaultDiscountAccount"] = get_account("Default Payment Discount Account")
    setup["paymentTerms"] = get_account("Default Payment Terms Template")
    setup["defaultCostCenter"] = get_cost_center("Main - ZI")
    setup["defaultFinanceBook"] = get_account("Default Finance Book")
    setup["exchangeGainLossAccount"] = get_account("Exchange Gain/Loss - ZI")
    setup["unrealizedExchangeGainLossAccount"] = get_account("Unrealized Exchange Gain/Loss")

    print(f"Accounting setup for company '{company_name}':")
    for key, value in setup.items():
        print(f"  {key}: {value}")

    return setup




def save_file(file_input, site_name="erpnext.localhost", folder_type="logos"):
    """
    Save a file to the local ERPNext folder.
    file_input can be:
      - base64 string starting with 'data:image/...'
      - full URL starting with http/https
      - actual file-like object (from Flask/Django request.files)
    Returns the relative path to the saved file.
    """
    try:
        base_path = os.path.join(
            os.getcwd(),
            site_name,
            "public",
            "files",
            "uploads",
            folder_type,
        )
        os.makedirs(base_path, exist_ok=True)

        # Case 1: Base64 image
        if isinstance(file_input, str) and file_input.startswith("data:image/"):
            header, encoded = file_input.split(",", 1)
            ext = header.split(";")[0].split("/")[1]
            filename = f"{uuid.uuid4().hex}.{ext}"
            save_path = os.path.join(base_path, filename)

            with open(save_path, "wb") as f:
                f.write(base64.b64decode(encoded))

            return f"/files/uploads/{folder_type}/{filename}"

        # Case 2: URL
        elif isinstance(file_input, str) and (file_input.startswith("http://") or file_input.startswith("https://")):
            headers = {
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://www.google.com/",
            }

            response = requests.get(file_input, headers=headers, stream=True)
            response.raise_for_status()

            ext = file_input.split("?")[0].split(".")[-1]
            if len(ext) > 4:
                ext = "png"

            filename = f"{uuid.uuid4().hex}.{ext}"
            save_path = os.path.join(base_path, filename)

            with open(save_path, "wb") as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)

            return f"/files/uploads/{folder_type}/{filename}"

        # Case 3: Actual file object (from request.files)
        elif hasattr(file_input, "read"):
            filename = f"{uuid.uuid4().hex}_{getattr(file_input, 'filename', 'file')}"
            save_path = os.path.join(base_path, filename)

            with open(save_path, "wb") as f:
                f.write(file_input.read())

            return f"/files/uploads/{folder_type}/{filename}"

        else:
            raise ValueError("Unsupported file input type")

    except Exception as e:
        print(f"Error saving file: {e}")
        return None
    
def get_next_custom_company_id():
    last = frappe.db.sql(
        """
        SELECT custom_company_id
        FROM `tabCompany`
        WHERE custom_company_id IS NOT NULL AND custom_company_id != ''
        ORDER BY CAST(REPLACE(custom_company_id, 'COMP-', '') AS UNSIGNED) DESC
        LIMIT 1
        """,
        as_dict=True
    )

    if last:
        last_num = int(last[0].custom_company_id.replace("COMP-", ""))
        next_num = last_num + 1
    else:
        next_num = 1

    return f"COMP-{next_num:05d}"
def ensure_account_and_cost_center(
    company_name,
    chart_of_accounts="Standard COA",
    default_expense_gl="Default Expense",
    fx_gain_loss_account="FX Gain / Loss",
    revaluation_frequency="Revaluation",
    round_off_account="Round Off",
    round_off_cost_center="Round Off",
    depreciation_account="Depreciation",
    appreciation_account="Appreciation"
):
    """
    Ensures all key accounts and cost centers exist for a company.
    Creates them if missing, sets defaults, and links parent accounts correctly.
    """
    messages = []

    def get_or_create_account(account_name, parent_account=None, account_type="Expense", root_type="Expense", is_group=0):
        """Fetch or create account safely"""
        if not account_name:
            return None

        existing = frappe.db.get_value("Account", {"company": company_name, "account_name": account_name}, "name")
        if existing:
            messages.append(f"Account '{account_name}' already exists.")
            return account_name

        # Ensure parent account exists for non-root accounts
        if not parent_account and account_type != "Equity":
            parent_account = frappe.db.get_value(
                "Account", {"company": company_name, "is_group": 1, "parent_account": None}, "account_name"
            )
            if not parent_account:
                # Create a root group if missing
                parent_account = f"Root - {company_name}"
                root_doc = frappe.get_doc({
                    "doctype": "Account",
                    "account_name": parent_account,
                    "company": company_name,
                    "account_type": "Equity",
                    "root_type": "Equity",
                    "is_group": 1
                })
                root_doc.insert(ignore_permissions=True)
                frappe.db.commit()
                messages.append(f"Root group '{parent_account}' created.")

        doc = frappe.get_doc({
            "doctype": "Account",
            "account_name": account_name,
            "company": company_name,
            "parent_account": parent_account,
            "account_type": account_type,
            "root_type": root_type,
            "is_group": is_group
        })
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
        messages.append(f"Account '{account_name}' created under '{parent_account}'.")
        return account_name

    def get_or_create_cost_center(cost_center_name, is_group=0):
        """Fetch or create cost center safely"""
        if not cost_center_name:
            return None

        existing = frappe.db.get_value("Cost Center", {"company": company_name, "cost_center_name": cost_center_name}, "name")
        if existing:
            messages.append(f"Cost Center '{cost_center_name}' already exists.")
            return cost_center_name

        doc = frappe.get_doc({
            "doctype": "Cost Center",
            "company": company_name,
            "cost_center_name": cost_center_name,
            "is_group": is_group
        })
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
        messages.append(f"Cost Center '{cost_center_name}' created.")
        return cost_center_name

    try:
        # --- Step 1: Ensure chart_of_accounts exists as group ---
        chart_of_accounts = get_or_create_account(chart_of_accounts, account_type="Equity", root_type="Equity", is_group=1)

        # --- Step 2: Create key child accounts ---
        default_expense_gl = get_or_create_account(default_expense_gl, parent_account=chart_of_accounts)
        fx_gain_loss_account = get_or_create_account(fx_gain_loss_account, parent_account=chart_of_accounts)
        revaluation_frequency = get_or_create_account(revaluation_frequency, parent_account=chart_of_accounts)
        round_off_account = get_or_create_account(round_off_account, parent_account=chart_of_accounts)
        depreciation_account = get_or_create_account(depreciation_account, parent_account=chart_of_accounts)
        appreciation_account = get_or_create_account(appreciation_account, parent_account=chart_of_accounts, account_type="Income", root_type="Income")


        round_off_cost_center = get_or_create_cost_center(round_off_cost_center)
        return {
            "status": "success",
            "status_code": 200,
            "message": "; ".join(messages)
        }

    except Exception as e:
        return {
            "status": "fail",
            "status_code": 500,
            "message": f"Error creating accounts or cost centers: {str(e)}"
        }



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

# @frappe.whitelist(allow_guest=False, methods=["POST"])
# def create_company_api():
#     try:
#         data = frappe.form_dict
#         company_name = data.get("companyName")
#         currency = data.get("currency")
#         country = data.get("country")
#         domain = data.get("domain")
#         tax_id = data.get("tpin")
#         phone_no = data.get("phone_no")
#         email = data.get("email")
#         custom_company_status = data.get("companyStatus")
#         custom_company_registration_number = data.get("companyRegistrationNumber")
#         custom_date_of_incoporation = data.get("custom_date_of_incoporation")
#         custom_company_type = data.get("companyType")
#         custom_company_industry_type = data.get("custom_company_industry_type")
#         custom_financial_year_begins = data.get("custom_financial_year_begins")
#         custom_alternate_number = data.get("custom_alternate_number")
#         custom_company_phone_number = data.get("custom_company_phone_number")
#         custom_address_line_1 = data.get("custom_address_line_1")
#         custom_address_line_2 = data.get("custom_address_line_2")
#         custom_district = data.get("custom_district")
#         custom_city = data.get("custom_city")
#         custom_province = data.get("custom_province")
#         custom_postal_code = data.get("custom_postal_code")
#         custom_time_zone = data.get("custom_time_zone")
#         custom_swift_code = data.get("custom_swift_code")
        
#         contactInfo = data.get("contactInfo")
        
        

#         if not company_name:
#             return send_response(status="fail", message="Company name is required", status_code=400, http_status=400)

#         if frappe.db.exists("Company", {"company_name": company_name}):
#             return send_response(status="fail", message="Company already exists", status_code=400, http_status=400)
        
#         if not tax_id:
#             return send_response(status="fail", message="Company TPIN is required", status_code=400, http_status=400)
        
#         if frappe.db.exists("Company", {"tax_id": tax_id}):
#             return send_response(status="fail", message="Company with this TPIN already exists", status_code=400, http_status=400)
        
#         if not email:
#             return send_response(status="fail", message="Email is required", status_code=400, http_status=400)
        
#         if not email.count("@") == 1 or not email.count(".") >= 1:
#             return send_response(status="fail", message="Invalid email format", status_code=400, http_status=400)
        
#         if frappe.db.exists("Company", {"email": email}):
#             return send_response(status="fail", message="Company with this email already exists", status_code=400, http_status=400)
        

#         next_id = get_next_custom_company_id()

#         company = frappe.get_doc({
#             "doctype": "Company",
#             "default_currency": currency,
#             "company_name": company_name,
#             "country": country,
#             "domain": domain,
#             "tax_id": tax_id,
#             "email": email,
#             "custom_company_status": custom_company_status,
#             "phone_no": phone_no,
#             "custom_company_id": next_id,
#             "custom_company_registration_number": custom_company_registration_number,
#             "custom_financial_year_begins": custom_financial_year_begins,
#             "custom_company_phone_number": custom_company_phone_number,
#             "custom_address_line_1": custom_address_line_1,
#             "custom_address_line_2": custom_address_line_2,
#             "custom_company_type": custom_company_type,
#             "custom_province": custom_province,
#             "custom_district": custom_district,
#             "custom_postal_code": custom_postal_code,
#             "custom_time_zone": custom_time_zone,
#             "custom_city": custom_city,
#             "custom_alternate_number": custom_alternate_number,
#             "custom_company_industry_type": custom_company_industry_type,
#             "custom_date_of_incoporation": custom_date_of_incoporation
#         })

#         company.insert(ignore_permissions=True)
#         frappe.db.commit()

#         return send_response(
#             status="success",
#             message="Company created successfully",
#             data={
#                 "custom_company_id": company.custom_company_id
#             },
#             status_code=201,
#             http_status=201
#         )

#     except Exception as e:
#         return send_response(
#             status="fail",
#             message=str(e),
#             status_code=500,
#             http_status=500
#         )

@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_companies_api():
    try:
        args = frappe.request.args
        page = args.get("page")
        page_size = args.get("page_size")

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


        all_companies = frappe.get_all(
            "Company", 
            fields=[
                "custom_company_id",
                "custom_company_registration_number",
                "custom_company_industry_type",
                "custom_company_status",
                "default_currency",
                "custom_province",
                "company_name",
                "custom_city",
                "phone_no",
                "country", 
                "tax_id",
                "email",                
            ],
            order_by="company_name asc"
        )

        total_companies = len(all_companies)
        if total_companies == 0:
            return send_response(
                status="success",
                message="No companies found.",
                data=[],
                status_code=200,
                http_status=200
            )

        start = (page - 1) * page_size
        end = start + page_size
        companies = all_companies[start:end]

        for company in companies:
            company["id"] = company.pop("custom_company_id")
            company["registrationNumber"] = company.pop("custom_company_registration_number")
            company["tpin"] = company.pop("tax_id")
            company["companyName"] = company.pop("company_name")
            company["companyStatus"] = company.pop("custom_company_status")
            company["industryType"] = company.pop("custom_company_industry_type")
            company["companyPhone"] = company.pop("phone_no")
            company["companyEmail"] = company.pop("email")
            company["city"] = company.pop("custom_city")
            company["province"] = company.pop("custom_province")
            company["country"] = company.pop("country")
            company["currency"] = company.pop("default_currency")

        total_pages = (total_companies + page_size - 1) // page_size

        response_data = {
            "success": True,
            "message": "Companies fetched successfully",
            "data": companies,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total_companies,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1
            }
        }

        return send_response_list(
            status="success",
            message="Companies fetched successfully",
            data=response_data,
            status_code=200,
            http_status=200
        )

    except Exception as e:
        frappe.log_error(message=str(e), title="Get Companies API Error")
        return send_response(
            status="fail",
            message="Failed to fetch companies",
            data={"error": str(e)},
            status_code=500,
            http_status=500
        )



@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_company_api():
    try:
        custom_company_id = frappe.form_dict.get("custom_company_id")
        if not custom_company_id:
            return send_response(
                status="fail",
                message="Company id is required (custom_company_id)",
                status_code=400,
                http_status=400
            )

        company_list = frappe.get_list(
            "Company",
            filters={"custom_company_id": custom_company_id},
            fields=["name"]
        )
        if not company_list:
            return send_response(
                status="fail",
                message="Company not found",
                status_code=404,
                http_status=404
            )

        company = frappe.get_doc("Company", company_list[0].name)
        def safe_attr(obj, attr):
            return getattr(obj, attr, "") or ""

        selling_terms = {}
        try:
            terms_doc = frappe.get_doc("Company Selling Terms", {"company": custom_company_id})

            payment_docs = frappe.get_all(
                "Company Selling Payments",
                filters={"company": custom_company_id},
                fields=["dueDates", "lateCharges", "tax", "notes"]
            )

            phases_docs = frappe.get_all(
                "Company Selling Payments Phases",
                filters={"company": custom_company_id},
                fields=["id", "phase_name", "percentage", "condition"]
            )

            phases_list = [
                {"id": p.get("id"), "phase": p.get("phase_name"), "percentage": p.get("percentage"), "condition": p.get("condition")}
                for p in phases_docs
            ]

            payment_info = {}
            if payment_docs:
                first = payment_docs[0]
                payment_info = {
                    "phases": phases_list,
                    "dueDates": first.get("dueDates"),
                    "lateCharges": first.get("lateCharges"),
                    "taxes": first.get("tax"),
                    "notes": first.get("notes")
                }

            selling_terms = {
                "general": safe_attr(terms_doc, "general"),
                "payment": payment_info,
                "delivery": safe_attr(terms_doc, "delivery"),
                "cancellation": safe_attr(terms_doc, "cancellation"),
                "warranty": safe_attr(terms_doc, "warranty"),
                "liability": safe_attr(terms_doc, "liability")
            }
        except frappe.DoesNotExistError:
            selling_terms = {}
            
        buying_terms = {}
        try:
            terms_doc = frappe.get_doc("Company Buying Terms", {"company": custom_company_id})

            payment_docs = frappe.get_all(
                "Company Buying Payments",
                filters={"company": custom_company_id},
                fields=["dueDates", "lateCharges", "taxes", "specialNotes"]
            )

            phases_docs = frappe.get_all(
                "Company Buying Payments Phases",
                filters={"company": custom_company_id},
                fields=["id", "phase_name", "percentage", "condition"]
            )

            phases_list = [
                {"id": p.get("id"), "phase": p.get("phase_name"), "percentage": p.get("percentage"), "condition": p.get("condition")}
                for p in phases_docs
            ]

            payment_info = {}
            if payment_docs:
                first = payment_docs[0]
                payment_info = {
                    "phases": phases_list,
                    "dueDates": first.get("dueDates"),
                    "lateCharges": first.get("lateCharges"),
                    "taxes": first.get("taxes"),
                    "notes": first.get("specialNotes")
                }

            buying_terms = {
                "general": safe_attr(terms_doc, "general"),
                "payment": payment_info,
                "delivery": safe_attr(terms_doc, "delivery"),
                "cancellation": safe_attr(terms_doc, "cancellation"),
                "warranty": safe_attr(terms_doc, "warranty"),
                "liability": safe_attr(terms_doc, "liability")
            }
        except frappe.DoesNotExistError:
            buying_terms = {}
        
        accounting_setup = get_accounting_setup(company.company_name)

        print(accounting_setup)

        data = {
            "registrationNumber": company.custom_company_registration_number,
            "tpin": company.tax_id,
            "companyName": company.company_name,
            "companyType": company.custom_company_type,
            "companyStatus": company.custom_company_status,
            "dateOfIncorporation": str(company.custom_date_of_incoporation),
            "industryType": company.custom_company_industry_type,

            "contactInfo": {
                "companyEmail": company.email,
                "companyPhone": company.phone_no,
                "alternatePhone": company.custom_alternate_number,
                "contactPerson": company.custom_contactperson,
                "contactEmail": company.custom_contactemail,
                "website": company.website,
                "contactPhone": company.custom_contactphone
            },

            "address": {
                "addressLine1": company.custom_address_line_1,
                "addressLine2": company.custom_address_line_2,
                "city": company.custom_city,
                "district": company.custom_district,
                "province": company.custom_province,
                "postalCode": company.custom_postal_code,
                "country": company.country,
                "timeZone": company.custom_time_zone
            },

            "bankAccounts": [
                {
                    "accountNo": company.custom_account_number,
                    "accountHolderName": company.custom_account_holder_name,
                    "bankName": company.custom_bank_name,
                    "swiftCode": company.custom_swift_code_,
                    "sortCode": company.custom_sort_code,
                    "branchAddress": company.custom_branch_address,
                    "currency": company.custom_currency,
                    "dateAdded": str(company.custom_date_of_addition),
                    "openingBalance": company.custom_opening_balance or 0.0
                }
            ],

            "financialConfig": {
                "baseCurrency": company.custom_currency,
                "financialYearStart": company.custom_financial_year_begins
            },
            
            "accountingSetup": {
                "chartOfAccounts": accounting_setup.get("chartOfAccounts", "Standard COA"),
                "defaultExpenseGL": accounting_setup.get("defaultExpenseGL", ""),
                "fxGainLossAccount": accounting_setup.get("fxGainLossAccount", ""),
                "revaluationFrequency": accounting_setup.get("revaluationFrequency", ""),
                "roundOffAccount": accounting_setup.get("roundOffAccount", ""),
                "roundOffCostCenter": accounting_setup.get("roundOffCostCenter", ""),
                "depreciationAccount": accounting_setup.get("depreciationAccount", ""),
                "appreciationAccount": accounting_setup.get("appreciationAccount", ""),
              
            },

            "terms": {
                "selling": selling_terms,
                "buying": buying_terms
            },

            "modules": {
                "accounting": company.custom_modules_accounting_,
                "crm": company.custom_module_crm,
                "hr": company.custom_module_hr,
                "inventory": company.custom_module_inventory,
                "procurement": company.custom_module_procurement,
                "sales": company.custom_module_sales,
                "supplierManagement": company.custom_module_suppliermanagement
            },

            "documents": {
                "companyLogoUrl": company.company_logo or "",
                "authorizedSignatureUrl": company.custom_signature
            },

            "templates": {
                "invoiceTemplate": company.custom_invoicetemplate,
                "quotationTemplate": company.custom_quotationtemplate,
                "rfqTemplate": company.custom_rfqtemplate
            }
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

    
    

    
# @frappe.whitelist(allow_guest=False, methods=["PUT"])
# def update_company_api():
#     try:
#         data = frappe.form_dict
#         name = data.get("name")

#         if not name:
#             return send_response(status="fail", message=_("Company name is required for update"), status_code=400)

#         company = frappe.get_doc("Company", name)

#         if data.get("company_name"):
#             company.company_name = data.get("company_name")
#         if data.get("country"):
#             company.country = data.get("country")
#         if data.get("domain"):
#             company.domain = data.get("domain")

#         company.save(ignore_permissions=True)
#         frappe.db.commit()

#         return send_response(status="success", message=_("Company updated successfully"), data=company.as_dict())

#     except frappe.DoesNotExistError:
#         return send_response(status="fail", message=_("Company not found"), status_code=404)
#     except Exception as e:
#         frappe.log_error(message=str(e), title="Update Company API Error")
#         return send_response(status="fail", message=str(e), status_code=500)
    
    
    
@frappe.whitelist(allow_guest=False, methods=["DELETE"])
def delete_company_api():
    try:
        custom_company_id = frappe.form_dict.get("id")

        if not custom_company_id:
            return send_response(
                status="fail", 
                message="Custom Company ID is required for delete", 
                status_code=400, 
                http_status=400
            )


        company = frappe.get_value("Company", {"custom_company_id": custom_company_id}, "name")

        if not company:
            return send_response(
                status="fail", 
                message="Company not found", 
                status_code=404, 
                http_status=404
            )

        frappe.db.sql("DELETE FROM `tabCompany Accounts` WHERE company_id=%s", custom_company_id)
        frappe.db.sql("DELETE FROM `tabCompany Selling Payments Phases` WHERE company=%s", company)
        frappe.db.sql("DELETE FROM `tabCompany Selling Payments` WHERE company=%s", company)
        frappe.db.sql("DELETE FROM `tabCompany Selling Terms` WHERE company=%s", company)

        frappe.db.sql("DELETE FROM `tabCompany Buying Payments Phases` WHERE company=%s", company)
        frappe.db.sql("DELETE FROM `tabCompany Buying Payments` WHERE company=%s", company)
        frappe.db.sql("DELETE FROM `tabCompany Buying Terms` WHERE company=%s", company)

        frappe.delete_doc("Company", company, ignore_permissions=True)
        frappe.db.commit()

        return send_response(
            status="success", 
            message="Company and related data deleted successfully",
            status_code=200,
            http_status=200
        )

    except Exception as e:
        frappe.log_error(message=str(e), title="Delete Company API Error")
        return send_response(
            status="fail", 
            message=str(e), 
            status_code=500,
            http_status=500
        )




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

def ensure_account(account_name, company, root_type="Expense"):
    """Ensure the Account exists, create if missing"""
    if not frappe.db.exists("Account", account_name):
        frappe.get_doc({
            "doctype": "Account",
            "account_name": account_name,
            "company": company,
            "root_type": root_type,
            "is_group": 0
        }).insert(ignore_permissions=True)
    return account_name

def ensure_cost_center(cost_center_name, company):
    """Ensure the Cost Center exists, create if missing"""
    if not frappe.db.exists("Cost Center", cost_center_name):
        frappe.get_doc({
            "doctype": "Cost Center",
            "cost_center_name": cost_center_name,
            "company": company,
            "is_group": 0
        }).insert(ignore_permissions=True)
    return cost_center_name

@frappe.whitelist(allow_guest=False, methods=["PUT"])
def update_company_terms_and_conditions():
    custom_company_id = (frappe.form_dict.get("custom_company_id") or "").strip()

    if not custom_company_id:
        return send_response(
            status="fail",
            message="custom_company_id is required",
            status_code=400,
            http_status=400
        )

    company = frappe.get_list("Company", filters={"custom_company_id": custom_company_id}, fields=["name"])
    if not company:
        return send_response(
            status="fail",
            message="Company not found",
            status_code=404,
            http_status=404
        )

    terms = frappe.form_dict.get("terms") or {}

    selling = terms.get("selling") or {}
    selling_payment = selling.get("payment") or {}
    selling_phases = selling_payment.get("phases", [])

    selling_terms_doc = frappe.get_doc("Company Selling Terms", frappe.db.exists("Company Selling Terms", {"company": custom_company_id})) \
                        if frappe.db.exists("Company Selling Terms", {"company": custom_company_id}) \
                        else frappe.new_doc("Company Selling Terms")
    selling_terms_doc.company = custom_company_id
    selling_terms_doc.general = (selling.get("general") or "").strip()
    selling_terms_doc.delivery = (selling.get("delivery") or "").strip()
    selling_terms_doc.cancellation = (selling.get("cancellation") or "").strip()
    selling_terms_doc.warranty = (selling.get("warranty") or "").strip()
    selling_terms_doc.liability = (selling.get("liability") or "").strip()
    selling_terms_doc.save(ignore_permissions=True)

    sell_payment_doc = frappe.get_doc("Company Selling Payments", frappe.db.exists("Company Selling Payments", {"company": custom_company_id})) \
                        if frappe.db.exists("Company Selling Payments", {"company": custom_company_id}) \
                        else frappe.new_doc("Company Selling Payments")
    sell_payment_doc.company = custom_company_id
    sell_payment_doc.type = selling_payment.get("type")
    sell_payment_doc.duedates = selling_payment.get("dueDates", "")
    sell_payment_doc.latecharges = selling_payment.get("lateCharges", "")
    sell_payment_doc.tax = selling_payment.get("taxes", "")
    sell_payment_doc.notes = selling_payment.get("specialNotes", "")
    sell_payment_doc.save(ignore_permissions=True)

    frappe.db.delete("Company Selling Payments Phases", {"company": custom_company_id})
    for p in selling_phases:
        phase_doc = frappe.new_doc("Company Selling Payments Phases")
        phase_doc.company = custom_company_id
        phase_doc.phase_name = p.get("phase")
        phase_doc.percentage = p.get("percentage")
        phase_doc.condition = p.get("when")
        phase_doc.insert(ignore_permissions=True)


    buying = terms.get("buying") or {}
    buying_payment = buying.get("payment") or {}
    buying_phases = buying_payment.get("phases", [])

    buying_terms_doc = frappe.get_doc("Company Buying Terms", frappe.db.exists("Company Buying Terms", {"company": custom_company_id})) \
                        if frappe.db.exists("Company Buying Terms", {"company": custom_company_id}) \
                        else frappe.new_doc("Company Buying Terms")
    buying_terms_doc.company = custom_company_id
    buying_terms_doc.general = (buying.get("general") or "").strip()
    buying_terms_doc.delivery = (buying.get("delivery") or "").strip()
    buying_terms_doc.cancellation = (buying.get("cancellation") or "").strip()
    buying_terms_doc.warranty = (buying.get("warranty") or "").strip()
    buying_terms_doc.liability = (buying.get("liability") or "").strip()
    buying_terms_doc.save(ignore_permissions=True)

    buy_payment_doc = frappe.get_doc("Company Buying Payments", frappe.db.exists("Company Buying Payments", {"company": custom_company_id})) \
                        if frappe.db.exists("Company Buying Payments", {"company": custom_company_id}) \
                        else frappe.new_doc("Company Buying Payments")
    
    buy_payment_doc.company = custom_company_id
    buy_payment_doc.type = buying_payment.get("type")
    buy_payment_doc.duedates = buying_payment.get("dueDates", "")
    buy_payment_doc.latecharges = buying_payment.get("lateCharges", "")
    buy_payment_doc.taxes = buying_payment.get("taxes", "")
    buy_payment_doc.specialnotes = buying_payment.get("specialNotes", "")
    buy_payment_doc.save(ignore_permissions=True)

    frappe.db.delete("Company Buying Payments Phases", {"company": custom_company_id})
    for p in buying_phases:
        phase_doc = frappe.new_doc("Company Buying Payments Phases")
        phase_doc.company = custom_company_id
        phase_doc.phase_name = p.get("phase")
        phase_doc.percentage = p.get("percentage")
        phase_doc.condition = p.get("when")
        phase_doc.insert(ignore_permissions=True)

    frappe.db.commit()

    return send_response(
        status="success",
        message="Company terms and conditions updated successfully",
        status_code=200
    )

@frappe.whitelist(allow_guest=True)
def create_company_api():
    data = frappe.form_dict
    print(data)
    registrationNumber = data.get("registrationNumber")
    tpin = data.get("tpin")
    companyName = data.get("companyName")
    companyType = data.get("companyType")
    companyStatus = data.get("companyStatus")
    dateOfIncorporation = data.get("dateOfIncorporation")
    industryType = data.get("industryType")
    
    def extract_nested(prefix):
        nested = {}
        for key, value in data.items():
            if key.startswith(prefix + "[") and key.endswith("]"):
                inner = key[len(prefix)+1:-1]  
                nested[inner] = value
        return nested
    
    def extract_phases(prefix):
        phases = []
        i = 0
        while True:
            key_base = f"{prefix}[{i}]"
            name = data.get(f"{key_base}[name]")
            if not name:
                break
            phases.append({
                "name": name,
                "percentage": data.get(f"{key_base}[percentage]"),
                "condition": data.get(f"{key_base}[condition]")
            })
            i += 1
        return phases

    
    def extract_nested_array(prefix):
        result = {}
        for key, value in data.items():
            if key.startswith(prefix + "[") and key.endswith("]"):
                inner = key[len(prefix)+1:-1] 
                parts = inner.replace("]", "").split("[")
                d = result
                for i, p in enumerate(parts[:-1]):
                    if p.isdigit():
                        p = int(p)
                        if not isinstance(d, list):
                            temp = []
                            d_keys = list(d.keys())
                            if d_keys:
                                raise ValueError(f"Unexpected dict keys {d_keys} when numeric index found")
                            d = temp
                            if i == 0:
                                result = d
                        while len(d) <= p:
                            d.append({})
                        d = d[p]
                    else:
                        if p not in d:
                            d[p] = {}
                        d = d[p]

                last_key = parts[-1]
                if last_key.isdigit():
                    last_key = int(last_key)
                    if not isinstance(d, list):
                        d_temp = []
                        d = d_temp
                    while len(d) <= last_key:
                        d.append(None)
                    d[last_key] = value
                else:
                    d[last_key] = value
        return result



    contactInfo = extract_nested("contactInfo")
    companyEmail = contactInfo.get("companyEmail")
    companyPhone = contactInfo.get("companyPhone")
    alternatePhone = contactInfo.get("alternatePhone")
    contactPerson = contactInfo.get("contactPerson")
    contactEmail = contactInfo.get("contactEmail")
    website = contactInfo.get("website")
    contactPhone = contactInfo.get("contactPhone")

    address = extract_nested("address")

    addressLine1 = address.get("addressLine1")
    addressLine2 = address.get("addressLine2")
    city = address.get("city")
    district = address.get("district")
    province = address.get("province")
    postalCode = address.get("postalCode")
    country = address.get("country")
    timeZone = address.get("timeZone")

    accounts_map = defaultdict(dict)

    for key, value in frappe.form_dict.items():
        if key.startswith("bankAccounts["):
            idx = key.split("[")[1].split("]")[0]
            field = key.split("[")[2].replace("]", "")
            accounts_map[idx][field] = value

    bank_accounts = []


    for bank in accounts_map.values():
        accountNo = bank.get("accountNo")
        accountHolderName = bank.get("accountHolderName")
        bankName = bank.get("bankName")
        swiftCode = bank.get("swiftCode")
        sortCode = bank.get("sortCode")
        branchAddress = bank.get("branchAddress")
        currency = bank.get("currency")
        dateAdded = bank.get("dateAdded")
        openingBalance = bank.get("openingBalance")
        bank_accounts.append({
            "accountNo": accountNo,
            "accountHolderName": accountHolderName,
            "bankName": bankName,
            "swiftCode": swiftCode,
            "sortCode": sortCode,
            "branchAddress": branchAddress,
            "currency": currency,
            "dateAdded": dateAdded,
            "openingBalance": openingBalance,
        })
    



    financial = extract_nested("financialConfig")

    baseCurrency = financial.get("baseCurrency")
    financialYearStart = financial.get("financialYearStart")

    acc = extract_nested("accountingSetup")

    chartOfAccounts = acc.get("chartOfAccounts")
    defaultExpenseGL = acc.get("defaultExpenseGL")
    fxGainLossAccount = acc.get("fxGainLossAccount")
    revaluationFrequency = acc.get("revaluationFrequency")
    roundOffAccount = acc.get("roundOffAccount")
    roundOffCostCenter = acc.get("roundOffCostCenter")
    depreciationAccount = acc.get("depreciationAccount")
    appreciationAccount = acc.get("appreciationAccount")

    modules = extract_nested("modules")

    accounting = modules.get("accounting")
    crm = modules.get("crm")
    hr = modules.get("hr")
    inventory = modules.get("inventory")
    procurement = modules.get("procurement")
    sales = modules.get("sales")
    supplierManagement = modules.get("supplierManagement")

    docs = data.get("documents", {})

    companyLogoFile = frappe.local.request.files.get("documents[companyLogoUrl]")
    authorizedSignatureFile = frappe.local.request.files.get("documents[authorizedSignatureUrl]")

    print("Company Logo file:", companyLogoFile)
    print("Authorized Signature file:", authorizedSignatureFile)

    if not companyLogoFile:
        return send_response(
            status="fail",
            message="companyLogoUrl is required",
            status_code=400,
            http_status=400
        )

    if not authorizedSignatureFile:
        return send_response(
            status="fail",
            message="authorizedSignatureUrl is required",
            status_code=400,
            http_status=400
        )


    if companyLogoFile:
        companyLogoFile = save_file(
            companyLogoFile,
            site_name="erpnext.localhost",
            folder_type="logos"
        )

    if authorizedSignatureFile:
        authorizedSignatureFile = save_file(
            authorizedSignatureFile,
            site_name="erpnext.localhost",
            folder_type="signatures"
        )

    print("Company Logo saved at:", companyLogoFile)
    print("Authorized Signature saved at:", authorizedSignatureFile)

    invoiceTemplateFile = frappe.local.request.files.get("templates[invoiceTemplate]")
    quotationTemplateFile = frappe.local.request.files.get("templates[quotationTemplate]")
    rfqTemplateFile = frappe.local.request.files.get("templates[rfqTemplate]")
    
    invoicePdfPath = save_file(invoiceTemplateFile, folder_type="pdfs") if invoiceTemplateFile else None
    quotationPdfPath = save_file(quotationTemplateFile, folder_type="pdfs") if quotationTemplateFile else None
    rfqPdfPath = save_file(rfqTemplateFile, folder_type="pdfs") if rfqTemplateFile else None
    if not invoiceTemplateFile:
        return send_response(status="fail", message="invoiceTemplate file is required", status_code=400, http_status=400)

    if not quotationTemplateFile:
        return send_response(status="fail", message="quotationTemplate file is required", status_code=400, http_status=400)

    if not rfqTemplateFile:
        return send_response(status="fail", message="rfqTemplate file is required", status_code=400, http_status=400)



    print("Invoice PDF saved at:", invoicePdfPath)
    print("Quotation PDF saved at:", quotationPdfPath)
    print("RFQ PDF saved at:", rfqPdfPath)
        
    
    if not companyName:
        return send_response(status="fail", message="Company name is required", status_code=400, http_status=400)

    if frappe.db.exists("Company", {"company_name": companyName}):
        return send_response(status="fail", message=f"Company name {companyName} already exists", status_code=400, http_status=400)
    
    if not tpin:
        return send_response(status="fail", message="Company TPIN is required", status_code=400, http_status=400)
    
    if frappe.db.exists("Company", {"tax_id": tpin}):
        return send_response(status="fail", message="Company with this TPIN already exists", status_code=400, http_status=400)
    
    if not companyEmail:
        return send_response(status="fail", message="Email is required", status_code=400, http_status=400)
    
    if not companyEmail.count("@") == 1 or not companyEmail.count(".") >= 1:
        return send_response(status="fail", message="Invalid email format", status_code=400, http_status=400)
    
    if not currency:
        return send_response(status="fail", message="Currency is required", status_code=400, http_status=400)

    
    if frappe.db.exists("Company", {"email": companyEmail}):
        return send_response(status="fail", message="Company with this email already exists", status_code=400, http_status=400)
    next_id = get_next_custom_company_id()

    company = frappe.get_doc({
            "doctype": "Company",
            "default_currency": currency,
            "company_name": companyName,
            "country": country,
            "website": website,
            "tax_id": tpin,
            "email": companyEmail,
            "custom_company_status": companyStatus,
            "phone_no": companyPhone,
            "custom_company_id": next_id,
            "custom_contactperson": contactPerson,
            "custom_contactemail": contactEmail,
            "custom_contactphone": contactPhone,
            "custom_company_registration_number": registrationNumber,
            "custom_financial_year_begins": financialYearStart,
            "custom_address_line_1":  addressLine1,
            "custom_address_line_2":  addressLine2,
            "custom_company_type": companyType,
            "custom_province": province,
            "custom_district": district,
            "custom_postal_code": postalCode,
            "custom_time_zone": timeZone,
            "custom_city": city,
            "custom_alternate_number": alternatePhone,
            "custom_company_industry_type": industryType,
            "custom_date_of_incoporation": dateOfIncorporation,
            "company_logo": companyLogoFile,
            "custom_signature": authorizedSignatureFile,
            "custom_invoicetemplate": invoicePdfPath,
            "custom_quotationtemplate": quotationPdfPath,
            "custom_rfqtemplate": rfqPdfPath,
            "custom_modules_accounting_": accounting,
            "custom_module_crm": crm,
            "custom_module_hr": hr,
            "custom_module_inventory": inventory,
            "custom_module_procurement": procurement,
            "custom_module_sales": sales,
            "custom_module_suppliermanagement": supplierManagement,
     
        })
    terms = extract_nested_array("terms")

    selling = terms.get("selling") or {}
    selling_payment = selling.get("payment") or {}
    selling_phases = extract_phases("terms[selling][payment][phases]")
    


    selling_terms_doc = frappe.get_doc("Company Selling Terms", frappe.db.exists("Company Selling Terms", {"company": next_id})) \
                        if frappe.db.exists("Company Selling Terms", {"company": next_id}) \
                        else frappe.new_doc("Company Selling Terms")
    selling_terms_doc.company = next_id
    selling_terms_doc.general = (selling.get("general") or "").strip()
    selling_terms_doc.delivery = (selling.get("delivery") or "").strip()
    selling_terms_doc.cancellation = (selling.get("cancellation") or "").strip()
    selling_terms_doc.warranty = (selling.get("warranty") or "").strip()
    selling_terms_doc.liability = (selling.get("liability") or "").strip()
    selling_terms_doc.save(ignore_permissions=True)

    sell_payment_doc = frappe.get_doc("Company Selling Payments", frappe.db.exists("Company Selling Payments", {"company": next_id})) \
                        if frappe.db.exists("Company Selling Payments", {"company": next_id}) \
                        else frappe.new_doc("Company Selling Payments")
    sell_payment_doc.company = next_id
    sell_payment_doc.type = selling_payment.get("type")
    sell_payment_doc.duedates = selling_payment.get("dueDates", "")
    sell_payment_doc.latecharges = selling_payment.get("lateCharges", "")
    sell_payment_doc.tax = selling_payment.get("taxes", "")
    sell_payment_doc.notes = selling_payment.get("notes", "")
    sell_payment_doc.save(ignore_permissions=True)

    frappe.db.delete("Company Selling Payments Phases", {"company": next_id})
    for p in selling_phases:
        phase_doc = frappe.new_doc("Company Selling Payments Phases")
        random_id = "{:06d}".format(random.randint(0, 999999)) 
        phase_doc.company = next_id
        phase_doc.id = random_id
        phase_doc.phase_name = p.get("name")
        phase_doc.percentage = p.get("percentage")
        phase_doc.condition = p.get("condition")
        phase_doc.insert(ignore_permissions=True)


    buying = terms.get("buying") or {}
    buying_payment = buying.get("payment") or {}
    buying_phases = extract_phases("terms[buying][payment][phases]")

    buying_terms_doc = frappe.get_doc("Company Buying Terms", frappe.db.exists("Company Buying Terms", {"company": next_id})) \
                        if frappe.db.exists("Company Buying Terms", {"company": next_id}) \
                        else frappe.new_doc("Company Buying Terms")
    buying_terms_doc.company = next_id
    buying_terms_doc.general = (buying.get("general") or "").strip()
    buying_terms_doc.delivery = (buying.get("delivery") or "").strip()
    buying_terms_doc.cancellation = (buying.get("cancellation") or "").strip()
    buying_terms_doc.warranty = (buying.get("warranty") or "").strip()
    buying_terms_doc.liability = (buying.get("liability") or "").strip()
    buying_terms_doc.save(ignore_permissions=True)

    buy_payment_doc = frappe.get_doc("Company Buying Payments", frappe.db.exists("Company Buying Payments", {"company": next_id})) \
                        if frappe.db.exists("Company Buying Payments", {"company": next_id}) \
                        else frappe.new_doc("Company Buying Payments")
    
    buy_payment_doc.company = next_id
    buy_payment_doc.type = buying_payment.get("type")
    buy_payment_doc.duedates = buying_payment.get("dueDates", "")
    buy_payment_doc.latecharges = buying_payment.get("lateCharges", "")
    buy_payment_doc.taxes = buying_payment.get("taxes", "")
    buy_payment_doc.specialnotes = buying_payment.get("notes", "")
    buy_payment_doc.save(ignore_permissions=True)

    frappe.db.delete("Company Buying Payments Phases", {"company": next_id})
    for p in buying_phases:
        random_id = "{:06d}".format(random.randint(0, 999999)) 
        phase_doc = frappe.new_doc("Company Buying Payments Phases")
        phase_doc.id = random_id
        phase_doc.company = next_id
        phase_doc.phase_name = p.get("name")
        phase_doc.percentage = p.get("percentage")
        phase_doc.condition = p.get("condition")
        phase_doc.insert(ignore_permissions=True)

    company.insert(ignore_permissions=True)
    frappe.db.commit()
    response = ensure_account_and_cost_center(
        round_off_account=roundOffAccount,
        round_off_cost_center=roundOffCostCenter,
        company_name=companyName,
        chart_of_accounts=chartOfAccounts,
        default_expense_gl=defaultExpenseGL,
        fx_gain_loss_account=fxGainLossAccount,
        revaluation_frequency=revaluationFrequency,
        depreciation_account=depreciationAccount,
        appreciation_account=appreciationAccount
    )
    for bank in bank_accounts:
        print("Bank data: ", bank)
        account_doc = frappe.get_doc({
            "doctype": "Company Accounts",
            "company_id": next_id,
            "id": "{:08d}".format(random.randint(0, 99999999)),
            "accountno": bank.get("accountNo"),
            "accountholdername": bank.get("accountHolderName"),
            "bankname": bank.get("bankName"),
            "swiftcode": bank.get("swiftCode"),
            "sortcode": bank.get("sortCode"),
            "branchaddress": bank.get("branchAddress"),
            "currency": bank.get("currency"),
            "dateadded": bank.get("dateAdded"),
            "openingbalance": bank.get("openingBalance"),
        })
        account_doc.insert(ignore_permissions=True)
        frappe.db.commit()


    return send_response(
        status="success",
        message=f"Company '{companyName}' created and accounts/cost centers ensured successfully",
        status_code=200
    )





@frappe.whitelist(allow_guest=True)
def update_company_api():
    data = frappe.form_dict
    print(data)

    def send_fail(msg, status_code=400, http_status=400):
        return send_response(
            status="fail", message=msg, status_code=status_code, http_status=http_status
        )

    custom_company_id = data.get("id")
    if not custom_company_id:
        return send_fail("Company id is required for update", 400, 400)

    try:
        company = frappe.get_doc("Company", {"custom_company_id": custom_company_id})
    except Exception:
        return send_fail(f"No company found with custom_company_id {custom_company_id}", 404, 404)

    def set_if_present(doc, field, value, transform=None):
        if value is None:
            return
        val = transform(value) if transform else value
        setattr(doc, field, val)
        
    def extract_nested(prefix):
        nested = {}
        for key, value in data.items():
            if key.startswith(prefix + "[") and key.endswith("]"):
                inner = key[len(prefix)+1:-1]  
                nested[inner] = value
        return nested
    
    def extract_phases(prefix):
        phases = []
        i = 0
        while True:
            key_base = f"{prefix}[{i}]"
            name = data.get(f"{key_base}[name]")
            if not name:
                break
            phases.append({
                "name": name,
                "percentage": data.get(f"{key_base}[percentage]"),
                "condition": data.get(f"{key_base}[condition]")
            })
            i += 1
        return phases

    
    def extract_nested_array(prefix):
        result = {}
        for key, value in data.items():
            if key.startswith(prefix + "[") and key.endswith("]"):
                inner = key[len(prefix)+1:-1] 
                parts = inner.replace("]", "").split("[")
                d = result
                for i, p in enumerate(parts[:-1]):
                    if p.isdigit():
                        p = int(p)
                        if not isinstance(d, list):
                            temp = []
                            d_keys = list(d.keys())
                            if d_keys:
                                raise ValueError(f"Unexpected dict keys {d_keys} when numeric index found")
                            d = temp
                            if i == 0:
                                result = d
                        while len(d) <= p:
                            d.append({})
                        d = d[p]
                    else:
                        if p not in d:
                            d[p] = {}
                        d = d[p]

                last_key = parts[-1]
                if last_key.isdigit():
                    last_key = int(last_key)
                    if not isinstance(d, list):
                        d_temp = []
                        d = d_temp
                    while len(d) <= last_key:
                        d.append(None)
                    d[last_key] = value
                else:
                    d[last_key] = value
        return result

    set_if_present(company, "company_name", data.get("companyName"))
    set_if_present(company, "tax_id", data.get("tpin"))
    set_if_present(company, "custom_company_registration_number", data.get("registrationNumber"))
    set_if_present(company, "custom_company_status", data.get("companyStatus"))
    set_if_present(company, "custom_company_industry_type", data.get("industryType"))
    set_if_present(company, "custom_date_of_incoporation", data.get("dateOfIncorporation"))
    set_if_present(company, "custom_company_type", data.get("companyType"))
    contactInfo = extract_nested("contactInfo")
    set_if_present(company, "email", contactInfo.get("companyEmail"))
    set_if_present(company, "phone_no", contactInfo.get("companyPhone"))
    set_if_present(company, "custom_alternate_number", contactInfo.get("alternatePhone"))
    set_if_present(company, "custom_contactperson", contactInfo.get("contactPerson"))
    set_if_present(company, "custom_contactemail", contactInfo.get("contactEmail"))
    set_if_present(company, "website", contactInfo.get("website"))
    set_if_present(company, "custom_contactphone", contactInfo.get("contactPhone"))

    address = extract_nested("address")
    set_if_present(company, "custom_address_line_1", address.get("addressLine1"))
    set_if_present(company, "custom_address_line_2", address.get("addressLine2"))
    set_if_present(company, "custom_city", address.get("city"))
    set_if_present(company, "custom_district", address.get("district"))
    set_if_present(company, "custom_province", address.get("province"))
    set_if_present(company, "custom_postal_code", address.get("postalCode"))
    set_if_present(company, "custom_time_zone", address.get("timeZone"))
    set_if_present(company, "country", address.get("country"))


    bank_accounts = []

    try:
        bank_accounts = extract_nested("bankAccounts") or []
    except Exception:
        bank_accounts = []

    company.set("Company Accounts", [])

    for bank in bank_accounts:
        company.append("Company Accounts", {
            "account_no": bank.get("accountNo"),
            "account_holder_name": bank.get("accountHolderName"),
            "bank_name": bank.get("bankName"),
            "swift_code": bank.get("swiftCode"),
            "sort_code": bank.get("sortCode"),
            "branch_address": bank.get("branchAddress"),
            "currency": bank.get("currency"),
            "date_added": bank.get("dateAdded"),
            "opening_balance": bank.get("openingBalance"),
        })


    financial = extract_nested("financialConfig")
    set_if_present(company, "custom_currency", financial.get("baseCurrency"))
    set_if_present(company, "custom_financial_year_begins", financial.get("financialYearStart"))

  
    modules = extract_nested("modules")
    if modules is not None:
        if "accounting" in modules:
            company.custom_modules_accounting_ = modules.get("accounting")
        if "crm" in modules:
            company.custom_module_crm = modules.get("crm")
        if "hr" in modules:
            company.custom_module_hr = modules.get("hr")
        if "inventory" in modules:
            company.custom_module_inventory = modules.get("inventory")
        if "procurement" in modules:
            company.custom_module_procurement = modules.get("procurement")
        if "sales" in modules:
            company.custom_module_sales = modules.get("sales")
        if "supplierManagement" in modules:
            company.custom_module_suppliermanagement = modules.get("supplierManagement")

        companyLogoFile = frappe.local.request.files.get("documents[companyLogoUrl]")
        authorizedSignatureFile = frappe.local.request.files.get("documents[authorizedSignatureUrl]")

        if companyLogoFile:
            file_doc = save_file(
                companyLogoFile,
                site_name="erpnext.localhost",
                folder_type="logos"
            )
            company.company_logo = file_doc

        if authorizedSignatureFile:
            file_doc = authorizedSignatureFile = save_file(
                authorizedSignatureFile,
                site_name="erpnext.localhost",
                folder_type="signatures"
            )
            company.custom_signature = file_doc

    invoiceTemplateFile = frappe.local.request.files.get("templates[invoiceTemplate]")
    quotationTemplateFile = frappe.local.request.files.get("templates[quotationTemplate]")
    rfqTemplateFile = frappe.local.request.files.get("templates[rfqTemplate]")
    if invoiceTemplateFile: 
        file = save_file(invoiceTemplateFile, folder_type="pdfs") if invoiceTemplateFile else None
        company.custom_invoicetemplate = file
    
    if quotationTemplateFile:
        quotationPdfPath = save_file(quotationTemplateFile, folder_type="pdfs") if quotationTemplateFile else None
        company.custom_quotationtemplate = quotationPdfPath
    
    if rfqTemplateFile:
        rfqPdfPath = save_file(rfqTemplateFile, folder_type="pdfs") if rfqTemplateFile else None
        company.custom_rfqtemplate = rfqPdfPath
        
    terms = extract_nested_array("terms")
    random_id = "{:06d}".format(random.randint(0, 999999)) 
    selling = terms.get("selling")
    if selling is not None:
        selling_payment = selling.get("payment") or {}
        selling_phases = extract_phases("terms[selling][payment][phases]")

     
        if frappe.db.exists("Company Selling Terms", {"company": custom_company_id}):
            selling_terms_doc = frappe.get_doc("Company Selling Terms", {"company": custom_company_id})
        else:
            selling_terms_doc = frappe.new_doc("Company Selling Terms")
            selling_terms_doc.company = custom_company_id

        if "general" in selling:
            selling_terms_doc.general = (selling.get("general") or "").strip()
        if "delivery" in selling:
            selling_terms_doc.delivery = (selling.get("delivery") or "").strip()
        if "cancellation" in selling:
            selling_terms_doc.cancellation = (selling.get("cancellation") or "").strip()
        if "warranty" in selling:
            selling_terms_doc.warranty = (selling.get("warranty") or "").strip()
        if "liability" in selling:
            selling_terms_doc.liability = (selling.get("liability") or "").strip()

        selling_terms_doc.save(ignore_permissions=True)

        if frappe.db.exists("Company Selling Payments", {"company": custom_company_id}):
            sell_payment_doc = frappe.get_doc("Company Selling Payments", {"company": custom_company_id})
        else:
            sell_payment_doc = frappe.new_doc("Company Selling Payments")
            sell_payment_doc.company = custom_company_id

        if "type" in selling_payment:
            sell_payment_doc.type = selling_payment.get("type")
        if "dueDates" in selling_payment:
            sell_payment_doc.duedates = selling_payment.get("dueDates") or ""
        if "lateCharges" in selling_payment:
            sell_payment_doc.latecharges = selling_payment.get("lateCharges") or ""
        if "taxes" in selling_payment:
            sell_payment_doc.tax = selling_payment.get("taxes") or ""
        if "notes" in selling_payment:
            sell_payment_doc.notes = selling_payment.get("notes") or ""

        sell_payment_doc.save(ignore_permissions=True)
        if selling_phases:
            updated_ids = set()
            for p in selling_phases:
                phase_id = p.get("id")
                is_delete = p.get("isDelete", 0)
       
                if phase_id and is_delete == 1:
                    if frappe.db.exists("Company Selling Payments Phases", {"id": phase_id}):
                        frappe.delete_doc("Company Selling Payments Phases", phase_id, ignore_permissions=True)
                    continue 
                
   
                if phase_id and frappe.db.exists("Company Selling Payments Phases", {"id": phase_id}):
                    phase_doc = frappe.get_doc("Company Selling Payments Phases", {"id": phase_id})
                    phase_doc.phase_name = p.get("name")
                    phase_doc.percentage = p.get("percentage")
                    phase_doc.condition = p.get("condition")
                    phase_doc.save(ignore_permissions=True)
                    updated_ids.add(phase_id)
                else:
                    phase_doc = frappe.new_doc("Company Selling Payments Phases")
                    phase_doc.id = "{:08d}".format(random.randint(0, 99999999)) 
                    phase_doc.company = custom_company_id
                    phase_doc.phase_name = p.get("name")
                    phase_doc.percentage = p.get("percentage")
                    phase_doc.condition = p.get("condition")
                    phase_doc.insert(ignore_permissions=True)
                    updated_ids.add(phase_doc.name)


    buying = terms.get("buying")
    if buying is not None:
        buying_payment = buying.get("payment") or {}
        buying_phases = extract_phases("terms[buying][payment][phases]")

    
        if frappe.db.exists("Company Buying Terms", {"company": custom_company_id}):
            buying_terms_doc = frappe.get_doc("Company Buying Terms", {"company": custom_company_id})
        else:
            buying_terms_doc = frappe.new_doc("Company Buying Terms")
            buying_terms_doc.company = custom_company_id

        if "general" in buying:
            buying_terms_doc.general = (buying.get("general") or "").strip()
        if "delivery" in buying:
            buying_terms_doc.delivery = (buying.get("delivery") or "").strip()
        if "cancellation" in buying:
            buying_terms_doc.cancellation = (buying.get("cancellation") or "").strip()
        if "warranty" in buying:
            buying_terms_doc.warranty = (buying.get("warranty") or "").strip()
        if "liability" in buying:
            buying_terms_doc.liability = (buying.get("liability") or "").strip()

        buying_terms_doc.save(ignore_permissions=True)

        if frappe.db.exists("Company Buying Payments", {"company": custom_company_id}):
            buy_payment_doc = frappe.get_doc("Company Buying Payments", {"company": custom_company_id})
        else:
            buy_payment_doc = frappe.new_doc("Company Buying Payments")
            buy_payment_doc.company = custom_company_id

        if "type" in buying_payment:
            buy_payment_doc.type = buying_payment.get("type")
        if "dueDates" in buying_payment:
            buy_payment_doc.duedates = buying_payment.get("dueDates") or ""
        if "lateCharges" in buying_payment:
            buy_payment_doc.latecharges = buying_payment.get("lateCharges") or ""
        if "taxes" in buying_payment:
            buy_payment_doc.taxes = buying_payment.get("taxes") or ""
        if "notes" in buying_payment:
            buy_payment_doc.specialnotes = buying_payment.get("notes") or ""

        buy_payment_doc.save(ignore_permissions=True)

        if buying_phases:
            updated_ids = set()
            for p in buying_phases:
                phase_id = p.get("id")
                is_delete = p.get("isDelete", 0)
                
                if phase_id and is_delete == 1:
                    if frappe.db.exists("Company Buying Payments Phases", {"id": phase_id}):
                        frappe.delete_doc("Company Buying Payments Phases", phase_id, ignore_permissions=True)
                    continue
                
                if phase_id and frappe.db.exists("Company Buying Payments Phases", {"id": phase_id}):
                    phase_doc = frappe.get_doc("Company Buying Payments Phases", {"id": phase_id})
                    phase_doc.phase_name = p.get("name")
                    phase_doc.percentage = p.get("percentage")
                    phase_doc.condition = p.get("condition")
                    phase_doc.save(ignore_permissions=True)
                    updated_ids.add(phase_id)
                else:
                    phase_doc = frappe.new_doc("Company Buying Payments Phases")
                    phase_doc.id = "{:08d}".format(random.randint(0, 99999999))
                    phase_doc.company = custom_company_id
                    phase_doc.phase_name = p.get("name")
                    phase_doc.percentage = p.get("percentage")
                    phase_doc.condition = p.get("condition")
                    phase_doc.insert(ignore_permissions=True)
                    updated_ids.add(phase_doc.name)


    company.save(ignore_permissions=True)
    frappe.db.commit()
    send_response(
        status="success",
        message="Company updated",
        status_code=200,
        http_status=200
    )

