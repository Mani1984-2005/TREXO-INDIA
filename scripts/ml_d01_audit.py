"""Reproducible D01 lineage audit + D01-corrected movement exports."""
import json, shutil, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from trexo.ml.governance.d01 import audit_lineage
from trexo.ml.config import REPORT_DIR, REPO_ROOT

res = audit_lineage()
md = REPORT_DIR / "d01_lineage_audit.md"
if md.exists():
    shutil.copyfile(md, REPO_ROOT / "docs" / "D01_LINEAGE_AUDIT.md")
print(json.dumps({
    "decision": res["decision"],
    "d01_rows": res["d01"]["row_count"],
    "net_line_value": res["d01"]["net_line_value"],
    "in_valid_sales": res["ml_dataset_presence"]["d01_rows_in_valid_sales"],
    "B_in_valid_sales": res["ml_dataset_presence"]["stockcode_B_rows_in_valid_sales"],
    "source_reconciliation_ok": res["source_verification"]["source_reconciliation_ok"],
    "corrected_movement_clean": res["corrected_movement_clean"],
    "processed_stage_contains_B": [p["contains_stockcode_B"] for p in res["processed_stage_artifacts"]],
}, indent=2))
