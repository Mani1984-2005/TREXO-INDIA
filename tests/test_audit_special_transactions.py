"""Reproducibility and integrity tests for Special Transaction Audit V1.

Framework: Python standard library ``unittest`` only (pytest is NOT installed
in this environment, and no new dependency may be installed).

Run from the project root:

    .\\.venv\\Scripts\\python.exe -m unittest discover -s tests -v

Slow tests that need the full 541,909-row Excel file are opt-in:

    $env:TREXO_SLOW_TESTS = "1"; .\\.venv\\Scripts\\python.exe -m unittest discover -s tests -v

Test layers
-----------
1. Synthetic-frame unit tests: partition logic, classification coverage,
   UNKNOWN preservation, bucket precedence regression, register coverage,
   special-code reporting (including AMAZON not-found), determinism.
2. Generated-output integrity tests: the seven report artefacts exist and
   reconcile against the dataset size and their own invariants.
3. Protected-file tests: SHA-256 of the original Excel file and of the V1/V2
   processed datasets equals the baseline recorded when the audit completed.
4. Optional slow tests: full-dataset partition counts and historical figures.

Nothing in this module writes to any project file.
"""

from __future__ import annotations

import hashlib
import os
import sys
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from trexo import audit_special_transactions as audit  # noqa: E402

REPORT_DIR = ROOT / "reports"

# SHA-256 baselines recorded at the end of the successful audit run.
# If any of these files changes, a test in ProtectedFileTests fails.
PROTECTED_BASELINE = {
    ROOT / "data" / "raw" / "Online Retail.xlsx":
        "43465A06F2CCF7C8B5BD2892BC7DEFB52F97487934FE93B16AE4C3936424676D",
    ROOT / "data" / "processed" / "product_movement_v1.csv":
        "43EAF924A58D538E843C32B5CE5A975AA611D10BFDBC9CB064F1E899ACF7C3CD",
    ROOT / "data" / "processed" / "product_movement_v2.csv":
        "11B5378A63EBD6A62EDEC83D8EBA6BDE94C28BEE78F8D1CA526CE810215678DB",
    ROOT / "data" / "processed" / "product_monthly_sales_v2.csv":
        "C9B6ABD8E9CB5E967A755D9BC26BA40FBCB4D4136FFB09EE4C261E93EE5676CC",
}

DATASET_SIZE = 541909

OUTPUT_FILES = [
    REPORT_DIR / "invoice_prefix_analysis_v1.csv",
    REPORT_DIR / "special_stockcode_analysis_v1.csv",
    REPORT_DIR / "zero_price_description_analysis_v1.csv",
    REPORT_DIR / "unusual_invoice_details_v1.csv",
    REPORT_DIR / "transaction_classification_register_v1.csv",
    REPORT_DIR / "special_transaction_anomalies_v1.csv",
    REPORT_DIR / "special_transaction_audit_v1.md",
]


# ------------------------------------------------------------------
# SYNTHETIC FIXTURES
# ------------------------------------------------------------------

def _row(source_row, invoice_no, stock_code, description, quantity,
         unit_price, customer=12345.0):
    """One synthetic source row with the columns load_transactions produces.

    CustomerID mirrors the real dataset: float64 (or NaN when missing),
    never a string, because customer_as_text() expects a numeric value.
    """
    return {
        "InvoiceNo": invoice_no,
        "StockCode": stock_code,
        "Description": description,
        "Quantity": quantity,
        "InvoiceDate": pd.Timestamp("2011-06-15 10:00:00"),
        "UnitPrice": unit_price,
        "CustomerID": customer,
        "Country": "United Kingdom",
        "SourceRow": source_row,
    }


def synthetic_source() -> pd.DataFrame:
    """Raw synthetic frame covering all eight audit partitions and key codes."""
    rows = [
        # P07 ordinary paid merchandise
        _row(2, "536365", "85123A", "WHITE HANGING HEART T-LIGHT HOLDER", 6, 2.55),
        # P01 cancellation with negative quantity
        _row(3, "C536365", "85123A", "WHITE HANGING HEART T-LIGHT HOLDER", -6, 2.55),
        # P02 cancellation with non-negative quantity (empty partition in the
        # real dataset; must still be classified)
        _row(4, "C540000", "21231", "TOILET SET", 4, 7.95),
        # P03 negative quantity, non-cancel, zero price, damage note
        _row(5, "550001", "21231", "damages", -30, 0.0, customer=None),
        # P03 negative quantity, non-cancel, missing description
        _row(6, "550002", "20713", None, -10, 0.0, customer=None),
        # P04 zero quantity
        _row(7, "550003", "21231", "TOILET SET", 0, 7.95),
        # P05 positive quantity, zero price, ordinary description
        _row(8, "550004", "21231", "TOILET SET", 12, 0.0, customer=None),
        # P05 positive quantity, zero price, missing description
        _row(9, "550007", "20713", None, 5, 0.0, customer=None),
        # P06 positive quantity, negative price
        _row(10, "550005", "21231", "TOILET SET", 2, -3.0, customer=None),
        # P07 special codes
        _row(11, "536366", "POST", "POSTAGE", 1, 18.0),
        _row(12, "536367", "M", "Manual", 1, 100.0),
        _row(13, "C540002", "D", "Discount", -5, 2.0),
        _row(14, "536368", "BANK CHARGES", "Bank Charges", 1, 15.0),
        _row(15, "536369", "C2", "CARRIAGE", 1, 7.50),
        # P07 non-standard product format (register row-level entry)
        _row(16, "536370", "DCGS0001", "BOXED GLASS ASHTRAY", 1, 5.0),
        # P07 very large quantity (register row-level entry)
        _row(17, "536371", "21231", "TOILET SET", 1500, 2.0),
        # P08 missing numeric value
        _row(18, "550006", "21231", "TOILET SET", None, 7.95),
    ]
    return pd.DataFrame(rows)


def synthetic_flagged() -> pd.DataFrame:
    """Flagged synthetic frame used by most tests (partitions + derived cols)."""
    return audit.add_audit_flags(synthetic_source())


def synthetic_movement_v2() -> pd.DataFrame:
    """Minimal movement V2 lookalike for the special-code cross-reference."""
    return pd.DataFrame(
        {
            "StockCode": ["85123A", "POST", "M", "m"],
            "TotalQuantitySold": [100, 50, 20, 5],
            "TotalSalesValue": [255.0, 50.0, 60.0, 5.0],
        }
    )


# ------------------------------------------------------------------
# 1. PARTITION LOGIC
# ------------------------------------------------------------------

class PartitionTests(unittest.TestCase):
    """Audit partitions must be exhaustive and mutually exclusive."""

    @classmethod
    def setUpClass(cls):
        cls.df = synthetic_flagged()

    def test_partition_count_reconciles_with_source_rows(self):
        counts = self.df["AuditPartition"].value_counts()
        self.assertEqual(int(counts.sum()), len(self.df))
        self.assertTrue(set(counts.index) <= set(audit.PARTITION_ORDER))

    def test_partition_labels_match_independent_logic(self):
        expected = []
        for _, row in self.df.iterrows():
            qty, price = row["Quantity"], row["UnitPrice"]
            cancel = str(row["InvoiceNo"]).startswith("C")
            if pd.isna(qty) or pd.isna(price):
                label = "P08_UNCLASSIFIABLE_MISSING_VALUES"
            elif cancel and qty < 0:
                label = "P01_CANCELLATION_NEGATIVE"
            elif cancel and qty >= 0:
                label = "P02_CANCELLATION_NON_NEGATIVE"
            elif qty == 0:
                label = "P04_ZERO_QUANTITY"
            elif not cancel and qty > 0 and price == 0:
                label = "P05_POSITIVE_QUANTITY_ZERO_PRICE"
            elif not cancel and qty > 0 and price < 0:
                label = "P06_POSITIVE_QUANTITY_NEGATIVE_PRICE"
            elif not cancel and qty > 0 and price > 0:
                label = "P07_POSITIVE_QUANTITY_PAID"
            else:
                label = "P03_NEGATIVE_QUANTITY_NON_CANCEL"
            expected.append(label)
        self.assertEqual(list(self.df["AuditPartition"]), expected)

    def test_all_eight_partitions_are_declared(self):
        self.assertEqual(len(audit.PARTITION_ORDER), 8)

    def test_prefix_analysis_records_sum_to_dataset(self):
        analysis = audit.build_prefix_analysis(self.df)
        self.assertEqual(int(analysis["Records"].sum()), len(self.df))
        self.assertAlmostEqual(
            float(analysis["PercentOfDataset"].sum()), 100.0, places=3
        )


# ------------------------------------------------------------------
# 2. CLASSIFICATION COVERAGE AND EVIDENCE
# ------------------------------------------------------------------

class ClassificationTests(unittest.TestCase):
    """Every row must receive a rule, and UNKNOWN must survive."""

    @classmethod
    def setUpClass(cls):
        cls.raw = synthetic_flagged()
        cls.classified = audit.classify_transactions(cls.raw)

    def test_no_row_is_dropped(self):
        self.assertEqual(len(self.classified), len(self.raw))
        self.assertEqual(
            list(self.classified["SourceRow"]), list(self.raw["SourceRow"])
        )

    def test_every_row_matches_exactly_one_rule(self):
        self.assertFalse(self.classified["ClassificationRule"].isna().any())
        self.assertFalse(self.classified["ProposedCategory"].isna().any())
        self.assertFalse(self.classified["ConfidenceLevel"].isna().any())

    def test_unknown_classifications_are_preserved_not_forced(self):
        unknown = self.classified[
            self.classified["ProposedCategory"] == "UNKNOWN"
        ]
        # Missing-description rows in P03 and P05 stay UNKNOWN, and the
        # missing-numeric row (P08) stays UNKNOWN as well.
        self.assertEqual(set(unknown["SourceRow"]), {6, 9, 18})
        self.assertTrue((unknown["ConfidenceLevel"] == "UNKNOWN").all())
        # UNKNOWN rows are never quietly converted into a known category.
        self.assertNotIn("CUSTOMER_SALE", set(unknown["ProposedCategory"]))

    def test_special_codes_get_their_own_categories(self):
        by_row = self.classified.set_index("SourceRow")
        expectations = {
            11: "SHIPPING_CHARGE",     # POST
            15: "SHIPPING_CHARGE",     # C2
            12: "NEEDS_MANUAL_REVIEW", # M
            13: "FINANCIAL_ADJUSTMENT",# D on a cancellation invoice
            14: "SERVICE_CHARGE",      # BANK CHARGES
        }
        for source_row, category in expectations.items():
            self.assertEqual(
                by_row.loc[source_row, "ProposedCategory"], category,
                f"SourceRow {source_row} should be {category}",
            )
        self.assertEqual(
            by_row.loc[11, "ClassificationRule"], "POSTAGE_CODE"
        )

    def test_cancellation_rows_are_classified_as_cancellations(self):
        by_row = self.classified.set_index("SourceRow")
        self.assertEqual(by_row.loc[3, "ProposedCategory"], "CANCELLATION")
        self.assertEqual(by_row.loc[4, "ProposedCategory"], "CANCELLATION")
        # The cancellation rows keep HIGH confidence and no forced physical
        # movement claim.
        self.assertEqual(by_row.loc[3, "ConfidenceLevel"], "HIGH")

    def test_line_value_is_exact_quantity_times_price(self):
        priced = self.classified[self.classified["Quantity"].notna()]
        self.assertTrue(
            (
                priced["LineValue"]
                == priced["Quantity"] * priced["UnitPrice"]
            ).all()
        )

    def test_physical_impact_never_asserts_stock_increase(self):
        allowed = {
            "PHYSICAL_STOCK_DECREASE",
            "NO_PHYSICAL_STOCK_MOVEMENT",
            "UNKNOWN_PHYSICAL_IMPACT",
        }
        self.assertTrue(
            set(self.classified["PhysicalInventoryImpact"]) <= allowed
        )


# ------------------------------------------------------------------
# 3. BUCKET PRECEDENCE REGRESSION (the 469-row bug)
# ------------------------------------------------------------------

class BucketPrecedenceTests(unittest.TestCase):
    """A negative-quantity zero-price row must keep its negative evidence."""

    @classmethod
    def setUpClass(cls):
        cls.classified = audit.classify_transactions(synthetic_flagged())

    def test_negative_zero_price_row_keeps_negative_bucket(self):
        row = self.classified.set_index("SourceRow").loc[5]
        # Description 'damages' with negative quantity: the zero-price bucket
        # assignment must NOT overwrite this with an administrative bucket.
        self.assertEqual(row["DescriptionBucket"], "DAMAGE_OR_DEFECT")
        self.assertEqual(
            row["ClassificationRule"], "NEGATIVE_NON_CANCEL_WRITE_OFF"
        )

    def test_positive_zero_price_row_gets_zero_bucket(self):
        row = self.classified.set_index("SourceRow").loc[8]
        self.assertEqual(
            row["DescriptionBucket"], "ORDINARY_PRODUCT_DESCRIPTION"
        )

    def test_zero_price_buckets_only_fill_unclaimed_rows(self):
        buckets = audit.assign_description_buckets(synthetic_flagged())
        by_row = buckets.to_dict()
        self.assertNotEqual(
            by_row[5], "ORDINARY_PRODUCT_DESCRIPTION",
            "negative row was overwritten by the zero-price bucket",
        )


# ------------------------------------------------------------------
# 4. CLASSIFICATION REGISTER
# ------------------------------------------------------------------

class RegisterTests(unittest.TestCase):
    """The register must cover every source row exactly once."""

    @classmethod
    def setUpClass(cls):
        classified = audit.classify_transactions(synthetic_flagged())
        cls.register, cls.stats = audit.build_classification_register(
            classified, set()
        )

    def test_rowcount_sums_to_dataset_size(self):
        self.assertEqual(
            int(self.register["RowCount"].sum()), len(synthetic_source())
        )

    def test_row_level_entries_have_unique_traceable_source_rows(self):
        row_entries = self.register[self.register["ScopeLevel"] == "ROW"]
        self.assertTrue(row_entries["SourceRow"].notna().all())
        self.assertEqual(
            int(row_entries["SourceRow"].duplicated().sum()), 0
        )
        valid = set(synthetic_flagged()["SourceRow"])
        self.assertTrue(set(row_entries["SourceRow"]) <= valid)

    def test_group_entries_cover_exactly_the_remaining_rows(self):
        row_entries = self.register[self.register["ScopeLevel"] == "ROW"]
        group_entries = self.register[self.register["ScopeLevel"] == "GROUP"]
        self.assertGreater(len(group_entries), 0)
        covered_by_rows = int(row_entries["RowCount"].sum())
        covered_by_groups = int(group_entries["RowCount"].sum())
        self.assertEqual(covered_by_rows + covered_by_groups, len(synthetic_source()))

    def test_investigated_rows_are_never_in_a_group_entry(self):
        row_entries = self.register[self.register["ScopeLevel"] == "ROW"]
        # Every non-P07, non-standard, or large-quantity row must appear as an
        # explicit row-level entry with its own evidence.
        for source_row in (5, 6, 16, 17):
            self.assertIn(source_row, set(row_entries["SourceRow"]))


# ------------------------------------------------------------------
# 5. SPECIAL STOCKCODE INVESTIGATION
# ------------------------------------------------------------------

class SpecialStockCodeTests(unittest.TestCase):
    """Requested codes must be reported, missing codes must not be faked."""

    @classmethod
    def setUpClass(cls):
        cls.df = synthetic_flagged()
        cls.analysis = audit.build_special_stockcode_analysis(
            cls.df, synthetic_movement_v2()
        )
        cls.by_code = cls.analysis.set_index("StockCodeKey")

    def test_all_requested_codes_have_a_row(self):
        for code in audit.REQUESTED_SPECIAL_CODES:
            self.assertIn(code, self.by_code.index, f"missing row for {code}")

    def test_amazon_reported_as_not_found_not_substituted(self):
        amazon = self.by_code.loc["AMAZON"]
        self.assertEqual(amazon["FoundInDataset"], "NO")
        self.assertEqual(int(amazon["Records"]), 0)
        self.assertEqual(int(amazon["UniqueInvoices"]), 0)
        # The look-alike code must not be silently merged into AMAZON.
        self.assertIn("AMAZONFEE", self.by_code.index)
        self.assertEqual(self.by_code.loc["AMAZONFEE", "FoundInDataset"], "NO")

    def test_present_codes_report_real_measurements(self):
        post = self.by_code.loc["POST"]
        self.assertEqual(post["FoundInDataset"], "YES")
        self.assertEqual(int(post["Records"]), 1)
        self.assertEqual(float(post["TotalTransactionValue"]), 18.0)
        self.assertEqual(post["PresentInMovementV2"], "YES")

    def test_movement_lookup_handles_case_variants(self):
        # Movement V2 contains 'm' while transactions contain 'M'; the
        # uppercased lookup must aggregate instead of returning a frame.
        manual = self.by_code.loc["M"]
        self.assertEqual(manual["PresentInMovementV2"], "YES")
        self.assertEqual(float(manual["V2TotalQuantitySold"]), 25.0)
        self.assertEqual(float(manual["V2TotalSalesValue"]), 65.0)

    def test_code_absent_from_movement_v2_reported_as_absent(self):
        carriage = self.by_code.loc["C2"]
        self.assertEqual(carriage["FoundInDataset"], "YES")
        self.assertEqual(carriage["PresentInMovementV2"], "NO")


# ------------------------------------------------------------------
# 6. DETERMINISM (synthetic, in-process)
# ------------------------------------------------------------------

class DeterminismTests(unittest.TestCase):
    """Identical input must produce identical output within one run."""

    @classmethod
    def setUpClass(cls):
        cls.flagged = synthetic_flagged()

    def test_classification_is_reproducible(self):
        first = audit.classify_transactions(self.flagged)
        second = audit.classify_transactions(self.flagged)
        pd.testing.assert_frame_equal(first, second)

    def test_prefix_analysis_is_reproducible(self):
        first = audit.build_prefix_analysis(self.flagged)
        second = audit.build_prefix_analysis(self.flagged)
        pd.testing.assert_frame_equal(first, second)

    def test_register_is_reproducible(self):
        classified = audit.classify_transactions(self.flagged)
        first, _ = audit.build_classification_register(classified, set())
        second, _ = audit.build_classification_register(classified, set())
        pd.testing.assert_frame_equal(first, second)

    def test_special_analysis_is_reproducible(self):
        first = audit.build_special_stockcode_analysis(
            self.flagged, synthetic_movement_v2()
        )
        second = audit.build_special_stockcode_analysis(
            self.flagged, synthetic_movement_v2()
        )
        pd.testing.assert_frame_equal(first, second)


# ------------------------------------------------------------------
# 7. GENERATED OUTPUT INTEGRITY (real artefacts)
# ------------------------------------------------------------------

@unittest.skipUnless(
    all(path.exists() for path in OUTPUT_FILES),
    "generated report artefacts are absent; run the audit script first",
)
class GeneratedOutputTests(unittest.TestCase):
    """The artefacts on disk must reconcile with the dataset size."""

    @classmethod
    def setUpClass(cls):
        cls.register = pd.read_csv(
            REPORT_DIR / "transaction_classification_register_v1.csv"
        )
        cls.anomalies = pd.read_csv(
            REPORT_DIR / "special_transaction_anomalies_v1.csv"
        )
        cls.prefix = pd.read_csv(
            REPORT_DIR / "invoice_prefix_analysis_v1.csv"
        )

    def test_all_seven_outputs_exist_and_are_non_empty(self):
        for path in OUTPUT_FILES:
            self.assertGreater(path.stat().st_size, 0, path.name)

    def test_register_covers_every_source_row(self):
        self.assertEqual(int(self.register["RowCount"].sum()), DATASET_SIZE)

    def test_register_row_entries_are_traceable(self):
        row_entries = self.register[self.register["ScopeLevel"] == "ROW"]
        self.assertEqual(int(row_entries["SourceRow"].duplicated().sum()), 0)
        self.assertTrue(
            (row_entries["SourceRow"].min() >= 2)
            and (row_entries["SourceRow"].max() <= DATASET_SIZE + 1)
        )

    def test_unknown_rows_survive_in_the_register(self):
        unknown_rows = int(
            self.register.loc[
                self.register["ConfidenceLevel"] == "UNKNOWN", "RowCount"
            ].sum()
        )
        self.assertGreater(unknown_rows, 0)
        self.assertEqual(
            set(
                self.register.loc[
                    self.register["ConfidenceLevel"] == "UNKNOWN",
                    "ProposedCategory",
                ].unique()
            ),
            {"UNKNOWN"},
        )

    def test_every_anomaly_stays_open(self):
        self.assertTrue((self.anomalies["ResolutionStatus"] == "OPEN").all())
        self.assertEqual(
            int(self.anomalies["AnomalyID"].duplicated().sum()), 0
        )
        allowed = {"CRITICAL", "HIGH", "MEDIUM", "LOW", "INFORMATIONAL"}
        self.assertTrue(set(self.anomalies["Severity"]) <= allowed)

    def test_prefix_records_sum_to_dataset(self):
        self.assertEqual(int(self.prefix["Records"].sum()), DATASET_SIZE)

    def test_report_mentions_approval_gate(self):
        text = (
            REPORT_DIR / "special_transaction_audit_v1.md"
        ).read_text(encoding="utf-8")
        self.assertIn("awaiting review", text)
        self.assertNotIn("V3 dataset created", text)


# ------------------------------------------------------------------
# 8. PROTECTED FILES
# ------------------------------------------------------------------

class ProtectedFileTests(unittest.TestCase):
    """V1, V2 and the original Excel file must never change."""

    def test_protected_files_match_baseline_sha256(self):
        for path, baseline in PROTECTED_BASELINE.items():
            with self.subTest(file=str(path.relative_to(ROOT))):
                self.assertTrue(path.exists(), f"missing: {path}")
                digest = hashlib.sha256(path.read_bytes()).hexdigest().upper()
                self.assertEqual(digest, baseline, f"{path.name} changed")

    def test_v2_product_movement_row_count_matches_history(self):
        path = ROOT / "data" / "processed" / "product_movement_v2.csv"
        with path.open(encoding="utf-8") as handle:
            rows = sum(1 for _ in handle) - 1
        self.assertEqual(
            rows, audit.HISTORICAL_EXPECTED["Product movement V2"]
        )

    def test_v2_monthly_sales_row_count_matches_history(self):
        path = ROOT / "data" / "processed" / "product_monthly_sales_v2.csv"
        with path.open(encoding="utf-8") as handle:
            rows = sum(1 for _ in handle) - 1
        self.assertEqual(
            rows, audit.HISTORICAL_EXPECTED["Product-month records V2"]
        )


# ------------------------------------------------------------------
# 9. OPTIONAL FULL-DATASET TESTS (slow)
# ------------------------------------------------------------------

@unittest.skipUnless(
    os.environ.get("TREXO_SLOW_TESTS") == "1",
    "set TREXO_SLOW_TESTS=1 to run full-dataset checks",
)
class FullDatasetTests(unittest.TestCase):
    """Load the real Excel file and re-measure the historical figures."""

    @classmethod
    def setUpClass(cls):
        cls.df = audit.add_audit_flags(audit.load_transactions(audit.RAW_FILE))

    def test_dataset_size(self):
        self.assertEqual(len(self.df), DATASET_SIZE)

    def test_partition_counts_match_historical_figures(self):
        counts = self.df["AuditPartition"].value_counts()
        expected = {
            "P01_CANCELLATION_NEGATIVE":
                audit.HISTORICAL_EXPECTED["Cancellation-negative records"],
            "P03_NEGATIVE_QUANTITY_NON_CANCEL":
                audit.HISTORICAL_EXPECTED["Negative non-cancellation records"],
            "P05_POSITIVE_QUANTITY_ZERO_PRICE":
                audit.HISTORICAL_EXPECTED["Positive zero-price records"],
            "P06_POSITIVE_QUANTITY_NEGATIVE_PRICE":
                audit.HISTORICAL_EXPECTED["Other invalid/financial adjustment records"],
            "P07_POSITIVE_QUANTITY_PAID":
                audit.HISTORICAL_EXPECTED["V2 eligible sales"],
        }
        for partition, value in expected.items():
            self.assertEqual(int(counts.get(partition, 0)), value, partition)

    def test_v2_sale_definition_reproduces_eligible_rows(self):
        eligible = (
            ~self.df["IsCancellationInvoice"]
            & (self.df["Quantity"] > 0)
            & (self.df["UnitPrice"] > 0)
        )
        self.assertEqual(int(eligible.sum()), audit.HISTORICAL_EXPECTED["V2 eligible sales"])

    def test_classification_of_real_rows_never_raises_and_never_drops(self):
        classified = audit.classify_transactions(self.df)
        self.assertEqual(len(classified), DATASET_SIZE)
        self.assertFalse(classified["ProposedCategory"].isna().any())


if __name__ == "__main__":
    unittest.main(verbosity=2)
