# rhel_cockpit - Role Goals & Progress Checklist

## Role Mission
Transform a bare RHEL 9 or RHEL 10 KVM host into a remotely managed hypervisor using the **Cockpit Web Console** (`https://<host>:9090`) with:
* **VM Lifecycle Management**: Native integration with KVM/Libvirt via `cockpit-machines`.
* **Zero Desktop GUI**: Headless server architecture (no X11/Wayland); VMs are managed in the browser.
* **Systemd Socket Activation**: Cockpit listens on `cockpit.socket` (port 9090) with on-demand daemon startup.
* **CIS Hardening Readiness**: Configured to remain accessible and secure even after CIS Level 1 benchmarks are applied.

---

## Role Checklist

### Step 1: Metadata & Defaults (Completed)
- [x] **`meta/main.yml`**: Galaxy metadata, EL 9 & 10 platform support, no collection requirements (only `ansible.builtin` modules).
- [x] **`defaults/main.yml`**: Configurable defaults: extra Cockpit packages and the session idle timeout.

---

### Step 2: Tasks Implementation (Completed)
- [x] **`tasks/main.yml`**: Master orchestrator calling sub-tasks in logical sequence.
- [x] **`tasks/preflight.yml`**: OS assertion (`RedHat` family, versions `9` and `10`).
- [x] **`tasks/packages.yml`**: DNF installation of `cockpit`, `cockpit-machines`, `cockpit-storaged`, `cockpit-networkmanager`, `cockpit-system`.
- [x] **`tasks/config.yml`**: Configuration of `/etc/cockpit/cockpit.conf` (session idle timeout).
- [x] **`tasks/service.yml`**: Systemd socket activation management (`cockpit.socket`).

---

### Step 3: Handlers, Templates & Tests (Completed)
- [x] **`handlers/main.yml`**: Handler to restart `cockpit.socket` when `cockpit.conf` changes.
- [x] **`templates/cockpit.conf.j2`**: Jinja2 template for `/etc/cockpit/cockpit.conf`.
- [x] **`ansible.cfg` & `tests/`**: Role path discovery, YAML inventory (`tests/inventory.yml`), and test playbook (`tests/test.yml`).

---

### Step 4: Documentation (Completed)
- [x] **`README.md`**: Complete architectural justifications, compatibility matrix, variable reference table, and verification commands.
- [x] **`docs/`**: Isolated Q&A knowledge base and implementation checklist.
