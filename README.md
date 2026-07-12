# Home SOC Lab — Custom Threat Detection Pipeline with Wazuh

A self-hosted Security Operations Center lab built from scratch on Wazuh,
featuring custom MITRE ATT&CK-mapped detection rules, validated against real
attack simulations, and enriched with live threat intelligence.

Every rule here was hand-written, deployed, debugged against real rule-engine
errors, and validated by actually triggering the attack behavior and
confirming the alert fires correctly — not just installed and left on
defaults.

## Architecture

```
                    ┌─────────────────────┐
                    │   Simulated Attacks   │
                    │  (SSH brute force,     │
                    │   sudo escalation)      │
                    └──────────┬───────────┘
                               │
                               ▼
        ┌──────────────────────────────────────────┐
        │         Target VM (Ubuntu ARM64)           │
        │            Wazuh Agent installed            │
        └───────────────────┬──────────────────────┘
                             │ logs/events (SSH, PAM, sudo)
                             ▼
        ┌──────────────────────────────────────────┐
        │       Manager VM (Ubuntu ARM64)            │
        │  ┌─────────────────────────────────────┐  │
        │  │  Wazuh Manager                        │  │
        │  │  - local_rules.xml (custom detections) │  │
        │  │  - Correlation & alerting engine        │  │
        │  └──────────────┬──────────────────────┘  │
        │  ┌──────────────▼──────────────────────┐  │
        │  │  Wazuh Indexer (OpenSearch)            │  │
        │  └──────────────┬──────────────────────┘  │
        │  ┌──────────────▼──────────────────────┐  │
        │  │  Wazuh Dashboard (web UI)               │  │
        │  └─────────────────────────────────────┘  │
        └───────────────────┬──────────────────────┘
                             │ alert JSON
                             ▼
        ┌──────────────────────────────────────────┐
        │      enrich_alerts.py (Python)              │
        │  - Extracts IPs from alerts                  │
        │  - Queries AbuseIPDB + VirusTotal (free)      │
        │  - Outputs enriched JSON with reputation data │
        └──────────────────────────────────────────┘
```

Built entirely on Apple Silicon (M-series Mac) using UTM for virtualization —
no cloud costs, no external dependencies beyond free-tier APIs.

## Stack

| Component | Tool | Notes |
|---|---|---|
| SIEM/XDR | Wazuh 4.14.6 | Free, open source, native ARM64 support |
| Virtualization | UTM (QEMU backend) | Free, Apple Silicon native |
| OS | Ubuntu Server 24.04 LTS ARM64 | Manager (4GB/2vCPU) + Target (2GB/1vCPU) |
| Threat intel | AbuseIPDB + VirusTotal APIs | Free tier |
| Enrichment | Custom Python script | requests-based, no external deps beyond that |

## Detections implemented

| Rule ID(s) | Detection | MITRE ATT&CK | Status |
|---|---|---|---|
| 100010 / 100011 / 100012 | SSH brute force with dynamic thresholding (5/10+ failures escalate severity) | T1110.001 | ✅ Validated — real attack simulated, confirmed correct 3-tier severity escalation |
| 100030 / 100031 | Sudo privilege escalation (single + repeated) | T1548.003 | ✅ Validated — real sudo escalation triggered, both rules fired correctly |
| 100032 | New admin account creation | T1136.001, T1098 | ✅ Validated |
| 100020–100022 | PowerShell abuse (encoded commands, download cradles, hidden window) | T1059.001, T1027, T1105, T1562.001 | 📝 Designed, not lab-validated |
| 100040–100042 | LOLBin abuse (certutil, mshta, rundll32) | T1218.002/.005/.011, T1140 | 📝 Designed, not lab-validated |

See `atomic-tests/validation_mapping.md` for the full validation log with
screenshots.

## The debugging story

Writing the rules was the easy part — getting them to actually load and fire
correctly surfaced real Wazuh rule-engine constraints that aren't obvious
from documentation alone:

1. **`same_source_ip` misuse** — this correlation tag is only valid on
   frequency-based rules that reference a parent via `if_matched_sid`. I'd
   initially placed it on a plain atomic rule, which crashed the manager on
   restart with `Invalid use of frequency/context options`.

2. **Reserved field collision** — `user` is a static/reserved field in
   Wazuh's schema, not a generic dynamic field. Using
   `<field name="user" type="pcre2">` failed with `Field 'user' is static`.
   The fix was Wazuh's dedicated `<user negate="yes">` tag instead.

3. **Wrong assumed rule IDs** — I initially referenced built-in Wazuh rule
   IDs `5401` (sudo) and `5901` (new user) from memory/convention. Neither
   actually existed in this Wazuh version — the real IDs, confirmed by
   reading actual alert data in the dashboard, were `5402` and `5902`. This
   is the most important lesson from the whole build: **verify against real
   system output, don't trust remembered IDs or tutorial conventions.**

Every one of these was caught by reading `/var/ossec/logs/ossec.log`
directly after a failed `systemctl restart`, rather than guessing blindly.

## Threat intel enrichment (SOAR-lite)

`scripts/enrich_alerts.py` reads Wazuh's alert log, extracts any external IP
addresses mentioned in each alert, and cross-references them against
AbuseIPDB and VirusTotal's free APIs — attaching reputation data (abuse
confidence score, report count, vendor detections) back onto the alert.

Tested against a mock alert referencing `8.8.8.8` and confirmed correct,
real API responses from both services:

```json
{
  "ip": "8.8.8.8",
  "abuseipdb": {
    "abuse_confidence_score": 0,
    "total_reports": 120,
    "country": "US",
    "isp": "Google LLC"
  },
  "virustotal": {
    "malicious": 0,
    "suspicious": 0,
    "harmless": 55
  }
}
```

This is a simplified version of what's called SOAR (Security Orchestration,
Automation, and Response) — automatically adding context to alerts so an
analyst doesn't have to manually look up every IP.

## Repo structure

```
home-soc-lab/
├── wazuh-rules/
│   └── local_rules.xml          # custom detection rules, MITRE-tagged
├── scripts/
│   └── enrich_alerts.py         # threat intel enrichment (SOAR-lite)
├── atomic-tests/
│   └── validation_mapping.md    # validation log with real results
├── setup-guide/
│   └── SETUP_GUIDE.md           # full beginner-friendly build guide
├── docs/
│   └── screenshots/             # alert screenshots proving each detection
└── README.md
```


