# Detection Validation Log

Real validation results — each row below reflects an actual attack
simulation run against the lab, not a hypothetical test plan.

## Validation Table

| Rule ID | Detection | ATT&CK Technique | Test Performed | Result |
|---|---|---|---|---|
| 100010 | SSHD repeated failed login (base detection) | T1110.001 | `ssh nonexistentuser@localhost` with wrong password, repeated | ✅ Validated — fired on every failed attempt as expected |
| 100011 | SSH brute force (6+ failures in 120s) | T1110.001 | Same as above, sustained for 6+ attempts | ✅ Validated — correctly escalated to level 10 alert |
| 100012 | SSH brute force HIGH CONFIDENCE (10+ in 60s) | T1110.001 | Same as above, sustained for 10+ attempts within 60s | ✅ Validated — correctly escalated to level 12 alert |
| 100030 | Sudo privilege escalation (single event) | T1548.003 | `sudo whoami` as non-root user | ✅ Validated — fired correctly after fixing rule ID reference (5401 → 5402) |
| 100031 | Sudo privilege escalation (5+ in 5 min) | T1548.003 | Repeated `sudo whoami` x6 in quick succession | ✅ Validated — frequency correlation fired correctly |
| 100032 | New admin account creation | T1136.001, T1098 | `sudo useradd -m testadmin && sudo usermod -aG sudo testadmin` | ⚠️ Rule ID corrected (5901 → 5902) via real dashboard data. Field mapping for group membership (`user.groups`) still pending empirical verification against actual event fields. |
| 100020 | PowerShell encoded command | T1059.001 | N/A | 📝 Not tested — requires Windows VM, out of scope for this Linux-only build |
| 100021 | PowerShell download cradle | T1105 | N/A | 📝 Not tested — Windows-only |
| 100022 | PowerShell hidden window / bypass | T1562.001 | N/A | 📝 Not tested — Windows-only |
| 100040 | certutil LOLBin abuse | T1218.002 | N/A | 📝 Not tested — Windows-only |
| 100041 | mshta LOLBin abuse | T1218.005 | N/A | 📝 Not tested — Windows-only |
| 100042 | rundll32 LOLBin abuse | T1218.011 | N/A | 📝 Not tested — Windows-only |

## Key lesson from validation

Two of the three Linux detection rules initially failed to fire — not
because the detection logic was wrong, but because the referenced built-in
Wazuh rule IDs were incorrect (assumed from memory/convention rather than
verified). This was only caught by examining real alert data in the
dashboard after triggering the actual behavior, which showed the true rule
IDs (`5402` for sudo, `5902` for new user) rather than the initially assumed
`5401`/`5901`.

**Takeaway:** empirical verification against live system output is
non-negotiable when writing correlation rules — tutorial conventions and
memory are not a substitute for checking actual behavior.

## Screenshots

Place screenshots proving each validated detection in
`docs/screenshots/`, named to match the rule ID, e.g.:
- `100011-100012-ssh-bruteforce-escalation.png`
- `100030-100031-sudo-escalation.png`
- `enrichment-8888-abuseipdb-vt.png`
