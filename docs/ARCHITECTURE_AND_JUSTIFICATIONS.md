# rhel_cockpit - Role Architecture and Technical Justifications

## 1. Executive Summary

The `rhel_cockpit` role provisions Red Hat Enterprise Linux (RHEL 9 and RHEL 10) hosts with a lightweight, browser-based administration interface. In an enterprise KVM hypervisor architecture, this role provides the graphical management layer for virtual machines, storage pools, and host telemetry without requiring a desktop environment (GUI).

The role solves four key operational challenges:

1. **Headless Hypervisor Management**: Replaces desktop GUI tools like `virt-manager` with browser-based VM management (`cockpit-machines`), eliminating X11/Wayland overhead.
2. **Resource-Efficient Socket Activation**: Enforces systemd socket activation on TCP port 9090 (`cockpit.socket`) so zero background memory or CPU is consumed when no administrator is logged in.
3. **CIS Benchmark Level 1 Compliance**: Configures session idle timeouts (15 minutes) and security login warning banners in `/etc/cockpit/cockpit.conf`.
4. **Resilient Variable Strategy**: Eliminates the Ansible list replacement trap by isolating mandatory management packages in `vars/main.yml` while exposing `cockpit_extra_packages` for optional plugins.

---

## 2. Directory Structure and Architectural Justification

The role follows the standard Ansible Galaxy directory layout:

```
rhel_cockpit/
├── meta/
│   └── main.yml
├── defaults/
│   └── main.yml
├── vars/
│   └── main.yml
├── tasks/
│   ├── main.yml
│   ├── preflight.yml
│   ├── packages.yml
│   ├── config.yml
│   ├── service.yml
│   └── firewall.yml
├── handlers/
│   └── main.yml
├── templates/
│   └── cockpit.conf.j2
├── files/
│   └── verify_cockpit.py
└── docs/
    ├── ARCHITECTURE_AND_JUSTIFICATIONS.md
    ├── KNOWLEDGE_BASE_QA.md
    └── ROLE_GOALS_AND_CHECKLIST.md
```

### Directory-by-Directory Rationale

| Directory    | Purpose                        | Technical Justification                                                                                                                           |
| :----------- | :----------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------ |
| `meta/`      | Galaxy metadata & dependencies | Defines supported platforms (EL 9 and 10) and required collections (`ansible.posix`, `community.general`).                                        |
| `defaults/`  | Configurable role variables    | Lowest precedence. Contains overridable settings: `cockpit_port`, `cockpit_idle_timeout`, `cockpit_banner`, and `cockpit_extra_packages`.         |
| `vars/`      | Protected role constants       | High precedence. Stores the mandatory package list (`cockpit`, `cockpit-machines`, etc.) to prevent accidental list overwrites from `group_vars`. |
| `tasks/`     | Modular execution files        | Divides installation, configuration, socket management, and firewall into focused, maintainable task files.                                       |
| `handlers/`  | Event triggers                 | Flushes `cockpit.socket` restarts and `firewalld` reloads only when underlying configuration files physically change.                             |
| `templates/` | Jinja2 templates               | Dynamically templates `/etc/cockpit/cockpit.conf` based on role variables.                                                                        |
| `files/`     | Standalone tools               | Deploys `/usr/local/bin/verify_cockpit.py` for automated compliance verification.                                                                 |
| `docs/`      | Technical documentation        | Isolates role architecture design, justifications, and mentor changelogs within the role boundary.                                                |

---

## 3. Package Architecture: Core vs. Extra Packages

### The Problem: The List Replacement Trap

If `cockpit_packages` is defined in `defaults/main.yml`, any user specifying a custom plugin in their inventory (e.g. `cockpit_packages: [cockpit-podman]`) triggers Ansible's list replacement behavior. The entire default list is wiped out, and **`cockpit-machines` is never installed**. As a result, the hypervisor web console loses its Virtual Machines tab.

### The Solution: Two-Tier Package Strategy

1. **`vars/main.yml` (Mandatory Core Packages)**:
   Contains the minimum required set for headless hypervisor administration:
   - `cockpit`: Web console framework and authentication daemon.
   - `cockpit-machines`: Virtual machine lifecycle management interface (KVM / Libvirt).
   - `cockpit-storaged`: Disk partition and storage pool management interface.
   - `cockpit-networkmanager`: Network interface and bridge management.
   - `cockpit-system`: System telemetry, systemd services, and journal log inspection.

2. **`defaults/main.yml` (Optional Extra Packages)**:
   Exposes `cockpit_extra_packages: []`. Administrators can add optional modules (e.g. `cockpit-podman`, `cockpit-sosreport`) without risking core VM management functionality.

[SCREENSHOT: Terminal output of cockpit package installation task completing with cockpit-machines installed]

---

## 4. Headless Hypervisor Architecture: Why `virt-manager` is Absent

In enterprise datacenters, hypervisors are provisioned as **headless servers** (no graphical desktop environment):

- **The Problem with `virt-manager`**: `virt-manager` is a desktop application requiring GTK, X11, or Wayland libraries. Installing it on a hypervisor drags in hundreds of graphical dependencies (~400MB+), increases the system's attack surface, and requires X11 forwarding over SSH.
- **The Solution**: `tasks/packages.yml` explicitly enforces `state: absent` on `cockpit_absent_packages: [virt-manager]`.
- **The Replacement**: `cockpit-machines` provides full VM management (power on, power off, snapshot, console VNC/SPICE access, hardware editing) directly inside any web browser via HTTPS.

[SCREENSHOT: DNF task output confirming virt-manager is absent on the hypervisor host]

---

## 5. Systemd Socket Activation (Port 9090)

The role manages `cockpit.socket` rather than `cockpit.service`:

```
Client Browser (HTTPS) ---> Port 9090 ---> systemd (cockpit.socket)
                                               │ (On-Demand Activation)
                                               ▼
                                         cockpit-ws.service (Spun up)
                                               │ (Idle Timeout)
                                               ▼
                                         Terminates automatically
```

### Architectural Benefits:

1. **Zero Idle Resource Consumption**: When no administrator is logged into the web console, `cockpit-ws` is not running. Only the low-memory systemd socket listener is active.
2. **Automatic Scaling**: When an administrator navigates to `https://<hypervisor-ip>:9090`, systemd immediately launches the web service process.
3. **Resilience**: If the web process crashes, the socket continues listening and relaunches the service on the next connection attempt.

[SCREENSHOT: systemctl status cockpit.socket showing active (listening) on TCP port 9090]

---

## 6. Task-by-Task Implementation and Engineering Justification

### Step 1: `tasks/preflight.yml` (OS Validation)

- **What it does**: Asserts that `ansible_facts['os_family'] == 'RedHat'` and major version is `9` or `10`.
- **Justification**: Prevents accidental role execution on incompatible operating systems (Debian, Ubuntu) where Cockpit package names and paths differ.

---

### Step 2: `tasks/packages.yml` (Package Installation & Headless Enforcement)

- **What it does**:
  1. Installs mandatory packages from `cockpit_packages` in `vars/main.yml`.
  2. Installs optional packages from `cockpit_extra_packages` in `defaults/main.yml`.
  3. Ensures legacy GUI tools (`virt-manager`) are uninstalled (`state: absent`).
- **Justification**: Guarantees headless hypervisor standards and eliminates the list replacement trap.

---

### Step 3: `tasks/config.yml` (Security Configuration)

- **What it does**:
  1. Creates `/etc/cockpit` directory with mode `0755`.
  2. Deploys `/etc/cockpit/cockpit.conf` using `templates/cockpit.conf.j2`.
  3. Ensures root user access is permitted in `/etc/cockpit/disallowed-users` when `cockpit_allow_root_login: true`.
- **Justification**:
  - **CIS Idle Timeout**: Configures `IdleTimeout = 15` in both `[WebService]` and `[Session]` sections to comply with CIS Benchmark requirements for automated session termination.
  - **Security Warning Banner**: Displays legal and organizational authorization notices prior to authentication.

[SCREENSHOT: Cockpit login screen displaying the configured security authorization banner]

---

### Step 4: `tasks/service.yml` (Socket Activation)

- **What it does**: Enables and starts `cockpit.socket` using `ansible.builtin.systemd_service`.
- **Justification**: Standardizes on-demand socket activation, opening TCP port 9090.

---

### Step 5: `tasks/firewall.yml` (Firewall Rule Configuration)

- **What it does**:
  1. Gathers system service status facts into `ansible_facts.services` via `ansible.builtin.service_facts`.
  2. Permanently enables `service: cockpit` (TCP port 9090) in the public firewalld zone only when `firewalld.service` is verified to be in a running state.
- **Justification (Why `service_facts` beats `command`)**:
  - **The Flaw of Raw `command`**: Running `command: systemctl is-active firewalld` executes a raw shell subprocess. If `firewalld` is uninstalled or stopped, `systemctl` exits with return code 3, throwing a fatal error unless masked with `failed_when: false`.
  - **The Native `service_facts` Advantage**: `service_facts` queries the systemd bus directly using Ansible's internal Python engine. If `firewalld` is inactive or missing, the condition `'firewalld.service' in ansible_facts.services and ansible_facts.services['firewalld.service']['state'] == 'running'` simply evaluates to `false`, gracefully skipping the firewall task without errors or shell execution overhead.

[SCREENSHOT: firewall-cmd --list-services output showing cockpit listed in active zone]

---

### Step 6: `tasks/main.yml` (Verification Tool Deployment)

- **What it does**: Deploys `/usr/local/bin/verify_cockpit.py` with permissions `0755`.
- **Justification**: Delivers an automated on-host diagnostic tool that verifies packages, socket activation, port listening, security settings, and local HTTPS responses.

[SCREENSHOT: verify_cockpit.py execution showing all 5 verification phases passing (100%)]

---

## 7. Verification Checklist

Execute the following checks on the target hypervisor host:

1. **Package Verification**:

   ```bash
   rpm -q cockpit cockpit-machines
   # Expected: Both packages listed
   rpm -q virt-manager
   # Expected: package virt-manager is not installed
   ```

2. **Systemd Socket Status**:

   ```bash
   systemctl is-active cockpit.socket
   # Expected: active
   ss -tulpn | grep 9090
   # Expected: LISTEN on port 9090
   ```

3. **Security Configuration**:

   ```bash
   cat /etc/cockpit/cockpit.conf
   # Expected: IdleTimeout = 15 and Banner configured
   ```

4. **Firewall Status**:

   ```bash
   firewall-cmd --list-services | grep cockpit
   # Expected: cockpit included in service list
   ```

5. **Automated Verification Script**:
   ```bash
   /usr/local/bin/verify_cockpit.py
   # Expected: [OK] ALL COCKPIT ACCEPTANCE CRITERIA PASSED! (100%)
   ```

---

## 8. Mentor Feedback and Architecture Changelog

This section records architectural iterations implemented based on senior mentor guidance:

### 1. Two-Tier Package Architecture

- **Mentor Guidance**: Core management packages must never be placed in `defaults/` where user inventory variables can unintentionally replace the list.
- **Implementation**: Moved core packages (`cockpit`, `cockpit-machines`, `cockpit-storaged`, `cockpit-networkmanager`, `cockpit-system`) into `vars/main.yml`. Added `cockpit_extra_packages: []` in `defaults/main.yml` for user-defined plugins.

### 2. Elimination of Raw Command in Firewall Task

- **Mentor Guidance**: Avoid invoking shell processes with `ansible.builtin.command` when native Ansible modules or facts can evaluate system state cleanly.
- **Implementation**: Replaced `command: systemctl is-active firewalld` with `ansible.builtin.service_facts` in `tasks/firewall.yml`.
- **Engineering Justification**: `service_facts` queries the systemd state directly in Python and loads `ansible_facts.services`. If `firewalld` is absent or inactive, the task skips cleanly without generating non-zero shell exit codes (such as exit code 3) or requiring messy `failed_when: false` workarounds. This guarantees 100% clean, idempotent execution on both minimal and fully-configured hosts.

### 3. Automated Verification Tool

- **Mentor Guidance**: Provide an on-host acceptance script to validate that Cockpit is operational and compliant.
- **Implementation**: Built and deployed `/usr/local/bin/verify_cockpit.py` verifying package state, socket activation, port 9090 listening, CIS idle timeout, and local HTTPS connectivity.
