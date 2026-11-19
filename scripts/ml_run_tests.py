"""Execute the real test suite and record exact results (no hand-typed pass claims)."""
import json, os, platform, re, subprocess, sys, datetime as dt
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

def parse(out: str) -> dict:
    def n(word):
        vals = [int(x) for x in re.findall(rf"(\d+) {word}", out)]
        return max(vals) if vals else 0
    return {"passed": n("passed"), "failed": n("failed"), "errors": n("error"),
            "skipped": n("skipped"), "xfailed": n("xfailed"), "xpassed": n("xpassed")}

def run(label: str, env_extra: dict) -> dict:
    env = os.environ.copy()
    env.update({"PYTHONPATH": str(ROOT / "src"), **env_extra})
    p = subprocess.run([sys.executable, "-m", "pytest", "tests", "-q", "-rs"],
                       cwd=ROOT, capture_output=True, text=True, env=env)
    out = p.stdout + "\n" + p.stderr
    counts = parse(out)
    counts.update({"label": label, "returncode": p.returncode,
                   "command": "python -m pytest tests -q -rs",
                   "environment": env_extra,
                   "summary_line": next((l for l in reversed(out.splitlines()) if " passed" in l or " failed" in l or " error" in l), ""),
                   "output_tail": "\n".join(out.splitlines()[-40:])})
    return counts

import numpy, pandas, sklearn, lightgbm
result = {
    "executed_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
    "python": sys.version.split()[0],
    "platform": platform.platform(),
    "packages": {"numpy": numpy.__version__, "pandas": pandas.__version__,
                 "scikit-learn": sklearn.__version__, "lightgbm": lightgbm.__version__},
    "standard": run("standard", {}),
    "full_dataset": run("full_dataset", {"TREXO_SLOW_TESTS": "1"}),
}
(ROOT / "reports" / "ml").mkdir(parents=True, exist_ok=True)
(ROOT / "reports" / "ml" / "test_results.json").write_text(json.dumps(result, indent=2))
print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk in ("returncode", "passed", "failed", "errors", "skipped", "summary_line")}
                  for k, v in (("standard", result["standard"]), ("full_dataset", result["full_dataset"]))}, indent=2))
