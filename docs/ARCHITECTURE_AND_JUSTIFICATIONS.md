# rhel_cockpit - Role Architecture and Technical Justifications

## 1. Executive Summary

The `rhel_cockpit` role provisions Red Hat Enterprise Linux (RHEL 9 and RHEL 10) hosts with a lightweight, browser-based administration interface. In an enterprise KVM hypervisor architecture, this role provides the graphical management layer for virtual machines, storage pools, and host telemetry without requiring a desktop environment (GUI).

The role solves four key operational challenges:

1. **Headless Hypervisor Management**: Browser-based VM management (`cockpit-machines`) instead of a desktop GUI, so no X11/Wayland is needed on the host.
2. **Resource-Efficient Socket Activation**: Enforces systemd socket activation on TCP port 9090 (`cockpit.socket`) so zero background memory or CPU is consumed when no administrator is logged in.
3. **CIS Benchmark Level 1 Compliance**: Configures the session idle timeout (15 minutes) in `/etc/cockpit/cockpit.conf`.
4. **Resilient Variable Strategy**: Eliminates the Ansible list replacement trap by isolating mandatory management packages in `vars/main.yml` while exposing `rhel_cockpit_extra_packages` for optional plugins.

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
├── handlers/
│   └── main.yml
├── templates/
│   └── cockpit.conf.j2
└── docs/
    ├── ARCHITECTURE_AND_JUSTIFICATIONS.md
    ├── KNOWLEDGE_BASE_QA.md
    └── ROLE_GOALS_AND_CHECKLIST.md
```

### Directory-by-Directory Rationale

| Directory    | Purpose                        | Technical Justification                                                                                                                           |
| :----------- | :----------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------ |
| `meta/`      | Galaxy metadata & dependencies | Defines supported platforms (EL 9 and 10) (the role uses only `ansible.builtin` modules, so no extra collections are required).                                        |
| `defaults/`  | Configurable role variables    | Lowest precedence. Contains overridable settings: `rhel_cockpit_idle_timeout` and `rhel_cockpit_extra_packages`. |
| `vars/`      | Protected role constants       | High precedence. Stores the mandatory package list (`cockpit`, `cockpit-machines`, etc.) to prevent accidental list overwrites from `group_vars`. |
| `tasks/`     | Modular execution files        | Divides installation, configuration, and socket management into focused, maintainable task files.                                       |
| `handlers/`  | Event triggers                 | Restarts `cockpit.socket` only when `cockpit.conf` physically changes.                                                                 |
| `templates/` | Jinja2 templates               | Dynamically templates `/etc/cockpit/cockpit.conf` based on role variables.                                                                        |
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
   Exposes `rhel_cockpit_extra_packages: []`. Administrators can add optional modules (e.g. `cockpit-podman`, `cockpit-sosreport`) without risking core VM management functionality.

[SCREENSHOT: Terminal output of cockpit package installation task completing with cockpit-machines installed]

---

## 4. Headless Hypervisor Architecture

Hypervisors are provisioned as **headless servers** (no graphical desktop environment). VM management is done through `cockpit-machines` in a browser over HTTPS (power on/off, snapshots, VNC/SPICE console, hardware editing), so no desktop application such as `virt-manager` is needed. `virt-manager` is not shipped in RHEL 9 or 10, so the role does not try to remove it.

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

### Step 2: `tasks/packages.yml` (Package Installation)

- **What it does**:
  1. Installs mandatory packages from `cockpit_packages` in `vars/main.yml`.
  2. Installs optional packages from `rhel_cockpit_extra_packages` in `defaults/main.yml`.
- **Justification**: Keeps mandatory packages out of `defaults/` so `group_vars` cannot replace them (the list replacement trap).

---

### Step 3: `tasks/config.yml` (Session Idle Timeout)

- **What it does**: Deploys `/etc/cockpit/cockpit.conf` from `templates/cockpit.conf.j2` and restarts `cockpit.socket` when it changes. The file contains only:
  ```ini
  [Session]
  IdleTimeout = 15
  ```
- **Justification**: CIS requires idle administrative sessions to be terminated. `IdleTimeout` is a `[Session]` option (see `man cockpit.conf`); Cockpit has no idle timeout unless it is set.
- **Deliberately not set** (Cockpit's defaults are used): the port (it cannot be set in `cockpit.conf`; it comes from `cockpit.socket`, default 9090), `AllowUnencrypted` (default `false`), the `/etc/cockpit` directory (owned by the `cockpit-ws` package), and the login banner (not needed). Root login is left at Cockpit's default: `root` is listed in `/etc/cockpit/disallowed-users`, so log in with an administrator account.

---

### Step 4: `tasks/service.yml` (Socket Activation)

- **What it does**: Enables and starts `cockpit.socket` using `ansible.builtin.systemd_service`.
- **Justification**: Standardizes on-demand socket activation: Cockpit listens on TCP 9090 and starts its web daemon only when someone connects.

---

## 7. Verification Checklist

Execute the following checks on the target hypervisor host:

1. **Package Verification**:

   ```bash
   rpm -q cockpit cockpit-machines
   # Expected: Both packages listed
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
   # Expected: [Session] with IdleTimeout = 15
   ```

4. **Firewall Status** (Cockpit is allowed by default; the role does not change the firewall):

   ```bash
   firewall-cmd --list-services | grep cockpit
   # Expected: cockpit included in service list
   ```

---

## 8. Mentor Feedback and Architecture Changelog

This section records architectural iterations implemented based on senior mentor guidance:

### 1. Two-Tier Package Architecture

- **Mentor Guidance**: Core management packages must never be placed in `defaults/` where user inventory variables can unintentionally replace the list.
- **Implementation**: Moved core packages (`cockpit`, `cockpit-machines`, `cockpit-storaged`, `cockpit-networkmanager`, `cockpit-system`) into `vars/main.yml`. Added `rhel_cockpit_extra_packages: []` in `defaults/main.yml` for user-defined plugins.

### 2. Elimination of Raw Command in Firewall Task (later removed)

- **Mentor Guidance**: Avoid invoking shell processes with `ansible.builtin.command` when native Ansible modules or facts can evaluate system state cleanly.
- **Implementation**: Replaced `command: systemctl is-active firewalld` with `ansible.builtin.service_facts` in `tasks/firewall.yml`. The whole firewall task was later removed because `cockpit` is already allowed in the `public` zone on stock RHEL 9 and 10.
- **Engineering Justification**: `service_facts` queries the systemd state directly in Python and loads `ansible_facts.services`. If `firewalld` is absent or inactive, the task skips cleanly without generating non-zero shell exit codes (such as exit code 3) or requiring messy `failed_when: false` workarounds. This guarantees 100% clean, idempotent execution on both minimal and fully-configured hosts.

### 3. Automated Verification Tool (later removed)

- **Mentor Guidance**: Provide an on-host acceptance script to validate that Cockpit is operational and compliant.
- **Implementation**: A `verify_cockpit.py` script was built for this, then removed from the role. Verification is now the manual checklist in the Verification Checklist section and the README.
