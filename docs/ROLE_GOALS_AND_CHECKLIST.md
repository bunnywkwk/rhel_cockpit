# rhel_cockpit - Role Goals & Progress Checklist

## 🎯 Role Mission
Transform a bare RHEL 9 or RHEL 10 KVM host into a remotely managed hypervisor using the **Cockpit Web Console** (`https://<host>:9090`) with:
* **VM Lifecycle Management**: Native integration with KVM/Libvirt via `cockpit-machines`.
* **Zero Desktop GUI**: Strict headless server architecture (no X11/Wayland, ensuring legacy `virt-manager` is absent).
* **Systemd Socket Activation**: Cockpit listens on `cockpit.socket` (port 9090) with on-demand daemon startup.
* **Firewall Management**: Automated `firewalld` configuration to permit Cockpit web access.
* **CIS Hardening Readiness**: Configured to remain accessible and secure even after CIS Level 1 benchmarks are applied.

---

## 📋 Role Checklist

### Step 1: Metadata & Defaults (Completed)
- [x] **`meta/main.yml`**: Galaxy metadata, EL 9 & 10 platform support, collection requirements (`ansible.posix`, `community.general`).
- [x] **`defaults/main.yml`**: Configurable defaults for Cockpit packages, absent GUI tools (`virt-manager`), socket activation, firewall, and security idle timeout.

---

### Step 2: Tasks Implementation (Completed)
- [x] **`tasks/main.yml`**: Master orchestrator calling sub-tasks in logical sequence.
- [x] **`tasks/preflight.yml`**: OS assertion (`RedHat` family, versions `9` and `10`).
- [x] **`tasks/packages.yml`**: DNF installation of `cockpit`, `cockpit-machines`, `cockpit-storaged`, `cockpit-networkmanager`, and removal of `virt-manager`.
- [x] **`tasks/config.yml`**: Configuration of `/etc/cockpit/cockpit.conf` (idle timeout, banner) and root login permissions.
- [x] **`tasks/service.yml`**: Systemd socket activation management (`cockpit.socket`).
- [x] **`tasks/firewall.yml`**: Firewalld rule permanent enablement for `service: cockpit` (port `9090`).

---

### Step 3: Handlers, Templates & Tests (Completed)
- [x] **`handlers/main.yml`**: Handlers to restart `cockpit.socket` and reload `firewalld`.
- [x] **`templates/cockpit.conf.j2`**: Jinja2 template for `/etc/cockpit/cockpit.conf`.
- [x] **`ansible.cfg` & `tests/`**: Role path discovery, YAML inventory (`tests/inventory.yml`), and test playbook (`tests/test.yml`).

---

### Step 4: Documentation (Completed)
- [x] **`README.md`**: Complete architectural justifications, compatibility matrix, variable reference table, and verification commands.
- [x] **`docs/`**: Isolated Q&A knowledge base and implementation checklist.
