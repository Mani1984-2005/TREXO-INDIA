"""END-TO-END DEMO on a SYNTHETIC shop (labelled). Shows the ledger -> ageing -> recovery pipeline works when verified inventory exists.
Nothing here is real data or a performance claim."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import pandas as pd
from trexo.ml.config import REPORT_DIR
from trexo.ml.retail.inventory.synthetic import synthetic_shop, LABEL
from trexo.ml.retail.service import RetailIntelligenceService
ev, prods, label = synthetic_shop(n_products=14, days=180, seed=11)
events = ev.assign(ts=ev["ts"].astype(str), expiry_date=None).to_dict("records")
svc = RetailIntelligenceService()
costs = {p: c for p, (c, _, _) in prods.items()}; prices = {p: pr for p, (_, pr, _) in prods.items()}
bal = svc.inventory_balances({"events": events})
pri = svc.stock_priority({"events": events, "as_of": "2011-06-29"})
rec = svc.recovery_recommendations({"events": events, "as_of": "2011-06-29", "prices": prices, "costs": costs, "rules": {"min_margin": 0.10, "max_discount": 0.2}, "holding_rate_annual": 0.2})
out = REPORT_DIR / "retail"
pd.DataFrame(bal["balances"]).assign(data_label=label).to_csv(out / "demo_synthetic_balances.csv", index=False)
pd.DataFrame(pri["queue"]).assign(data_label=label).to_csv(out / "demo_synthetic_selling_queue.csv", index=False)
pd.DataFrame(rec["plan"]).assign(data_label=label).to_csv(out / "demo_synthetic_recovery_plan.csv", index=False)
print(label, "balances", len(bal["balances"]), "queue", len(pri["queue"]), "plan", len(rec["plan"]), "rejected", len(bal["rejected_events"]))
print(pd.DataFrame(rec["plan"])[["rank", "product_id", "risk_classification", "recommended_actions", "confidence"]].head(6).to_string() if rec["plan"] else "no interventions")
