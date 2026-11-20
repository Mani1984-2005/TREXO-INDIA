import json, sys, time, datetime as dt
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from trexo.ml.config import REPORT_DIR, SEED
from trexo.ml.data_pipeline.pipeline import load_sales
from trexo.ml.retail.pricing.elasticity import weekly_price_panel, estimate_with_validation
from trexo.ml.registry.registry import save_model_bundle
t0 = time.time(); sales = load_sales(); panel = weekly_price_panel(sales)
est = estimate_with_validation(panel, n_boot=40, seed=SEED)
est["observation_period"] = [str(sales["Date"].min().date()), str(sales["Date"].max().date())]
est["response"] = "weekly distinct invoices per product (Poisson, product + week fixed effects)"
est["runtime_s"] = round(time.time() - t0, 1)
(REPORT_DIR / "retail").mkdir(parents=True, exist_ok=True)
(REPORT_DIR / "retail" / "pricing_elasticity_results.json").write_text(json.dumps(est, indent=2))
# scenario-use policy derived from validation (conservative bound = CI limit closest to zero)
use = {"central": est["coefficient"], "conservative": est["ci95"][1], "usable_as_pooled_prior": est["usable_as_pooled_prior"],
       "source_label": "estimated_pooled" if est["usable_as_pooled_prior"] else "assumed",
       "fallback_assumed_values": [-0.5, -1.0, -2.0]}
meta = save_model_bundle("pricing", {"elasticity": use}, {"validation": est, "random_seed": SEED,
        "status_note": "pooled associational elasticity of purchase frequency; product-level elasticities intentionally NOT produced (too noisy)"})
print(json.dumps(est, indent=2)); print(meta["model_version"])
