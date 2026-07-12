#!/usr/bin/env python3
"""
Alert Enrichment Script - Home SOC Lab
----------------------------------------
Reads Wazuh alerts (JSON) and enriches any IP addresses found with
reputation data from AbuseIPDB and VirusTotal (both free tier APIs).

Usage:
    python3 enrich_alerts.py --alert-file /var/ossec/logs/alerts/alerts.json

Setup:
    1. Get a free AbuseIPDB API key: https://www.abuseipdb.com/api
    2. Get a free VirusTotal API key: https://www.virustotal.com/gui/join-us
    3. Export them as environment variables before running:
         export ABUSEIPDB_API_KEY="your_key_here"
         export VT_API_KEY="your_key_here"

This is intentionally simple/synchronous (no async) so it's easy to read
and demo in an interview - the point is showing SOAR-lite enrichment logic,
not building a production-grade async pipeline.
"""

import os
import re
import sys
import json
import time
import argparse
import requests

ABUSEIPDB_KEY = os.environ.get("ABUSEIPDB_API_KEY")
VT_KEY = os.environ.get("VT_API_KEY")

ABUSEIPDB_URL = "https://api.abuseipdb.com/api/v2/check"
VT_URL = "https://www.virustotal.com/api/v3/ip_addresses/{ip}"

IP_REGEX = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}"
    r"(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b"
)

# simple in-memory cache so we don't burn API quota re-checking the same IP
_cache = {}


def extract_ips(alert):
    """Pull candidate IPs out of common Wazuh alert fields."""
    ips = set()
    text_blob = json.dumps(alert)
    for match in IP_REGEX.findall(text_blob):
        # skip obviously private/reserved ranges - not useful to look up
        if match.startswith(("10.", "192.168.", "127.")) or match.startswith("172.1") \
           or match.startswith("172.2") or match.startswith("172.3"):
            continue
        ips.add(match)
    return ips


def check_abuseipdb(ip):
    if not ABUSEIPDB_KEY:
        return {"error": "ABUSEIPDB_API_KEY not set"}
    headers = {"Key": ABUSEIPDB_KEY, "Accept": "application/json"}
    params = {"ipAddress": ip, "maxAgeInDays": 90}
    try:
        resp = requests.get(ABUSEIPDB_URL, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json().get("data", {})
        return {
            "abuse_confidence_score": data.get("abuseConfidenceScore"),
            "total_reports": data.get("totalReports"),
            "country": data.get("countryCode"),
            "isp": data.get("isp"),
        }
    except requests.RequestException as e:
        return {"error": str(e)}


def check_virustotal(ip):
    if not VT_KEY:
        return {"error": "VT_API_KEY not set"}
    headers = {"x-apikey": VT_KEY}
    try:
        resp = requests.get(VT_URL.format(ip=ip), headers=headers, timeout=10)
        resp.raise_for_status()
        stats = resp.json()["data"]["attributes"]["last_analysis_stats"]
        return {
            "malicious": stats.get("malicious"),
            "suspicious": stats.get("suspicious"),
            "harmless": stats.get("harmless"),
        }
    except requests.RequestException as e:
        return {"error": str(e)}
    except KeyError:
        return {"error": "unexpected VT response shape"}


def enrich_ip(ip):
    if ip in _cache:
        return _cache[ip]

    result = {
        "ip": ip,
        "abuseipdb": check_abuseipdb(ip),
        "virustotal": check_virustotal(ip),
    }
    _cache[ip] = result

    # free-tier rate limits are generous but not infinite - be polite
    time.sleep(1)
    return result


def process_alert_file(path, tail_only=False):
    enriched_alerts = []
    with open(path, "r") as f:
        lines = f.readlines()
        if tail_only:
            lines = lines[-50:]  # demo mode: only enrich the most recent alerts

    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            alert = json.loads(line)
        except json.JSONDecodeError:
            continue

        ips = extract_ips(alert)
        if not ips:
            continue

        enrichment = [enrich_ip(ip) for ip in ips]
        enriched_alerts.append({
            "rule_id": alert.get("rule", {}).get("id"),
            "rule_description": alert.get("rule", {}).get("description"),
            "agent": alert.get("agent", {}).get("name"),
            "enrichment": enrichment,
        })

    return enriched_alerts


def main():
    parser = argparse.ArgumentParser(description="Enrich Wazuh alerts with threat intel")
    parser.add_argument("--alert-file", required=True, help="Path to Wazuh alerts.json")
    parser.add_argument("--tail-only", action="store_true",
                         help="Only process the last 50 lines (useful for demos)")
    parser.add_argument("--output", default="enriched_alerts.json")
    args = parser.parse_args()

    results = process_alert_file(args.alert_file, tail_only=args.tail_only)

    with open(args.output, "w") as f:
        json.dump(results, f, indent=2)

    print(f"Enriched {len(results)} alerts containing external IPs.")
    print(f"Output written to {args.output}")


if __name__ == "__main__":
    main()
