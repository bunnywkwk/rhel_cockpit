# rhel_cockpit - Knowledge Base & Q&A Reference

This document captures the core architecture decisions, security rationale, and technical justifications for the `rhel_cockpit` role.

---

## ❓ Core Q&A Reference

### Q1: What is Cockpit and why do we use `cockpit-machines` instead of `virt-manager`?
* **A**:
  * **`virt-manager` (The Legacy Tool)**: A heavy desktop GTK application. It requires X11 graphical libraries, X-forwarding over SSH, or a full desktop environment installed on the server. Red Hat deprecated it in RHEL 8 and removed it in RHEL 9/10.
  * **`cockpit-machines` (The Modern Tool)**: A lightweight web module that connects directly to the local Libvirt sockets. It enables administrators to create, clone, start, stop, pause, snapshot, and view graphical VNC/SPICE consoles of VMs through any standard web browser over HTTPS on port `9090`.
  * **Headless Security**: Enterprise hypervisors must run headless (minimal text-only OS) to minimize memory overhead, reduce attack surface, and satisfy CIS security benchmarks.

---

### Q2: How does Cockpit communicate with Libvirt on RHEL 9 vs. RHEL 10?
* **A**:
  * **On RHEL 9**: Cockpit connects to the monolithic `/run/libvirt/libvirt-sock` managed by `libvirtd.socket`.
  * **On RHEL 10**: Cockpit connects directly to the modular driver sockets:
    * `/run/libvirt/virtqemud-sock` (for VM state and compute)
    * `/run/libvirt/virtnetworkd-sock` (for network interfaces and bridges)
    * `/run/libvirt/virtstoraged-sock` (for storage pools and disk volumes)
  * Cockpit's backend (`cockpit-machines`) automatically supports both architectures seamlessly through the standard libvirt API.

---

### Q3: What packages make up the full Cockpit Hypervisor Management Suite?
* **A**:
  1. **`cockpit`**: Core web service and web server daemon (`cockpit-ws`).
  2. **`cockpit-machines`**: Virtual machine management plugin (connects to KVM/Libvirt).
  3. **`cockpit-storaged`**: Disk, partition, LVM, and storage pool monitoring.
  4. **`cockpit-networkmanager`**: Network interface, bridge, and firewall monitoring.
  5. **`cockpit-system`**: CPU, RAM, journald system logs, and systemd service management.

---

### Q4: Why does Cockpit use Systemd Socket Activation (`cockpit.socket`)?
* **A**:
  * Instead of running a heavy web server process 24/7 in background memory, Systemd listens on TCP port `9090` via `cockpit.socket`.
  * When an administrator browses to `https://<host>:9090`, Systemd intercepts the TCP handshake and spawns `cockpit-ws.service` on demand.
  * After the administrator logs out and the session idles out, Cockpit can terminate to release host RAM.

---

### Q5: How do we prevent CIS Level 1 Hardening from breaking Cockpit?
* **A**:
  1. **Firewalld Port 9090**: CIS enforces strict default-deny firewall policies. We explicitly configure `firewalld` to permanently allow `service: cockpit` (port `9090/tcp`).
  2. **Session Idle Timeout**: CIS Benchmark requires terminating idle administrative sessions. We configure `IdleTimeout = 15` (or 30) minutes in `/etc/cockpit/cockpit.conf`.
  3. **PAM & TLS**: Cockpit utilizes the host's native PAM authentication and system crypto policies, ensuring compliance with CIS password and cipher standards.

---

### Q6: How do we verify that Cockpit is working properly after deployment?
* **A**:
  1. Check socket status: `systemctl is-active cockpit.socket` (must return `active`).
  2. Check firewall status: `firewall-cmd --list-services` (must include `cockpit`).
  3. Test HTTP/TLS response: `curl -k -I https://localhost:9090` (must return HTTP `200 OK` or `302/401 Redirect/Auth`).
  4. Open `https://<HOST_IP>:9090` in your web browser, log in with `root` or an admin user, and verify the **"Virtual Machines"** tab is visible and functional!

---

### Q7: Why do file modules specify `owner: root`, `group: root`, `mode: "0644"`, and where is "Others" defined?
* **A**:
  * **File Creation Modules** (`file`, `template`, `copy`) manage files on disk. CIS benchmarks require all configuration files in `/etc/` to be strictly owned by `root:root` with permissions no more permissive than `0644`.
  * **Package/Service/Firewall Modules** do not need `owner`/`group` because RPM packages embed internal ownership, services run in memory, and firewall rules operate in the Linux kernel.
  * **How `0644` defines "Others"**:
    * `0644` has 3 permission slots: `[6: Owner] [4: Group] [4: Others]`.
    * "Others" (World) is a universal catch-all in Linux meaning *"anyone who is not root and not in the root group"*.
    * Because "Others" means everyone else, Linux doesn't need an `others:` username setting; its permission is set directly by that 3rd octal digit (`4` = read-only)!

---

### Q8: Why parameterize socket activation in `defaults/main.yml` instead of hardcoding?
* **A**:
  * **Out-of-the-box Enforcement**: `defaults/main.yml` defaults to `cockpit_service_name: cockpit.socket`, `cockpit_service_state: started`, `cockpit_service_enabled: true`.
  * **Operational Flexibility**: Allowing variable overrides lets sysadmins temporarily disable Cockpit during emergency maintenance windows (`-e cockpit_service_state=stopped`) or run CI/CD container tests without modifying the role's source code.

---

### Q9: Do we need "Server with GUI" installed on the OS to run Cockpit?
* **A**:
  * **NO! Always use "Minimal Install" (Headless Server).**
  * **Server**: Cockpit is simply a web daemon on the server listening on TCP port `9090`. It needs zero desktop graphics (no GNOME, no X11, no Wayland), saving 1.5+ GB of RAM for virtual machines.
  * **Client**: You open Google Chrome or Firefox on **your laptop** and browse to `https://<server>:9090`. Your laptop's browser renders the GUI!

---

### Q10: What caused "Virtualization service (libvirt) is not active" in Cockpit, and why is this expected?
* **A**:
  * **Frontend vs Backend Separation**:
    * `rhel_cockpit` is the **Frontend Web Console** (`cockpit-machines`).
    * `rhel_kvm` is the **Backend Virtualization Engine** (`qemu-kvm`, `libvirtd`/`virtqemud`).
  * If a fresh VM only runs `rhel_cockpit`, Cockpit is live but waits for the `libvirt` engine to be started.
  * Running `rhel_kvm` provisions the libvirt sockets and storage pools, and Cockpit instantly recognizes the active hypervisor upon browser refresh!
