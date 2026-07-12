# Home SOC Lab — Full Setup Guide (Apple Silicon Mac, 16GB RAM)

This guide assumes zero prior VM/Linux experience. Follow it phase by phase —
don't skip ahead, and confirm each phase works before moving to the next.

**Confirmed compatible:** Wazuh added native ARM64 support for its central
components in version 4.12+ (current stable: 4.14.5), so everything below
runs natively on your M5 chip — no emulation, no workarounds.

**RAM budget for your 16GB Mac:**
- Manager VM: 4GB RAM, 2 vCPU
- Target VM: 2GB RAM, 1 vCPU
- Total used: 6GB, leaving ~10GB for macOS itself — comfortable headroom.

---

## Phase 1: Install UTM + Download Ubuntu

1. Download UTM (free) from **https://mac.getutm.app** — or via Homebrew:
   ```
   brew install --cask utm
   ```
2. Drag it into Applications, open it once to confirm it launches.
3. Download **Ubuntu Server 24.04 LTS (ARM64)** ISO from:
   **https://ubuntu.com/download/server/arm**
   (~2-3GB, takes a few minutes)

✅ Checkpoint: You have UTM open and the Ubuntu ISO file downloaded (check
your Downloads folder for a `.iso` file).

---

## Phase 2: Create the Manager VM

This VM will run the actual Wazuh server (the "brain" of the SOC).

1. Open UTM, click the **"+"** button → **"Virtualize"** (not Emulate —
   Virtualize uses Apple's native virtualization, much faster).
2. Choose **Linux**.
3. Under "Boot ISO Image", browse to the Ubuntu ARM64 ISO you downloaded.
4. Hardware settings:
   - **Memory**: 4096 MB (4GB)
   - **CPU Cores**: 2
5. Storage: 40GB (default is usually fine, Wazuh + logs need reasonable space)
6. Network: leave as default (**Shared Network** / NAT) — this lets the VM
   reach the internet and lets your other VM talk to it.
7. Name the VM **"wazuh-manager"** and click Save.
8. Click the Play button to boot it. Follow the Ubuntu Server installer:
   - Choose language, keyboard layout (defaults are fine)
   - Network: leave on DHCP (automatic)
   - Skip proxy/mirror screens (defaults)
   - Disk: use the whole disk (default)
   - **Profile setup**: set a username/password you'll remember —
     e.g. username `wazuh-admin`, and a password you'll actually remember
     (you'll type it a lot via SSH)
   - **Important**: when asked, select **"Install OpenSSH server"** — this
     lets you connect to the VM from your Mac's Terminal instead of typing
     inside the tiny UTM window
   - Skip additional snaps/features, let it finish installing
9. Once installed, it'll prompt to reboot — let it, then remove/eject the
   ISO if UTM asks (so it doesn't try to reinstall from the ISO again).

✅ Checkpoint: You can log in with your username/password inside the UTM
window and see a Linux terminal prompt like `wazuh-admin@wazuh-manager:~$`.

### Find the VM's IP address
Once logged in, run:
```bash
ip addr show
```
Look for something like `inet 192.168.64.X` — write this IP down, you'll
need it to SSH in and later to connect the agent.

### Connect via your Mac's Terminal (much easier than the UTM window)
On your Mac, open **Terminal** (Cmd+Space, type "Terminal") and run:
```bash
ssh wazuh-admin@<the-ip-you-found>
```
Type "yes" if asked about authenticity, then enter your password. You're now
controlling the VM from a proper terminal — this is how we'll do everything
from here on.

---

## Phase 3: Create the Target VM

This is the "monitored" machine — the one we'll simulate attacks on.

Repeat the same steps as Phase 2, with these differences:
- **Memory**: 2048 MB (2GB)
- **CPU Cores**: 1
- Name it **"target-linux"**
- Use a simple username like `target-user`
- Also install OpenSSH server here too

Once installed, find its IP the same way (`ip addr show`), and confirm you
can SSH into it from your Mac too:
```bash
ssh target-user@<target-vm-ip>
```

✅ Checkpoint: You now have two VMs running, and you can SSH into both from
your Mac's Terminal (in two separate Terminal tabs/windows — keep both open,
you'll switch between them).

---

## Phase 4: Install Wazuh (all-in-one) on the Manager VM

SSH into **wazuh-manager** (not the target), then run the official
all-in-one installer:

```bash
curl -sO https://packages.wazuh.com/4.14/wazuh-install.sh && sudo bash ./wazuh-install.sh -a
```

This installs the manager, indexer, and dashboard together — takes 10-15
minutes. **Don't close the terminal or let your Mac sleep during this.**

At the end, it will print an admin password for the dashboard — **copy this
somewhere safe**, you can't easily see it again without a password reset
command.

### Confirm it worked
```bash
sudo systemctl status wazuh-manager
```
You should see `active (running)` in green.

### Access the dashboard
On your Mac, open a browser and go to:
```
https://<wazuh-manager-vm-ip>
```
(Yes, `https`, and yes your browser will warn about a self-signed
certificate — click "Advanced" → "Proceed anyway", this is expected for a
home lab.)

Log in with username `admin` and the password from the install output.

✅ Checkpoint: You see the Wazuh dashboard home screen in your browser.

---

## Phase 5: Install the Agent on the Target VM

Now we connect the target machine so the manager can watch it.

SSH into **target-linux**, then run (replace `<manager-ip>` with your actual
manager VM's IP address):

```bash
curl -sO https://packages.wazuh.com/4.x/apt/pool/main/w/wazuh-agent/wazuh-agent_4.14.5-1_arm64.deb
sudo WAZUH_MANAGER='<manager-ip>' dpkg -i ./wazuh-agent_4.14.5-1_arm64.deb
sudo systemctl daemon-reload
sudo systemctl enable wazuh-agent
sudo systemctl start wazuh-agent
```

### Confirm it worked
```bash
sudo systemctl status wazuh-agent
```
Should show `active (running)`.

Back in the **Wazuh dashboard** (in your Mac browser), go to
**Agents** in the left menu — you should see `target-linux` listed with a
green "Active" status.

✅ Checkpoint: Your target VM shows up as an active, connected agent in the
dashboard. This is the biggest milestone — the "camera" is now watching and
reporting back.

---

## Phase 6: Deploy the Custom Detection Rules

On the **manager** VM, we now add the custom rules from this project
(`wazuh-rules/local_rules.xml`).

1. From your Mac, copy the rules file to the manager VM:
   ```bash
   scp wazuh-rules/local_rules.xml wazuh-admin@<manager-ip>:/tmp/local_rules.xml
   ```
   (run this from the folder on your Mac where you saved the project files)

2. SSH into the manager VM, then move the file into place:
   ```bash
   sudo cp /tmp/local_rules.xml /var/ossec/etc/rules/local_rules.xml
   sudo chown wazuh:wazuh /var/ossec/etc/rules/local_rules.xml
   sudo systemctl restart wazuh-manager
   ```

3. Confirm no errors loading the rules:
   ```bash
   sudo tail -50 /var/ossec/logs/ossec.log
   ```
   Look for any line mentioning `local_rules.xml` with an error — if you see
   none, it loaded cleanly.

### Quick test: trigger a benign alert
On the **target** VM, deliberately fail an SSH login a few times from
another terminal to trigger rule 100011:
```bash
ssh nonexistentuser@localhost
```
(enter any wrong password 3-4 times, it'll fail — that's the point)

Then check the Wazuh dashboard → **Security Events** — you should see new
alerts appear within a few seconds mentioning failed login attempts.

✅ Checkpoint: You've seen your first custom alert appear live in the
dashboard.

---

## Phase 7: Simulate Real Attacks + Validate

Now we prove the rules work against realistic attack techniques, following
`atomic-tests/validation_mapping.md`. Since we're Linux-only for this build,
focus on:

- **SSH brute force** (rules 100010-100012)
- **Sudo privilege escalation** (rules 100030-100032)

Example for sudo escalation testing — on the target VM, run several sudo
commands in quick succession as a non-root user, and confirm rule 100031
fires in the dashboard.

For each one that fires correctly:
1. Screenshot the alert in the dashboard
2. Update `atomic-tests/validation_mapping.md`, changing ⬜ Pending to
   ✅ Validated

---

## Troubleshooting quick reference

- **VM won't boot / black screen**: make sure you selected "Virtualize" not
  "Emulate" when creating it in UTM.
- **Can't SSH in**: double check the IP with `ip addr show` — it can change
  after a reboot if using DHCP.
- **Dashboard won't load in browser**: confirm `sudo systemctl status
  wazuh-dashboard` shows active, and that you're using `https://` not `http://`.
- **Agent shows "Disconnected"**: check `sudo systemctl status wazuh-agent`
  on the target, and confirm the manager IP in
  `/var/ossec/etc/ossec.conf` on the target matches the manager's actual IP.
- **Mac feels slow while VMs run**: close other heavy apps (Chrome with many
  tabs, etc.) — 6GB across two VMs plus macOS should be fine on 16GB, but
  background apps add up.

---

## Once this all works

Move on to Phase 6 from the original plan (already covered above) then the
enrichment script (`scripts/enrich_alerts.py`) — copy it to the manager VM
and run it against `/var/ossec/logs/alerts/alerts.json` to test AbuseIPDB/VT
enrichment on any alerts containing external IPs.
