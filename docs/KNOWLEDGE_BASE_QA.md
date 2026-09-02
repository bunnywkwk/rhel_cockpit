# rhel_cockpit - Knowledge Base & Q&A Reference

This document captures the core architecture decisions, security rationale, and technical justifications for the `rhel_cockpit` role.

---

## ❓ Core Q&A Reference

### Q1: What is Cockpit and why do we use `cockpit-machines` instead of `virt-manager`?

- **A**:
  - **`virt-manager` (The Legacy Tool)**: A heavy desktop GTK application. It requires X11 graphical libraries, X-forwarding over SSH, or a full desktop environment installed on the server. Red Hat deprecated it in RHEL 8 and removed it in RHEL 9/10.
  - **`cockpit-machines` (The Modern Tool)**: A lightweight web module that connects directly to the local Libvirt sockets. It enables administrators to create, clone, start, stop, pause, snapshot, and view graphical VNC/SPICE consoles of VMs through any standard web browser over HTTPS on port `9090`.
  - **Headless Security**: Enterprise hypervisors must run headless (minimal text-only OS) to minimize memory overhead, reduce attack surface, and satisfy CIS security benchmarks.

---

### Q2: How does Cockpit communicate with Libvirt on RHEL 9 vs. RHEL 10?

- **A**:
  - **On RHEL 9**: Cockpit connects to the monolithic `/run/libvirt/libvirt-sock` managed by `libvirtd.socket`.
  - **On RHEL 10**: Cockpit connects directly to the modular driver sockets:
    - `/run/libvirt/virtqemud-sock` (for VM state and compute)
    - `/run/libvirt/virtnetworkd-sock` (for network interfaces and bridges)
    - `/run/libvirt/virtstoraged-sock` (for storage pools and disk volumes)
  - Cockpit's backend (`cockpit-machines`) automatically supports both architectures seamlessly through the standard libvirt API.

---

### Q3: What packages make up the full Cockpit Hypervisor Management Suite?

- **A**:
  1. **`cockpit`**: Core web service and web server daemon (`cockpit-ws`).
  2. **`cockpit-machines`**: Virtual machine management plugin (connects to KVM/Libvirt).
  3. **`cockpit-storaged`**: Disk, partition, LVM, and storage pool monitoring.
  4. **`cockpit-networkmanager`**: Network interface, bridge, and firewall monitoring.
  5. **`cockpit-system`**: CPU, RAM, journald system logs, and systemd service management.

---

### Q4: Why does Cockpit use Systemd Socket Activation (`cockpit.socket`)?

- **A**:
  - Instead of running a heavy web server process 24/7 in background memory, Systemd listens on TCP port `9090` via `cockpit.socket`.
  - When an administrator browses to `https://<host>:9090`, Systemd intercepts the TCP handshake and spawns `cockpit-ws.service` on demand.
  - After the administrator logs out and the session idles out, Cockpit can terminate to release host RAM.

---

### Q5: How do we prevent CIS Level 1 Hardening from breaking Cockpit?

- **A**:
  1. **Firewalld Port 9090**: CIS enforces strict default-deny firewall policies. We explicitly configure `firewalld` to permanently allow `service: cockpit` (port `9090/tcp`).
  2. **Session Idle Timeout**: CIS Benchmark requires terminating idle administrative sessions. We configure `IdleTimeout = 15` (or 30) minutes in `/etc/cockpit/cockpit.conf`.
  3. **PAM & TLS**: Cockpit utilizes the host's native PAM authentication and system crypto policies, ensuring compliance with CIS password and cipher standards.

---

### Q6: How do we verify that Cockpit is working properly after deployment?

- **A**:
  1. Check socket status: `systemctl is-active cockpit.socket` (must return `active`).
  2. Check firewall status: `firewall-cmd --list-services` (must include `cockpit`).
  3. Test HTTP/TLS response: `curl -k -I https://localhost:9090` (must return HTTP `200 OK` or `302/401 Redirect/Auth`).
  4. Open `https://<HOST_IP>:9090` in your web browser, log in with `root` or an admin user, and verify the **"Virtual Machines"** tab is visible and functional!
