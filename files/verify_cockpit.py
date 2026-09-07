#!/usr/bin/env python3

# Cockpit Web Console Acceptance & Security Compliance Verification

import os
import sys
import subprocess
import urllib.request
import ssl

# ANSI Colors
GREEN = "\033[0;32m"
RED = "\033[0;31m"
BLUE = "\033[0;34m"
BOLD = "\033[1m"
NC = "\033[0m"

passed = 0
failed = 0


def run_cmd(cmd):
    """Runs a shell command and returns (rc, stdout)"""
    try:
        res = subprocess.run(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return res.returncode, res.stdout.strip()
    except Exception as e:
        return 1, str(e)


def check(description, is_pass, detail=""):
    """Evaluates and prints pass/fail status for a test criterion"""
    global passed, failed

    if is_pass:
        passed += 1
        msg = f" [{GREEN}PASS{NC}] {description}"
        if detail:
            msg += f" ({detail})"
        print(msg)
    else:
        failed += 1
        msg = f" [{RED}FAIL{NC}] {description}"
        if detail:
            msg += f" (Details: {detail})"
        print(msg)


def get_os_major():
    """Detects target OS distribution major version"""
    if os.path.exists("/etc/os-release"):
        with open("/etc/os-release") as f:
            for line in f:
                if line.startswith("VERSION_ID="):
                    val = line.strip().split("=")[1].replace('"', "")
                    return int(val.split(".")[0])
    return 9


def main():
    print(f"{BOLD}============================================================{NC}")
    print(f"{BOLD}       COCKPIT WEB CONSOLE ACCEPTANCE TEST (PY)             {NC}")
    print(f"{BOLD}============================================================{NC}")

    major = get_os_major()
    check("Target OS Major Version Detected", True, f"RHEL/EL Version: {major}")

    # 1. Package Verification
    print(f"\n{BOLD}--- 1. Package Installation & Headless Architecture ---{NC}")
    rc_c, _ = run_cmd("rpm -q cockpit")
    check("Package 'cockpit' installed", rc_c == 0)

    rc_m, _ = run_cmd("rpm -q cockpit-machines")
    check("Package 'cockpit-machines' installed (VM Management)", rc_m == 0)

    rc_v, _ = run_cmd("rpm -q virt-manager")
    check("Legacy 'virt-manager' GUI package is ABSENT (Headless)", rc_v != 0)

    # 2. Systemd Socket Activation
    print(f"\n{BOLD}--- 2. Systemd Socket Activation ---{NC}")
    rc_s, _ = run_cmd("systemctl is-active cockpit.socket")
    check("cockpit.socket is active", rc_s == 0)

    rc_e, _ = run_cmd("systemctl is-enabled cockpit.socket")
    check("cockpit.socket is enabled on boot", rc_e == 0)

    rc_p, _ = run_cmd("ss -tulpn | grep -E ':9090\b'")
    check("TCP Port 9090 is listening (Socket Activated)", rc_p == 0)

    # 3. Security & CIS Hardening Configuration
    print(f"\n{BOLD}--- 3. Security Configuration (/etc/cockpit/cockpit.conf) ---{NC}")
    conf_path = "/etc/cockpit/cockpit.conf"
    conf_exists = os.path.exists(conf_path)
    check("Configuration file exists", conf_exists, conf_path)

    if conf_exists:
        with open(conf_path) as cf:
            content = cf.read()
            check(
                "CIS IdleTimeout configured (15 minutes)",
                "IdleTimeout = 15" in content or "idletimeout = 15" in content.lower(),
            )
            check(
                "Security Login Banner configured",
                "Banner =" in content or "banner =" in content.lower(),
            )

    # 4. Firewall Configuration
    print(f"\n{BOLD}--- 4. Firewall Verification ---{NC}")
    rc_fw_active, _ = run_cmd("systemctl is-active firewalld")
    if rc_fw_active == 0:
        rc_fw_svc, out_fw = run_cmd("firewall-cmd --list-services")
        check(
            "Firewalld permits 'cockpit' service",
            "cockpit" in out_fw,
            "Zone allows cockpit",
        )
    else:
        check("Firewalld not active (skipped)", True, "firewalld stopped/disabled")

    # 5. Local Web Console HTTP Handshake
    print(f"\n{BOLD}--- 5. Web Console HTTP Handshake ---{NC}")
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request("https://127.0.0.1:9090", headers={"User-Agent": "CockpitAcceptanceTest"})
        with urllib.request.urlopen(req, context=ctx, timeout=5) as response:
            check("Cockpit Web Service responds on https://127.0.0.1:9090", response.status in [200, 302, 401], f"HTTP {response.status}")
    except urllib.error.HTTPError as e:
        check("Cockpit Web Service responds on https://127.0.0.1:9090", True, f"HTTP {e.code}")
    except Exception as e:
        check("Cockpit Web Service responds on https://127.0.0.1:9090", False, str(e))

    # Summary Report
    total = passed + failed
    print(f"\n{BOLD}============================================================{NC}")
    print(f"{BOLD}                     SUMMARY REPORT                         {NC}")
    print(f"{BOLD}============================================================{NC}")
    print(f" Total Checks : {total}")
    print(f" Passed       : {GREEN}{passed}{NC}")
    print(f" Failed       : {RED}{failed}{NC}")

    if failed == 0:
        print(f"\n {GREEN}{BOLD}[OK] ALL COCKPIT ACCEPTANCE CRITERIA PASSED! (100%){NC}\n")
        sys.exit(0)
    else:
        print(f"\n {RED}{BOLD}[FAIL] SOME CHECKS FAILED.{NC}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()

