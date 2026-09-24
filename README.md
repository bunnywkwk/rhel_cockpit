# Ansible Role: rhel_cockpit

An enterprise-grade Ansible role to deploy and configure the Cockpit Web Console with Virtual Machine Management (`cockpit-machines`) on RHEL 9 and RHEL 10 hypervisors.

This role keeps the hypervisor headless (no desktop GUI), enables Systemd Socket Activation on TCP port 9090, opens the port in firewalld, and applies the session idle timeout required by CIS Benchmark Level 1.

Task-by-task explanation (what each task does and why it exists): [docs/TASK_WALKTHROUGH.md](docs/TASK_WALKTHROUGH.md).
Architectural justifications and verification procedures: [docs/ARCHITECTURE_AND_JUSTIFICATIONS.md](docs/ARCHITECTURE_AND_JUSTIFICATIONS.md).

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
| `rhel_cockpit_manage_firewall`           | `true`           | Opens port 9090 in firewalld.                                                |
| `rhel_cockpit_firewall_zone`             | `public`         | Firewalld zone to configure.                                                 |
| `rhel_cockpit_idle_timeout`              | `15`             | Session idle timeout in minutes (CIS requirement).                           |

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

### 2. Extra Plugins and a Custom Idle Timeout

```yaml
---
- name: Deploy Cockpit with Plugins and Custom Timeout
  hosts: hypervisors
  become: true
  vars:
    rhel_cockpit_idle_timeout: 30
    rhel_cockpit_extra_packages:
      - cockpit-podman
  roles:
    - role: rhel_cockpit
```

---

## 5. Verification and Health Checks

### Manual CLI commands (run on the hypervisor)

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
