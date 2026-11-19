import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from trexo.ml.data_pipeline.pipeline import run_pipeline
print(json.dumps(run_pipeline(), indent=2))
