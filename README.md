# Ansible Role: rhel_cockpit

An enterprise-grade Ansible role to deploy and configure the Cockpit Web Console with Virtual Machine Management (`cockpit-machines`) on RHEL 9 and RHEL 10 hypervisors.

This role adheres strictly to headless server design (ensuring legacy `virt-manager` desktop GUI is absent), enables Systemd Socket Activation on TCP port 9090, configures firewalld rules, and applies security banners and idle timeouts ready for CIS Benchmark Level 1 compliance.

Detailed architectural justifications, folder structure breakdowns, and verification procedures are documented in [docs/ARCHITECTURE_AND_JUSTIFICATIONS.md](docs/ARCHITECTURE_AND_JUSTIFICATIONS.md).

---

## 1. Architectural Overview and Technical Justifications

### Web Console vs. Legacy virt-manager

- **Deprecated GUI**: Red Hat officially deprecated `virt-manager` (the desktop GTK app) in RHEL 8 and removed it in RHEL 9 and 10.
- **Headless Security**: Hypervisors run headless (minimal OS without an X11/Wayland desktop) to reduce memory overhead and minimize the attack surface.
- **Cockpit Web Console**: Provides complete VM lifecycle management (create, start, stop, snapshot, VNC/SPICE console access) over secure HTTPS on port 9090.

### Systemd Socket Activation (cockpit.socket)

- Cockpit utilizes systemd socket activation on TCP port 9090.
- **Zero Idle RAM**: The web daemon (`cockpit-ws`) only spins up on-demand when an administrator connects and shuts down when idle, saving hypervisor host memory.

### CIS Benchmark Level 1 Compatibility

- **Firewalld Port 9090**: Opens `service: cockpit` permanently so the web console is never locked out when CIS default-deny firewall rules are applied.
- **Idle Session Timeout**: Sets `IdleTimeout = 15` in `/etc/cockpit/cockpit.conf` to satisfy CIS administrative session termination standards.
- **Security Banner**: Displays an authorized access warning banner on the login screen.

---

## 2. Requirements and Collections

### Supported Platforms

- Red Hat Enterprise Linux 9 / AlmaLinux 9 / Rocky Linux 9
- Red Hat Enterprise Linux 10 / AlmaLinux 10 / CentOS Stream 10

### Required Collections

- `ansible.posix` (>= 1.5.0)
- `community.general` (>= 7.0.0)

---

## 3. Role Variables

Available default variables are defined in [defaults/main.yml](defaults/main.yml):

| Variable                            | Default          | Description                                                                  |
| :---------------------------------- | :--------------- | :--------------------------------------------------------------------------- |
| `rhel_cockpit_extra_packages`            | `[]`             | Optional extra Cockpit plugins (e.g. `cockpit-podman`, `cockpit-sosreport`). |
| `rhel_cockpit_absent_packages`           | `[virt-manager]` | Legacy GUI packages ensured absent to maintain a headless host.              |
| `rhel_cockpit_service_name`              | `cockpit.socket` | Name of the socket unit to manage.                                           |
| `rhel_cockpit_service_state`             | `started`        | Desired socket state (`started`).                                            |
| `rhel_cockpit_service_enabled`           | `true`           | Whether socket starts on boot.                                               |
| `rhel_cockpit_manage_firewall`           | `true`           | Opens port 9090 in firewalld.                                                |
| `rhel_cockpit_firewall_zone`             | `public`         | Firewalld zone to configure.                                                 |
| `rhel_cockpit_port`                      | `9090`           | Web console TCP port.                                                        |
| `rhel_cockpit_idle_timeout`              | `15`             | Session idle timeout in minutes (CIS requirement).                           |
| `rhel_cockpit_banner`                    | _(String)_       | Authorized access login banner text.                                         |
| `rhel_cockpit_allow_root_login`          | `true`           | Permits root administrative access via web console.                          |
| `cockpit_deploy_verification_tools` | `true`           | Deploys `/usr/local/bin/verify_cockpit.py` for automated compliance checks.  |

_Note: Mandatory core packages (`cockpit`, `cockpit-machines`, `cockpit-storaged`, `cockpit-networkmanager`, `cockpit-system`) are defined in `vars/main.yml` as protected role constants._

---

## 4. Example Usage

### 1. Minimal Playbook

```yaml
---
- name: Deploy Cockpit Web Console
  hosts: hypervisors
  become: true
  roles:
    - role: rhel_cockpit
```

### 2. Custom Port, Extra Plugins, and Security Banner

```yaml
---
- name: Deploy Cockpit with Plugins and Custom Timeout
  hosts: hypervisors
  become: true
  vars:
    rhel_cockpit_idle_timeout: 30
    rhel_cockpit_extra_packages:
      - cockpit-podman
    rhel_cockpit_banner: "WARNING: Authorized Access Only. All actions monitored."
  roles:
    - role: rhel_cockpit
```

---

## 5. Verification and Health Checks

### Automated 1-Click Verification Tool

This role deploys a standalone Python diagnostic verification script to `/usr/local/bin/verify_cockpit.py`.

SSH into the hypervisor host and execute:

```bash
/usr/local/bin/verify_cockpit.py
```

This tool automatically validates:

1. **Package Verification**: Confirms `cockpit` and `cockpit-machines` are installed, and `virt-manager` is absent.
2. **Socket Activation**: Confirms `cockpit.socket` is enabled, active, and listening on port 9090.
3. **Security Configuration**: Checks `/etc/cockpit/cockpit.conf` for 15-minute idle timeout and warning banner.
4. **Firewall Verification**: Confirms firewalld allows the `cockpit` service.
5. **Web Handshake**: Tests local HTTPS response on `https://127.0.0.1:9090`.

### Manual CLI Commands

```bash
# 1. Verify Socket Status
systemctl is-active cockpit.socket

# 2. Verify Port Listening
ss -tulpn | grep 9090

# 3. Verify Firewall Service
firewall-cmd --list-services | grep cockpit

# 4. Test HTTP Response
curl -k -I https://localhost:9090
```

---

## 6. License and Author

- **License**: MIT
- **Author**: Aeron (Trainee at AIRNAV)
