import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import pandas as pd
from trexo.ml.config import *
from trexo.ml.data_pipeline.pipeline import load_sales
from trexo.ml.features.labels import build_training_table
from trexo.ml.simulation.backtest import simulate
H = HorizonConfig(); sales = load_sales()
# calibration table cutoffs every 30d from 2011-03-10; simulated cutoffs are later, label-complete only
cal_cut = list(pd.date_range("2011-03-10", "2011-10-10", freq="30D"))
cal = build_training_table(sales, cal_cut, H.label_horizon_days)
sim_cut = ["2011-06-08", "2011-07-08", "2011-08-07", "2011-09-06", "2011-10-06"]
res = simulate(sales, cal, sim_cut, H.label_horizon_days, pause_threshold=0.6)
res.to_csv(REPORT_DIR / "simulation_backtest_by_cutoff.csv", index=False)
agg = res.groupby("strategy")[["units_bought", "units_sold_of_bought", "excess_units", "unmet_demand_units",
      "purchase_lines_on_zero_demand_products", "units_bought_on_zero_demand_products", "actual_demand_units"]].sum()
agg["fill_rate_proxy"] = agg["units_sold_of_bought"] / agg["actual_demand_units"]
agg["turnover_proxy"] = agg["units_sold_of_bought"] / agg["units_bought"]
agg.to_csv(REPORT_DIR / "simulation_backtest_summary.csv"); pd.set_option("display.width", 250)
print(res.to_string()); print(agg.T.to_string())
