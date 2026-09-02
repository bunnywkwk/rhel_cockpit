# rhel_cockpit - Role Goals & Implementation Procedure

## 🎯 Role Mission

Transform a bare RHEL 9 or RHEL 10 KVM host into a remotely managed hypervisor using the **Cockpit Web Console** (`https://<host>:9090`) with:

- **VM Lifecycle Management**: Native integration with KVM/Libvirt via `cockpit-machines`.
- **Zero Desktop GUI**: Strict headless server architecture (no X11/Wayland, ensuring legacy `virt-manager` is absent).
- **Systemd Socket Activation**: Cockpit listens on `cockpit.socket` (port 9090) with on-demand daemon startup.
- **Firewall Management**: Automated `firewalld` configuration to permit Cockpit web access.
- **CIS Hardening Readiness**: Configured to remain accessible and secure even after CIS Level 1 benchmarks are applied.

---

## 📋 Step-by-Step Implementation Procedure

```
rhel_cockpit /
├── 1. Role Metadata & Defaults
│   ├── meta/main.yml                 # Galaxy info, EL 9 & 10 platforms, collection dependencies
│   └── defaults/main.yml             # Packages list, port 9090, firewall toggle, session timeout
│
├── 2. Sub-Task Pipeline (tasks/)
│   ├── tasks/main.yml                # Master orchestrator
│   ├── tasks/preflight.yml           # OS version assertion & sanity checks
│   ├── tasks/packages.yml            # Install cockpit, cockpit-machines, ensure virt-manager absent
│   ├── tasks/config.yml              # /etc/cockpit/cockpit.conf configuration (Timeout, banner)
│   ├── tasks/service.yml             # Enable & start cockpit.socket
│   └── tasks/firewall.yml            # Firewalld rule for service: cockpit (port 9090)
│
├── 3. Handlers & Templates
│   ├── handlers/main.yml             # Handlers to restart cockpit.socket & reload firewalld
│   └── templates/cockpit.conf.j2     # Configuration template for /etc/cockpit/cockpit.conf
│
└── 4. Tests & Enterprise Documentation
    ├── ansible.cfg                   # Role discovery path (roles_path = ../)
    ├── tests/inventory & test.yml    # Test playbook and VM target inventory
    └── README.md                     # Architecture justifications, variable tables, verification
```

---

## ⚡ Task Execution Pipeline in `tasks/main.yml`

| Step  | Task File             | Responsibility                                                                                                                     |
| :---: | :-------------------- | :--------------------------------------------------------------------------------------------------------------------------------- |
| **1** | `tasks/preflight.yml` | Validates target OS family (`RedHat`) and versions (`9`, `10`).                                                                    |
| **2** | `tasks/packages.yml`  | Installs `cockpit`, `cockpit-machines`, `cockpit-storaged`, `cockpit-networkmanager`, and ensures legacy `virt-manager` is absent. |
| **3** | `tasks/config.yml`    | Generates `/etc/cockpit/cockpit.conf` with security settings (idle timeout, web banner).                                           |
| **4** | `tasks/service.yml`   | Enables and starts `cockpit.socket` using systemd socket activation.                                                               |
| **5** | `tasks/firewall.yml`  | Configures `firewalld` to permanently permit `service: cockpit` (port 9090).                                                       |

---

## 🔒 CIS Hardening Compatibility (Why this matters)

When Ansible Lockdown applies CIS Benchmark Level 1 in the main playbook:

1. **Firewall Default Deny**: CIS blocks all unapproved ports. The `rhel_cockpit` role opens `service: cockpit` in the active `firewalld` zone so the web console is never locked out.
2. **Headless Security**: CIS benchmarks penalize X11/GUI desktop packages on servers. By avoiding `virt-manager` and installing only the web plugin (`cockpit-machines`), the hypervisor remains headless and compliant.
3. **Session Idle Timeout**: Cockpit's configuration template sets idle session timeouts to comply with CIS session termination requirements.
