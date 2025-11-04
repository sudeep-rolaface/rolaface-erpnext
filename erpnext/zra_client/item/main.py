from datetime import datetime
import random
import requests
import json
import frappe
from urllib.parse import quote
from frappe.model.naming import make_autoname
from erpnext.zra_client.main import ZRAClient
from frappe.utils import strip


class zraItem(ZRAClient):

    def get_tpin(self):
        return self.tpin

    def get_branch(self):
        return self.branch_code

    def create_item_helper(self, payload):
        self.create_item_zra(payload)

    def create_item(self, item_data):
        print("Incoming item_data:", json.dumps(item_data, indent=2))

        get_item_class_code = item_data.get("custom_item_class_code", "").strip()
        if not get_item_class_code:
            frappe.throw("Missing custom_item_class_code")

        print("Item class code:", get_item_class_code)

        excise_name = item_data.get("custom_excise_tax_category_code", "").strip()
        exciseTxCatCd = "ECM" if excise_name == "Excise on Coal" else "EXEEG"

        product_type = item_data.get("custom_product_type", "").strip()
        itemTyCd = {"Raw Material": "1", "Finished Product": "2"}.get(product_type, "3")

        try:
            encoded_class_code = quote(get_item_class_code)
            res = requests.get(f"http://0.0.0.0:7000/api/get-item-class-by-name/{encoded_class_code}/", timeout=5)
            res.raise_for_status()
            data = res.json()
            itemClsCd = data.get("itemClsCd")
            if not itemClsCd:
                frappe.throw(f"itemClsCd not found for '{get_item_class_code}'")
        except requests.RequestException as e:
            frappe.throw(f"Error fetching item class code: {e}")

        unit_name = item_data.get("custom_units_of_measure", "Pair").strip()
        try:
            res = requests.get(f"http://0.0.0.0:7000/unitofmeasure/{quote(unit_name)}/", timeout=5)
            res.raise_for_status()
            unit_data = res.json()
            qtyUnitCd = unit_data.get("code")
            if not qtyUnitCd:
                frappe.throw(f"Unit code not found for '{unit_name}'")
        except requests.RequestException as e:
            frappe.throw(f"Error fetching unit code for '{unit_name}': {e}")

        country_name = item_data.get("custom_origin_place_code", "").strip().upper()
        try:
            res = requests.get(f"http://0.0.0.0:7000/country/{quote(country_name)}/", timeout=5)
            res.raise_for_status()
            country_data = res.json()
            country_code = country_data.get("code")
            if not country_code:
                frappe.throw(f"Country code not found for '{country_name}'")
        except requests.RequestException as e:
            frappe.throw(f"Error fetching country code for '{country_name}': {e}")

        packaging_unit = item_data.get("custom_packaging_unit_code", "").strip()
        try:
            res = requests.get(f"http://0.0.0.0:7000/packaging-unit-code/{quote(packaging_unit)}/", timeout=5)
            res.raise_for_status()
            packaging_data = res.json()
            packaging_unit_code = packaging_data.get("code")
            if not packaging_unit_code:
                frappe.throw(f"Packaging unit code not found for '{packaging_unit}'")
        except requests.RequestException as e:
            frappe.throw(f"Error fetching packaging unit code for '{packaging_unit}': {e}")

        vat_map = {
            "StandardRated": "A", "MinimumTaxableValue": "B", "Exports": "C1",
            "ZeroRatingLocalPurchases": "C2", "ZeroRatedByNature": "C3",
            "Exempt": "D", "Disbursement": "E", "ReverseVAT": "RVAT"
        }
        vat = item_data.get("custom_vat", "").replace(" ", "").strip()
        vatCatCd = vat_map.get(vat, "A")

        ipl = item_data.get("custom_ipl_category_code", "").strip()
        if not ipl:
            frappe.throw("Insurance type is required")
        iplCatCd = "IPL1" if ipl == "Insurance Premium Levy" else "IPL2"

        for _ in range(5):
            rand_num = random.randint(1, 9999999)
            formatted = f"{rand_num:07d}"
            item_code = f"{country_code}{itemTyCd}{packaging_unit_code}{qtyUnitCd}{formatted}"
            if not frappe.db.exists("Item", {"item_code": item_code}):
                break
        else:
            frappe.throw("Failed to generate a unique item code after 5 attempts.")

        print("Generated item_code:", item_code)
        item_data["item_code"] = item_code

        created_by = item_data.get("owner", "System")
        default_price = float(item_data.get("custom_default_unit_price", 0))

        payload = {
            "tpin": self.get_tpin(),
            "bhfId": self.get_branch(),
            "itemCd": item_code,
            "itemClsCd": itemClsCd,
            "itemTyCd": itemTyCd,
            "itemNm": item_data.get("item_name") or "Unnamed",
            "orgnNatCd": country_code,
            "pkgUnitCd": packaging_unit_code,
            "qtyUnitCd": qtyUnitCd,
            "vatCatCd": vatCatCd,
            "iplCatCd": iplCatCd,
            "tlCatCd": None,
            "exciseTxCatCd": exciseTxCatCd,
            "btchNo": None,
            "bcd": None,
            "dftPrc": default_price,
            "manufacturerTpin": "null",
            "manufacturerItemCd": "null",
            "rrp": str(default_price),
            "svcChargeYn": "Y",
            "rentalYn": "N",
            "addInfo": None,
            "sftyQty": item_data.get("sftyQty", 0),
            "isrcAplcbYn": "N",
            "useYn": "Y",
            "regrNm": created_by,
            "regrId": created_by,
            "modrNm": created_by,
            "modrId": created_by
        }

        print("Payload being sent:", json.dumps(payload, indent=2))

        self.create_item_helper(payload)
        return item_data

    def override_item_name(self):
        """Optional override logic (if needed later)."""
        if hasattr(self, "item_data") and "item_code" in self.item_data:
            self.item_data["item_name"] = self.item_data["item_code"]

    def autoname(self):
        """Custom autoname method."""
        if frappe.db.get_default("item_naming_by") == "Naming Series":
            if self.variant_of:
                if not self.item_code:
                    template_item_name = frappe.db.get_value("Item", self.variant_of, "item_name")
                    make_variant_item_code(self.variant_of, template_item_name, self)
            else:
                from frappe.model.naming import set_name_by_naming_series
                set_name_by_naming_series(self)
                self.item_code = self.name

        self.item_code = strip(self.item_code)
        self.name = self.item_code
