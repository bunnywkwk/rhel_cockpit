# Ansible Role: `rhel_cockpit`

An enterprise-grade Ansible role to deploy and configure the **Cockpit Web Console** with **Virtual Machine Management (`cockpit-machines`)** on **RHEL 9** and **RHEL 10** hypervisors.

This role strictly adheres to headless server design (ensuring legacy `virt-manager` desktop GUI is absent), enables Systemd Socket Activation on port `9090`, configures `firewalld` rules, and applies security banners and idle timeouts ready for CIS Benchmark Level 1 compliance.

---

## 🏗️ Architectural Overview & Technical Justifications

### 1. Web Console vs. Legacy `virt-manager`
* **Deprecated GUI**: Red Hat officially deprecated `virt-manager` (the desktop GTK app) in RHEL 8 and removed it in RHEL 9/10.
* **Headless Security**: Hypervisors run headless (minimal OS without X11 desktop) to reduce memory overhead and minimize attack surface.
* **Cockpit Web Console**: Provides full VM lifecycle management (create, start, stop, snapshot, view VNC/SPICE consoles) over secure HTTPS on port `9090`.

### 2. Systemd Socket Activation (`cockpit.socket`)
* Cockpit utilizes systemd socket activation on TCP port `9090`.
* **Zero Idle RAM**: The web daemon (`cockpit-ws`) only spins up on-demand when an administrator connects and shuts down when idle, saving hypervisor host memory.

### 3. CIS Benchmark Level 1 Compatibility
* **Firewalld Port 9090**: Opens `service: cockpit` permanently so the web console is never locked out when CIS default-deny firewall rules are applied.
* **Idle Session Timeout**: Sets `IdleTimeout = 15` in `/etc/cockpit/cockpit.conf` to satisfy CIS administrative session termination standards.
* **Security Banner**: Displays an authorized access warning banner on the login screen.

---

## 📋 Requirements & Collections

### Supported Platforms
* Red Hat Enterprise Linux 9 / AlmaLinux 9 / Rocky Linux 9
* Red Hat Enterprise Linux 10 / AlmaLinux 10 / CentOS Stream 10

### Required Collections
* `ansible.posix` (>= 1.5.0)
* `community.general` (>= 7.0.0)

---

## ⚙️ Role Variables

Available default variables are defined in [`defaults/main.yml`](defaults/main.yml):

| Variable | Default | Description |
| :--- | :--- | :--- |
| `cockpit_packages` | *(List)* | Packages installed (`cockpit`, `cockpit-machines`, `cockpit-storaged`, etc.). |
| `cockpit_absent_packages` | `[virt-manager]` | Legacy GUI packages ensured absent. |
| `cockpit_service_name` | `cockpit.socket` | Name of the socket unit to manage. |
| `cockpit_service_state` | `started` | Desired socket state (`started`). |
| `cockpit_service_enabled` | `true` | Whether socket starts on boot. |
| `cockpit_manage_firewall` | `true` | Opens port 9090 in `firewalld`. |
| `cockpit_firewall_zone` | `public` | Firewalld zone to configure. |
| `cockpit_port` | `9090` | Web console TCP port. |
| `cockpit_idle_timeout` | `15` | Session idle timeout in minutes (CIS requirement). |
| `cockpit_banner` | *(String)* | Authorized access login banner text. |
| `cockpit_allow_root_login`| `true` | Permits root administrative access via web console. |

---

## 🚀 Example Usage

### 1. Minimal Playbook
```yaml
---
- name: Deploy Cockpit Web Console
  hosts: hypervisors
  become: true
  roles:
    - role: rhel_cockpit
```

### 2. Custom Port and Security Banner
```yaml
---
- name: Deploy Cockpit with Custom Timeout
  hosts: hypervisors
  become: true
  vars:
    cockpit_idle_timeout: 30
    cockpit_banner: "WARNING: Company Production Hypervisor. Authorized Logins Only."
  roles:
    - role: rhel_cockpit
```

---

## 🔍 Verification & Health Checks

After running the role, verify Cockpit with the following commands:

```bash
# 1. Verify Socket Status
systemctl is-active cockpit.socket
# Expected output: active

# 2. Verify Firewall Service
firewall-cmd --list-services
# Expected output: includes 'cockpit'

# 3. Test HTTP Response
curl -k -I https://localhost:9090
# Expected output: HTTP/1.1 200 OK or 302/401 Redirect

# 4. Open Web Browser
# Navigate to: https://<HOST_IP>:9090
```

---

## 📄 License & Author
* **License**: MIT
* **Author**: Aeron (Trainee at AIRNAV)