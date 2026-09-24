# rhel_cockpit - Knowledge Base & Q&A Reference

This document captures the core architecture decisions, security rationale, and technical justifications for the `rhel_cockpit` role.

---

## Core Q&A Reference

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
  2. **Session Idle Timeout**: CIS Benchmark requires terminating idle administrative sessions. We configure `IdleTimeout = 15` minutes in the `[Session]` section of `/etc/cockpit/cockpit.conf`.
  3. **PAM & TLS**: Cockpit utilizes the host's native PAM authentication and system crypto policies, ensuring compliance with CIS password and cipher standards.

---

### Q6: How do we verify that Cockpit is working properly after deployment?

- **A**:
  1. Check socket status: `systemctl is-active cockpit.socket` (must return `active`).
  2. Check firewall status: `firewall-cmd --list-services` (must include `cockpit`).
  3. Test HTTP/TLS response: `curl -k -I https://localhost:9090` (must return HTTP `200 OK` or `302/401 Redirect/Auth`).
  4. Open `https://<HOST_IP>:9090` in your web browser, log in with `root` or an admin user, and verify the **"Virtual Machines"** tab is visible and functional!

---

### Q7: Why do file modules specify `owner: root`, `group: root`, `mode: "0644"`, and where is "Others" defined?

- **A**:
  - **File Creation Modules** (`file`, `template`, `copy`) manage files on disk. CIS benchmarks require all configuration files in `/etc/` to be strictly owned by `root:root` with permissions no more permissive than `0644`.
  - **Package/Service/Firewall Modules** do not need `owner`/`group` because RPM packages embed internal ownership, services run in memory, and firewall rules operate in the Linux kernel.
  - **How `0644` defines "Others"**:
    - `0644` has 3 permission slots: `[6: Owner] [4: Group] [4: Others]`.
    - "Others" (World) is a universal catch-all in Linux meaning _"anyone who is not root and not in the root group"_.
    - Because "Others" means everyone else, Linux doesn't need an `others:` username setting; its permission is set directly by that 3rd octal digit (`4` = read-only)!

---

### Q8: Why are the socket name, state and enabled flag hardcoded in `service.yml`?

- **A**: They are not settings. The role always enables and starts `cockpit.socket`, so exposing them as variables would only give something to override by mistake.

---

### Q9: Do we need "Server with GUI" installed on the OS to run Cockpit?

- **A**:
  - **NO! Always use "Minimal Install" (Headless Server).**
  - **Server**: Cockpit is simply a web daemon on the server listening on TCP port `9090`. It needs zero desktop graphics (no GNOME, no X11, no Wayland), saving 1.5+ GB of RAM for virtual machines.
  - **Client**: You open Google Chrome or Firefox on **your laptop** and browse to `https://<server>:9090`. Your laptop's browser renders the GUI!

---

### Q10: What caused "Virtualization service (libvirt) is not active" in Cockpit, and why is this expected?

- **A**:
  - **Frontend vs Backend Separation**:
    - `rhel_cockpit` is the **Frontend Web Console** (`cockpit-machines`).
    - `rhel_kvm` is the **Backend Virtualization Engine** (`qemu-kvm`, `libvirtd`/`virtqemud`).
  - If a fresh VM only runs `rhel_cockpit`, Cockpit is live but waits for the `libvirt` engine to be started.
  - Running `rhel_kvm` provisions the libvirt sockets and storage pools, and Cockpit instantly recognizes the active hypervisor upon browser refresh!

---

### Q11: Are we enabling Cockpit port 9090, and how is it opened across the system?

- **A**:
  - **Yes, TCP port 9090 is coordinated across three system layers:**
    1. **Firewall Layer (`tasks/firewall.yml`)**: Enforcing `service: cockpit` in `firewalld`. In Enterprise Linux, `/usr/lib/firewalld/services/cockpit.xml` defines `<port protocol="tcp" port="9090"/>`. Enabling this service permits inbound traffic on port 9090.
    2. **Systemd Socket Layer (`tasks/service.yml`)**: Enabling `cockpit.socket`. The unit file contains `ListenStream=9090`, causing the Linux kernel to actively bind and listen on `0.0.0.0:9090`.
    3. **Application Layer**: Cockpit's default port is 9090. It cannot be changed in `cockpit.conf` (see `man cockpit.conf`), only via `cockpit.socket`, so the role sets nothing for it.

---

### Q12: What is `service_facts` and why is it superior to `command: systemctl is-active firewalld`?

- **A**:
  - **What it is**: `ansible.builtin.service_facts` is an official module that queries systemd directly via Python and returns a structured dictionary in `ansible_facts.services`.
  - **Why it beats raw `command`**:
    - Running `command: systemctl is-active firewalld` spawns a subshell process. If `firewalld` is stopped or not installed, `systemctl` exits with error code 3, failing the play unless masked with `failed_when: false`.
    - With `service_facts`, Ansible checks `'firewalld.service' in ansible_facts.services and ansible_facts.services['firewalld.service']['state'] == 'running'`. If `firewalld` is inactive or missing, the condition evaluates cleanly to `false` without errors or subshell overhead.

---

### Q13: Why did we move `cockpit_packages` to `vars/main.yml` and expose `rhel_cockpit_extra_packages: []` in `defaults/main.yml`?

- **A**:
  - **The List Replacement Trap**: If core packages are defined in `defaults/main.yml`, any user overriding `cockpit_packages` in `group_vars` (e.g. to install `cockpit-podman`) causes Ansible to replace the entire default list. As a result, **`cockpit-machines` is omitted**, and the hypervisor loses its Virtual Machine management tab.
  - **The Two-Tier Solution**:
    - `vars/main.yml` holds mandatory binaries (`cockpit`, `cockpit-machines`, `cockpit-storaged`, `cockpit-networkmanager`, `cockpit-system`) as protected role constants that cannot be accidentally replaced.
    - `defaults/main.yml` provides `rhel_cockpit_extra_packages: []` where administrators can safely add supplemental plugins without risking core hypervisor management tools.

---

### Q14: What causes `fatal: .git/index: index file smaller than expected` and how do we resolve it?

- **A**:
  - **The Cause**: Git's staging area cache (`.git/index`) requires a binary header of at least 12 bytes. If a system restart, terminal interruption, or IDE crash occurs while Git is writing to the index, the file is left truncated at 0 bytes. When Git tries to parse a 0-byte file, it throws this fatal error.
  - **Resolution**: Because `.git/index` is merely a temporary cache (all commit history lives safely in `.git/objects/`), you simply delete the 0-byte cache and rebuild it:
    ```bash
    rm -f .git/index
    git reset
    git status
    ```

---
