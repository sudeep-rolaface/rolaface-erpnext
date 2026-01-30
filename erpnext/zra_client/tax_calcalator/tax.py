from erpnext.zra_client.main import ZRAClient
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
import requests
import random
import uuid
import json
import os

ZRA_CLIENT_INSTANCE = ZRAClient()


class TaxCaller():
    def __init__(self):
        self.taxbl_totals = {key: 0.0 for key in self.TAX_RATES}
        self.tax_amt_totals = {key: 0.0 for key in self.TAX_RATES}
        super().__init__()
        
    def reset_totals(self):
        for key in self.TAX_RATES:
            self.taxbl_totals[key] = 0.0
            self.tax_amt_totals[key] = 0.0
        print("[INFO] Tax totals and amounts have been reset to zero.")


    def create_normal_sale_helper(self, payload):
        return self.create_sale_zra_client(payload)

    TAX_RATES = {
        "A": 16, "B": 16, "C1": 0, "C2": 0, "C3": 0,
        "D": 0, "E": 0, "F": 10,
        "Ipl1": 5, "Ipl2": 0,
        "Tl": 1.5,
        "ECM": 5,
        "EXEEG": 3,
        "RVAT": 16
    }


    @staticmethod
    def format_tax_amount(value):
        return float(Decimal(str(value)).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP))

    def generate_cis_invc_no(self):
        no = f"CIS{random.randint(1, 999):03d}-{random.randint(1000, 9999)}"
        print(f"[INFO] Generated invoice no: {no}")
        return no

    def calculate_tax_for_item(self, item):
        qty = float(item.get("qty", 0))
        price_tax_inclusive = float(item.get("prc", 0))
        discount_rate = 0.0

        vat_cat = item.get("VatCd")
        ipl_cat = item.get("IplCd")
        tl_cat = item.get("TlCd")
        excise_cat = item.get("ExciseCd")


        print(f"\n[CALCULATE TAX] {item['itemNm']} (qty={qty}, price={price_tax_inclusive}, "
              f"vatCatCd={vat_cat}, iplCatCd={ipl_cat}, tlCatCd={tl_cat}, exciseTxCatCd={excise_cat})")

        supply_amount = round(qty * price_tax_inclusive, 2)
        discount_amount = round(supply_amount * (discount_rate / 100), 2)

        vat_rate = self.TAX_RATES.get(vat_cat, 0) / 100 if vat_cat else 0
        ipl_rate = self.TAX_RATES["Ipl1"] / 100 if ipl_cat == "IPL1" else self.TAX_RATES["Ipl2"] / 100 if ipl_cat == "IPL2" else 0
        tl_rate = self.TAX_RATES["Tl"] / 100 if tl_cat == "TL" else 0
        ecm_rate = self.TAX_RATES["ECM"] / 100 if excise_cat == "ECM" else 0

        combined_rate_excl_ecm = vat_rate + ipl_rate + tl_rate
        base_amount = round(supply_amount / (1 + combined_rate_excl_ecm), 2) if combined_rate_excl_ecm > 0 else supply_amount

        vat_tax = round(base_amount * vat_rate, 2)
        ipl_tax = round(base_amount * ipl_rate, 2)
        tl_tax = round(base_amount * tl_rate, 2)

        ecm_taxable_amount = 0.0
        ecm_tax = 0.0

        ipl_taxable_amt = base_amount if ipl_rate > 0 else (supply_amount if ipl_cat == "IPL2" else 0.0)

        return {
            "splyAmt": supply_amount,
            "dcRt": discount_rate,
            "dcAmt": discount_amount,
            "vatTaxblAmt": base_amount if vat_cat else 0.0,
            "vatAmt": vat_tax,
            "iplTaxblAmt": ipl_taxable_amt,
            "iplAmt": ipl_tax,
            "tlTaxblAmt": base_amount if tl_rate > 0 else 0.0,
            "tlAmt": tl_tax,
            "ecmTaxblAmt": ecm_taxable_amount,
            "ecmAmt": ecm_tax,
            "totAmt": supply_amount
        }

    def build_payload(self, items, base_data):
        print("\n[BUILD PAYLOAD] Processing items...")
        processed_items = []

        for idx, item in enumerate(items):
            tax_result = self.calculate_tax_for_item(item)

            vat_cat = item.get("VatCd")
            ipl_cat = item.get("IplCd")
            tl_cat = item.get("TlCd")
            excise_cat = item.get("ExciseCd")

            if vat_cat in self.TAX_RATES:
                self.taxbl_totals[vat_cat] += tax_result["vatTaxblAmt"]
                self.tax_amt_totals[vat_cat] += tax_result["vatAmt"]

            if ipl_cat == "IPL1":
                self.taxbl_totals["Ipl1"] += tax_result["iplTaxblAmt"]
                self.tax_amt_totals["Ipl1"] += tax_result["iplAmt"]
            elif ipl_cat == "IPL2":
                self.taxbl_totals["Ipl2"] += tax_result["iplTaxblAmt"]

            if tl_cat == "TL":
                self.taxbl_totals["Tl"] += tax_result["tlTaxblAmt"]
                self.tax_amt_totals["Tl"] += tax_result["tlAmt"]

            if excise_cat == "ECM":
                ecm_taxbl_amt = 150.0
                ecm_tax_amt = round(ecm_taxbl_amt * (self.TAX_RATES["ECM"] / 100), 2)
                self.taxbl_totals["ECM"] += ecm_taxbl_amt
                self.tax_amt_totals["ECM"] += ecm_tax_amt
            else:
                ecm_taxbl_amt = 0.0
                ecm_tax_amt = 0.0

            processed_item = {
                "itemSeq": idx + 1,
                "itemCd": item["itemCd"],
                "itemClsCd": item["itemClsCd"],
                "itemNm": item["itemNm"],
                "qty": float(item.get("qty", 0)),
                "prc": float(item.get("prc", 0)),
                "rrp": round(float(item.get("prc", 0)), 2),
                **tax_result,
                "vatCatCd": vat_cat or "",
                "iplCatCd": ipl_cat or "",
                "tlCatCd": tl_cat or "",
                "pkgUnitCd": item.get("pkgUnitCd", "BA"),
                "pkg": float(item.get("pkg", 1.0)),
                "qtyUnitCd": item.get("qtyUnitCd", "BE"),
                "bcd": item.get("bcd", ""),
                "isrccCd": item.get("isrccCd", ""),
                "isrccNm": item.get("isrccNm", ""),
                "isrcRt": float(item.get("isrcRt", 0.0)),
                "isrcAmt": float(item.get("isrcAmt", 0.0)),
                "ecmTaxblAmt": ecm_taxbl_amt,
                "ecmAmt": ecm_tax_amt,
                "totAmt": round(tax_result["splyAmt"] + ecm_tax_amt, 2)
            }

            processed_items.append(processed_item)

        total_taxable_amount = round(sum(
            item.get("vatTaxblAmt", 0.0)
            + item.get("iplTaxblAmt", 0.0)
            + item.get("tlTaxblAmt", 0.0)
            + item.get("ecmTaxblAmt", 0.0)
            for item in processed_items
        ), 2)

        total_tax_amount = round(sum(
            item["vatAmt"] + item["iplAmt"] + item["tlAmt"] + item["ecmAmt"]
            for item in processed_items
        ), 2)
        total_amount = round(sum(item["totAmt"] for item in processed_items), 2)        
        lpoNumber = base_data.get("lpoNumber")
        get_principal_id = base_data.get("principalId")
        exchangeRt = base_data.get("exchangeRt")
        currencyCd = base_data.get("currencyCd")
        destnCountryCd = base_data.get("destnCountryCd")
        invoiceName = base_data.get("name")

        logged_in_user = "Admin"
        username = "Admin"

        next_invc_no = 1
        
        payload = {
            "tpin": ZRA_CLIENT_INSTANCE.get_tpin(),
            "bhfId": ZRA_CLIENT_INSTANCE.get_branch_code(),
            "orgInvcNo": 0,
            "cisInvcNo":  1,
            "custTpin": base_data["cust_tpin"],
            "custNm": base_data["cust_name"],
            "salesTyCd": "N",
            "rcptTyCd": "S",
            "pmtTyCd": "01",
            "salesSttsCd": "02",
            "cfmDt": datetime.now().strftime("%Y%m%d%H%M%S"),
            "salesDt": datetime.now().strftime("%Y%m%d"),
            "totItemCnt": len(items),
            **self.generate_tax_fields(),
            "totTaxblAmt": total_taxable_amount,
            "totTaxAmt": self.format_tax_amount(total_tax_amount),
            "cashDcRt": 0,
            "cashDcAmt": 0.0,
            "totAmt": total_amount,
            "prchrAcptcYn": "N",
            "remark": "",
            "regrId": username,
            "regrNm": username,
            "modrId": username,
            "modrNm": username,
            "saleCtyCd": "1",
            "dbtRsnCd": "",
            "invcAdjustReason": "",
            "itemList": processed_items
        }
        if destnCountryCd:
            payload["destnCountryCd"] = destnCountryCd

        if lpoNumber:
            payload["lpoNumber"] = lpoNumber

        if get_principal_id:
            payload["principalId"] = get_principal_id
            
        if exchangeRt:
            payload["exchangeRt"] = exchangeRt
            
        if currencyCd:
            payload["currencyTyCd"] = currencyCd
            
        if destnCountryCd:
            payload["destnCountryCd"] = destnCountryCd
            
        

        self.to_use_data = payload

        print(json.dumps(payload, indent=4))
        return payload

    def generate_tax_fields(self):
        def fix_key(k):
            if k.upper() == "RVAT":
                return "Rvat"
            return k.capitalize()

        taxblAmt = {f"taxblAmt{fix_key(k)}": round(self.taxbl_totals.get(k, 0.0), 2) for k in self.TAX_RATES}
        taxRt = {f"taxRt{fix_key(k)}": self.TAX_RATES.get(k, 0) for k in self.TAX_RATES}
        taxAmt = {f"taxAmt{fix_key(k)}": round(self.tax_amt_totals.get(k, 0.0), 2) for k in self.TAX_RATES}

        return {**taxblAmt, **taxRt, **taxAmt}

    def send_sale_data(self, sell_data):
        customer_name = sell_data.get("customerName")
        customerTpin = sell_data.get("customer_tpin")
        name = sell_data.get("name")
        destnCountryCd = sell_data.get("destnCountryCd")
        exchangeRt = sell_data.get("exchangeRt")
        item_type = sell_data.get("itemTypeCd")

        is_stock_updated = 1 if item_type == "Service" else 0
        created_by = sell_data.get("modified_by")
        currencyCd = sell_data.get("currencyCd")
        lpoNumber = sell_data.get("lpoNumber")
    
        sell_data_item = sell_data.get("items")
        items = []
        for item in sell_data_item:

            
            itemCd = item.get("itemCode")
            packageUnitCode = item.get("packageUnitCode")
            unitOfMeasure = item.get("unitOfMeasure")
            itemClassCd = item.get("itemClassCode")
            getIplCd = item.get("IplCd")
            getTlCd = item.get("TlCd")
            getExciseCd = item.get("ExciseCd")
            getVatCd = item.get("VatCd")
            itemName = item.get("itemName")
            qty = item.get("qty")
            actual_stock = item.get('actual_qty', 0)
            price = item.get("price")
            remaining_stock = 0
            items.append({
                "itemCd": itemCd,
                "packageUnitCode": packageUnitCode,
                "unitOfMeasure": unitOfMeasure,
                "itemClsCd": itemClassCd,
                "IplCd": getIplCd,
                "TlCd": getTlCd,
                "ExciseCd": getExciseCd,
                "VatCd": getVatCd,
                "itemNm": itemName,
                "prc": price,
                "qty": qty
                
            })

            print(items)


        base_data = {
            "cust_name": customer_name,
            "cust_tpin": customerTpin,
            "name": name,
            "currencyCd": "ZMW",
            "exchangeRt": exchangeRt,
            "created_by": created_by,
            "currencyCd": currencyCd,
            "lpoNumber": lpoNumber,
            "destnCountryCd": destnCountryCd

            
        }


        print("\n[START] Sending sale data...")
        self.reset_totals()
        payload = self.build_payload(items, base_data)
        
        return payload
       