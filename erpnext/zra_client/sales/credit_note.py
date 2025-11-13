import random
from erpnext.zra_client.generic_api import send_response
from erpnext.zra_client.main import ZRAClient
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
import requests
import uuid
import frappe
import json
import os

class CreditNoteSale(ZRAClient):
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
        name = base_data.get("name")
        originRcptNo = self.get_sales_rcptno_by_inv_no(name)

        if not originRcptNo:
            return send_response(
                status="fail",
                message=f"No receipt number found for Sales Invoice '{name}'",
                status_code=404,
                http_status=404
            )
            


        logged_in_user = "Admin"
        username = "Admin"

        payload = {
            "tpin": self.get_tpin(),
            "bhfId": self.get_branch_code(),
            "orgSdcId": self.get_origin_sdc_id(),
            "orgInvcNo": originRcptNo,
            "cisInvcNo":  str(uuid.uuid4()),
            "custTpin": base_data["cust_tpin"],
            "custNm": base_data["cust_name"],
            "salesTyCd": "N",
            "rcptTyCd": "R",
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
            "rfdRsnCd": "01",
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
        name = sell_data.get("name")
        customer_doc = frappe.get_doc("Customer", customer_name)
        customer_tpin = customer_doc.get("customer_tpin")
        destnCountryCd = sell_data.get("destnCountryCd")
        exchangeRt = sell_data.get("exchangeRt")
        is_stock_updated = 1
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
                "prc": 5000,
                "qty": qty
                
            })

            print(items)


        base_data = {
            "cust_name": customer_name,
            "cust_tpin": customer_tpin,
            "name": name,
            "currencyCd": "ZMW",
            "exchangeRt": "1",
            "created_by": created_by,
            "currencyCd": "ZMW",
            "lpoNumber": lpoNumber,
            "destnCountryCd": destnCountryCd

            
        }


        print("\n[START] Sending sale data...")
        self.reset_totals()
        payload = self.build_payload(items, base_data)
        response = self.create_normal_sale_helper(payload)
        response = response.json()
        apiCallerResponse = response
        print(response)
        print(f"Response from ZRA: {response}")
        
        if response.get("resultCd") == "000":
            rcpt_no = response.get("data", {}).get("rcptNo")
            print("Updating rctpNo")
            self.update_sales_rcptno_by_inv_no(name, rcpt_no, 1)

            company_info = []
            company_info.append((
                self.get_company_name(),
                self.get_company_phone_no(),
                self.get_company_email(),
                self.get_tpin(),
            ))

        
            customer_info = []
            customer_info.append((
                payload["custTpin"],
                payload["custNm"]
            ))

            get_qrcode_url = response.get("data", {}).get("qrCodeUrl") 
            invoice = []
            invoice.append((
                payload["cisInvcNo"],
                self.todays_date(),
                "TAX INVOICE",
                get_qrcode_url
                
            ))
            sdc_data = []
            sdc_data.append((
                self.todays_date(),
                self.get_origin_sdc_id(),
            ))

            pdf_items = payload["itemList"]
            print(customer_info, company_info, invoice, pdf_items)
            created_by = sell_data.get("owner")
            ocrnDt = datetime.now().strftime("%Y%m%d")
            print(self.to_use_data)
            if is_stock_updated == 1:
                print("Updating stock items...")

                update_stock_items = []
                update_stock_master_items = []                    
                    
                for item in self.to_use_data.get("itemList", []):
                    update_stock_items.append({
                        "itemSeq": item.get("itemSeq"),
                        "itemCd": item.get("itemCd"),
                        "itemClsCd": item.get("itemClsCd"),
                        "itemNm": item.get("itemNm"),
                        "pkgUnitCd": item.get("pkgUnitCd"),
                        "qtyUnitCd": item.get("qtyUnitCd"),
                        "qty": item.get("qty"),
                        "prc": item.get("prc"),
                        "splyAmt": item.get("splyAmt"),
                        "taxblAmt": item.get("vatTaxblAmt"), 
                        "vatCatCd": item.get("vatCatCd"),
                        "taxAmt": item.get("vatAmt"),
                        "totAmt": item.get("totAmt"),
                        "pkg": item.get("pkg", 1),
                        "totDcAmt": item.get("dcAmt", 0),
                    })

        
                    update_stock_master_items.append({
                        "itemCd": item.get("itemCd"),
                        "rsdQty": remaining_stock 
                    })


                update_stock_payload = {
                    "tpin": self.tpin,
                    "bhfId": self.branch_code,
                    "sarNo": 1,
                    "orgSarNo": 0,
                    "regTyCd": "M",
                    "sarTyCd": "11",
                    "ocrnDt": ocrnDt,
                    "totItemCnt": self.to_use_data['totItemCnt'],
                    "totTaxblAmt": self.to_use_data['totTaxblAmt'],
                    "totTaxAmt": self.to_use_data['totTaxAmt'],
                    "totAmt": self.to_use_data['totAmt'],
                    "regrId": self.to_use_data["regrId"],
                    "regrNm": self.to_use_data["regrId"],
                    "modrNm": self.to_use_data["regrId"],
                    "modrId": self.to_use_data["regrId"],
                    "itemList": update_stock_items
                }

                update_stock_master_payload = {
                    "tpin": self.tpin,
                    "bhfId": self.get_branch_code(),
                    "regrId": self.to_use_data["regrId"],
                    "regrNm": self.to_use_data["regrId"],
                    "modrNm": self.to_use_data["regrId"],
                    "modrId": self.to_use_data["regrId"],
                    "stockItemList": update_stock_master_items 
                    }

                print(update_stock_payload, update_stock_master_items)
                self.run_stock_update_in_background(update_stock_payload, update_stock_master_payload, created_by)

                response_status = response.get("resultCd")
                response_message = response.get("resultMsg")

                return {
                    "resultCd": response_status,
                    "resultMsg": response_message
                }

            else:
                send_response(
                    status="fail",
                    message=f"ZRA API Error: {response.get('resultMsg', 'Unknown error')}",
                    status_code=400,
                    http_status=400
                )
                return

        return response
