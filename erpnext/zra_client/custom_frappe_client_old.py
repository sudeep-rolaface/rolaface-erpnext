from datetime import datetime
import random
import re
from erpnext.zra_client.generic_api import send_response
import frappe

class CustomFrappeClient():
    
    def GetOrCreateIncoterm(self, incoterm_code):
        if not incoterm_code:
            return None
        if frappe.db.exists("Incoterm", incoterm_code):
            return incoterm_code
        try:
            new_incoterm = frappe.get_doc({
                "doctype": "Incoterm",
                "code": incoterm_code,
                "title": incoterm_code 
            })
            new_incoterm.insert(ignore_permissions=True)
            frappe.db.commit()
            return new_incoterm.name
        except Exception as e:
            frappe.log_error(f"Failed to create Incoterm {incoterm_code}: {str(e)}")
            return None
        
    def GetOrCreateProject(self, project_name):
        if not project_name:
            return None

        existing = frappe.db.get_value("Project", {"project_name": project_name}, "name")
        if existing:
            return existing

        doc = frappe.get_doc({
            "doctype": "Project",
            "project_name": project_name,
            "company": self.getCurrentCompany()
        })
        try:
            doc.insert(ignore_permissions=True)
            frappe.db.commit()
        except frappe.DuplicateEntryError:
            existing = frappe.db.get_value("Project", {"project_name": project_name}, "name")
            return existing
        except frappe.UniqueValidationError:
            existing = frappe.db.get_value("Project", {"project_name": project_name}, "name")
            return existing

        return doc.name
        
    def GetItemDetails(self, item_code):
        if not item_code:
            return send_response(
                status="fail",
                message="Item code is required.",
                status_code=400,
                http_status=400
            )
        
        try:
            item = frappe.get_doc("Item", item_code)
            print(item)
            return item
        except frappe.DoesNotExistError:
            return send_response(
                status="fail",
                message=f"Item {item_code} not found",
                status_code=404,
                http_status=404
            )
        except Exception as e:
            return send_response(
                status="fail",
                message=f"Cannot proceed: {str(e)}",
                status_code=400,
                http_status=400
            )
            
    def GetDefaultWareHouse(self):
        WARE_HOUSE = "Finished Goods - Izyane"
        return WARE_HOUSE
    
    
    def getDefaultExpenseAccount(self):
        ACCOUNT = "Stock Difference - Izyane - I"
        return ACCOUNT
    

    def getStockReceivedButNotBilledAccount(self):
        company = self.getCurrentCompany()
        return frappe.get_cached_value(
            "Company",
            company,
            "stock_received_but_not_billed"
        )

    
    
    def createInvoiceTermsAndPayments(self, new_invoice_name, terms):
        
        terms_data = terms
        selling = terms.get("selling") or {}
        general = (selling.get("general") or "").strip()
        delivery = (selling.get("delivery") or "").strip()
        cancellation = (selling.get("cancellation") or "").strip()
        warranty = (selling.get("warranty") or "").strip()
        liability = (selling.get("liability") or "").strip()
        payment_terms_data = selling.get("payment") or {}
        print("Payments : ", payment_terms_data)
        dueDates = payment_terms_data.get("dueDates", "")
        lateCharges = payment_terms_data.get("lateCharges", "")
        tax = payment_terms_data.get("taxes", "")
        notes = payment_terms_data.get("notes", "")
        phases = payment_terms_data.get("phases", [])
        
        
        print("dueDate: ", dueDates, "lateCharges :", lateCharges, "tax: ", tax)

        terms_doc = frappe.get_doc({
            "doctype": "Sale Invoice Selling Terms",
            "invoiceno": new_invoice_name,
            "general": general,
            "delivery": delivery,
            "cancellation": cancellation,
            "warranty": warranty,
            "liability": liability
        })
        terms_doc.insert(ignore_permissions=True)

        if payment_terms_data:
            payment_doc = frappe.get_doc({
                "doctype": "Sale Invoice Selling Payment",
                "invoiceno": new_invoice_name,
                "duedates": dueDates,
                "latecharges": lateCharges,
                "taxes": tax,
                "notes": notes
            })
            payment_doc.insert(ignore_permissions=True)

        for phase in phases:
            random_id = "{:06d}".format(random.randint(0, 999999))

            phase_doc = frappe.get_doc({
                "doctype": "Sale Invoice Selling Payment Phases",
                "id": random_id,
                "invoiceno": new_invoice_name,
                "phase_name": phase.get("name", ""),
                "percentage": phase.get("percentage", 0),
                "condition": phase.get("condition", "")
            })
            phase_doc.insert(ignore_permissions=True)

        frappe.db.commit()

        return True
    
    def GetExpensesValuationAccount(self):
        VALID_ACCOUNTS_HEAD = [
            "Expenses Included In Valuation - I",
            "Freight and Forwarding Charges - I",
            "Marketing Expenses - I",
            "Miscellaneous Expenses - I"
        ]

        return VALID_ACCOUNTS_HEAD

    def getCurrentCompany(self):
        COMPANY = "Izyane"
        return COMPANY

    def GetTaxesChargesRate(self):
        RATES = ["Actual", "On Net Total", "On Previous Row Amount", "On Previous Row Total", "On Item Quantity"]
        
        return RATES
    
    def GetTaxAccountHeads(self):
        ACCOUNTS = []
        return ACCOUNTS

    
    

    def CreateSupplierAddress(self, addresses, supplier):
        """
        Create the Supplier (Billing) Address, link it to the Supplier, and insert it.
        Returns the Address name.
        """
        supplierAddress = addresses.get("supplierAddress", {})
        print("Supplier Address Data:", supplierAddress)

        if not supplierAddress:
            print("No Supplier Address provided.")
            return None

        try:
            doc = frappe.get_doc({
                "doctype": "Address",
                "address_title": supplierAddress.get("addressTitle", "").strip(),
                "address_type": supplierAddress.get("addressType", "Billing"),
                "address_line1": supplierAddress.get("addressLine1"),
                "address_line2": supplierAddress.get("addressLine2"),
                "city": supplierAddress.get("city"),
                "county": supplierAddress.get("county"),
                "state": supplierAddress.get("state"),
                "country": supplierAddress.get("country") or "Zambia",
                "pincode": supplierAddress.get("postalCode"),
                "phone": supplierAddress.get("phone"),
                "email_id": supplierAddress.get("email"),
            })

            # Link to Supplier
            doc.append("links", {
                "link_doctype": "Supplier",
                "link_name": supplier
            })

            doc.insert(ignore_permissions=True)
            print(f"Created Supplier Address: {doc.name}")
            return doc.name

        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "Create Supplier Address Error")
            print(f"Error creating Supplier Address: {str(e)}")
            return None


    def CreateDispatchAddress(self, addresses, supplier):
        """
        Create the Dispatch Address, link it to the Supplier, and insert it.
        Returns the Address name.
        """
        dispatchAddress = addresses.get("dispatchAddress", {})
        print("Dispatch Address Data:", dispatchAddress)

        if not dispatchAddress:
            print("No Dispatch Address provided.")
            return None

        try:
            doc = frappe.get_doc({
                "doctype": "Address",
                "address_title": dispatchAddress.get("addressTitle", "").strip(),
                "address_type": dispatchAddress.get("addressType", "Office"),
                "address_line1": dispatchAddress.get("addressLine1"),
                "address_line2": dispatchAddress.get("addressLine2"),
                "city": dispatchAddress.get("city"),
                "county": dispatchAddress.get("county"),
                "state": dispatchAddress.get("state"),
                "country": dispatchAddress.get("country") or "Zambia",
                "pincode": dispatchAddress.get("postalCode"),
                "phone": dispatchAddress.get("phone"),
                "email_id": dispatchAddress.get("email"),
            })

            # Link to Supplier
            doc.append("links", {
                "link_doctype": "Supplier",
                "link_name": supplier
            })

            doc.insert(ignore_permissions=True)
            print(f"Created Dispatch Address: {doc.name}")
            return doc.name

        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "Create Dispatch Address Error")
            print(f"Error creating Dispatch Address: {str(e)}")
            return None


    def CreateShippingAddress(self, addresses, supplier):
        shippingAddress = addresses.get("shippingAddress", {})
        print("Shipping Address Data:", shippingAddress)

        if not shippingAddress:
            print("No Shipping Address provided.")
            return None

        try:
            doc = frappe.get_doc({
                "doctype": "Address",
                "address_title": shippingAddress.get("addressTitle", "").strip(),
                "address_type": shippingAddress.get("addressType", "Shipping"),
                "address_line1": shippingAddress.get("addressLine1"),
                "address_line2": shippingAddress.get("addressLine2"),
                "city": shippingAddress.get("city"),
                "county": shippingAddress.get("county"),
                "state": shippingAddress.get("state"),
                "country": shippingAddress.get("country") or "Zambia",
                "pincode": shippingAddress.get("postalCode"),
                "phone": shippingAddress.get("phone"),
                "email_id": shippingAddress.get("email"),
            })

            doc.append("links", {
                "link_doctype": "Supplier",
                "link_name": supplier
            })

            doc.insert(ignore_permissions=True)
            print(f"Created Shipping Address: {doc.name}")
            return doc.name

        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "Create Shipping Address Error")
            print(f"Error creating Shipping Address: {str(e)}")
            return None
    
    
    def GetAvailableTaxCategory(self):
        tax_categories = frappe.get_all("Tax Category", fields=["name"])
        tax_names = [tax["name"] for tax in tax_categories]
        
        return tax_names

    def GetValidTaxTypes(self):
        LIST = ["A", "B", "C1", "C2", "C3", "D", "E", "RVAT"]
        return LIST
    
    def GetAllCompanyCostCenter(self):
        company = self.getCurrentCompany()
    
        cost_centers = frappe.get_all(
            "Cost Center",
            filters={"company": company, "disabled": 0, "is_group": 0},
            fields=["name"]
        )
    
        cost_center_names = [cc["name"] for cc in cost_centers]
        
        print("Cost Centers: ", cost_center_names)
        return cost_center_names
    

    def GetItemInfo(self, item_code):
        if not item_code:
            return send_response(
                status="fail",
                message="Item code is required.",
                status_code=400,
                http_status=400
            )
        
        try:
            item = frappe.get_doc("Item", item_code)
        except frappe.DoesNotExistError:
            return send_response(
                status="fail",
                message="Item not found",
                status_code=404,
                http_status=404
            )
        except Exception as e:
            return send_response(
                status="fail",
                message=f"Cannot proceed: {str(e)}",
                status_code=400,
                http_status=400
            )
        
        itemName = item.item_name
        itemClassCd = getattr(item, "custom_itemclscd", None)
        itemPackingUnitCd = getattr(item, "custom_pkgunitcd", None)
        itemUnitCd = getattr(item, "stock_uom", None)
        itemVatCd = getattr(item, "custom_vatcd", None)
        itemIplCd = getattr(item, "custom_iplcd", None)
        itemTlCd = getattr(item, "custom_tlcd", None)

        return {
            "itemName": itemName,
            "itemClassCd": itemClassCd,
            "itemPackingUnitCd": itemPackingUnitCd,
            "itemUnitCd": itemUnitCd,
            "itemVatCd": itemVatCd,
            "itemIplCd": itemIplCd,
            "itemTlCd": itemTlCd
        }
    
    def GetLogedInUser(self):
        username = "Timothy"
        return username
    
    def GetPaymentMethodsCodes(self):
        PAYMENT_METHOD_LIST_CODE = ["01", "02", "03", "04", "05", "06", "07", "08"]
        return PAYMENT_METHOD_LIST_CODE

    def GetPaymentMethodsName(self):
        PAYMENT_METHOD_LIST_NAME = [
            "CASH",
            "CREDIT",
            "CASH/CREDIT",
            "BANK CHECK",
            "DEBIT & CREDIT CARD",
            "MOBILE MONEY",
            "Bank transfer",
            "OTHER"
        ]
        return PAYMENT_METHOD_LIST_NAME
    
    def GetTransactionProgressCodes(self):
        TRANSACTION_PROGRESS_CODES = ["02", "05", "06", "04"]
        return TRANSACTION_PROGRESS_CODES

    def GetTransactionProgressNames(self):
        TRANSACTION_PROGRESS_NAMES = [
            "APPROVED",
            "REFUNDED",
            "TRANSFERRED",
            "REJECTED"
        ]
        return TRANSACTION_PROGRESS_NAMES
    
    def getNextCisInvoiceNo(self):
        last_purchase = frappe.get_all(
        "Purchase Invoice",
        fields=["name"],
        order_by="creation desc",
        limit=1
    )

        current_year = datetime.now().year

        if last_purchase:
            last_name = last_purchase[0]["name"] 

            match = re.search(r'(\d+)$', last_name)
            last_no = int(match.group(1)) if match else 0
        else:
            last_no = 0
        next_no = last_no + 1

        next_no_str = f"{next_no:05d}"
        next_invoice_name = f"ACC-PINV-{current_year}-{next_no_str}"

        return next_invoice_name
    
    def PurchaseInvoiceStatuses(self):
        LIST = [
            "Return",
            "Submitted",
            "Paid",
            "Party Paid",
            "Cancelled",
            "Internal Transfer",
            "Debit Note Issued"
        ]
        
        return LIST
    
    def GetNextCustomSupplierId(self):
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
    





        
        
        
