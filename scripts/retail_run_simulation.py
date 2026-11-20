"""Chronological clearance replay: REAL demand, ASSUMED stock/cost/response. Baseline = no discounts; TREXO = risk/coverage-triggered,
floor-protected offers chosen by the scenario objective. Sensitivity to wrongly-assumed elasticity is part of the result."""
import json, sys, itertools
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from trexo.ml.config import REPORT_DIR, HorizonConfig
from trexo.ml.data_pipeline.pipeline import load_sales
from trexo.ml.features.labels import build_training_table
from trexo.ml.retail.retail_simulation.replay import run_replay, ReplayAssumptions
sales = load_sales(); H = HorizonConfig()
train_cut = list(pd.date_range("2011-03-10", "2011-06-08", freq="30D"))          # label-complete before the replay start
cal = build_training_table(sales, train_cut, H.label_horizon_days)
iso = IsotonicRegression(y_min=0, y_max=1, out_of_bounds="clip").fit(cal["days_since_last_sale"], cal["y_inactive"])
START, WEEKS = "2011-08-10", 17                       # 17 complete weeks to 2011-12-07 (data ends 2011-12-09)
pooled = json.loads((REPORT_DIR / "retail" / "pricing_elasticity_results.json").read_text())["coefficient"]
rows = []
def go(label, **kw):
    a = ReplayAssumptions(**kw); r = run_replay(sales, iso, START, WEEKS, a)
    for arm in ("baseline", "trexo"):
        rows.append({"scenario": label, "arm": arm, **{k: v for k, v in kw.items()}, **r[arm]})
# S0: how much does the assumed write-off severity drive the conclusion? (decision = truth = pooled estimate)
for lgd in (0.0, 0.25, 0.5, 1.0): go(f"loss_given_dead={lgd} (e=pooled)", decision_elasticity=pooled, true_elasticity=pooled, loss_given_dead=lgd)
# S1: decision engine and customers agree (decision elasticity = true elasticity)
for e in (0.0, -0.5, pooled, -1.0, -2.0): go(f"decision=true e={e:.2f}", decision_elasticity=min(e, -1e-9) if e == 0 else e, true_elasticity=e)
# S2: engine believes the estimated pooled elasticity, customers differ
for te in (0.0, -0.3, -1.5): go(f"engine believes pooled, truth={te}", decision_elasticity=pooled, true_elasticity=te)
# S3: sensitivity to the ASSUMED initial stock and cost ratio (truth = pooled)
for sm, cr in itertools.product((1.0, 2.0), (0.5, 0.75)): go(f"stock x{sm}, cost ratio {cr} (truth pooled)", stock_multiple=sm, cost_ratio=cr, decision_elasticity=pooled, true_elasticity=pooled)
d = pd.DataFrame(rows); d.to_csv(REPORT_DIR / "retail" / "simulation_clearance_replay.csv", index=False)
piv = d.pivot(index="scenario", columns="arm", values=["gross_profit", "profit_after_assumed_writeoff", "units_sold", "ending_stock_cost_value", "discount_expense_vs_list", "leftover_units_zero_recent_demand", "offers_applied_product_weeks"])
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
out = pd.DataFrame({"dGP": piv["gross_profit"]["trexo"] - piv["gross_profit"]["baseline"], "dUnits": piv["units_sold"]["trexo"] - piv["units_sold"]["baseline"],
                    "dProfitAfterWO": piv["profit_after_assumed_writeoff"]["trexo"] - piv["profit_after_assumed_writeoff"]["baseline"], "dEndStockCost": piv["ending_stock_cost_value"]["trexo"] - piv["ending_stock_cost_value"]["baseline"],
                    "discount_exp": piv["discount_expense_vs_list"]["trexo"], "dLeftoverZeroDemand": piv["leftover_units_zero_recent_demand"]["trexo"] - piv["leftover_units_zero_recent_demand"]["baseline"],
                    "offers": piv["offers_applied_product_weeks"]["trexo"]}).round(0)
print(out.to_string()); b = d[(d.arm == "baseline")].iloc[0]; print("baseline ref:", b[["initial_units", "units_sold", "sell_through", "gross_profit", "ending_stock_cost_value", "products"]].to_dict())
