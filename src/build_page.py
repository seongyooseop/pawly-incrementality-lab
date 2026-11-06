"""Build the page: one self-contained HTML file with seven tabs.

Injects every chapter's output (and the work log) into site/template.html and
writes site/index.html. No server or library needed to open it.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"


def worklog():
    text = (ROOT / "docs" / "work_log.md").read_text(encoding="utf-8")
    entries = re.findall(r"\*\*(\d+\. [^*]+)\*\*\n(.+?)(?=\n\n|\Z)", text, flags=re.S)
    return [{"title": t.strip(), "body": b.strip().replace("\n", " ")} for t, b in entries]


def main():
    data = {
        "playbook": json.loads((OUT / "ch0_playbook.json").read_text()),
        "ch1_design": json.loads((OUT / "ch1_design.json").read_text()),
        "ch1_readout": json.loads((OUT / "ch1_readout.json").read_text()),
        "ch1_montecarlo": json.loads((OUT / "ch1_montecarlo.json").read_text()),
        "ch2": json.loads((OUT / "ch2_causal_impact.json").read_text()),
        "ch3": json.loads((OUT / "ch3_auto_bidding.json").read_text()),
        "ch4": json.loads((OUT / "ch4_mmm.json").read_text()),
        "cross": json.loads((OUT / "cross_platform.json").read_text()),
        "report": json.loads((OUT / "ch5_report.json").read_text()),
        "validation": json.loads((OUT / "validation.json").read_text()),
        "log": worklog(),
    }
    blob = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    html = (ROOT / "site" / "template.html").read_text(encoding="utf-8").replace("/*__DATA__*/", blob)
    (ROOT / "site" / "index.html").write_text(html, encoding="utf-8")
    print(f"site/index.html: {len(html) / 1024:.0f} KB, {len(data['log'])} log entries")


if __name__ == "__main__":
    main()
