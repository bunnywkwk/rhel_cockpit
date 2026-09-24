# rhel_cockpit: Task Walkthrough

Every task, in the order it runs: **what it does**, **why it is there**, and an **error seen** where a real error is related. "None seen" means the task never caused a failure. This role is small on purpose: it installs Cockpit, sets one CIS setting, starts the socket and opens the port.

## Execution order

| # | File | Purpose |
| :- | :--- | :--- |
| 1 | `tasks/main.yml` | Runs the steps below in order |
| 2 | `tasks/preflight.yml` | Stops the run on an unsupported OS |
| 3 | `tasks/packages.yml` | Installs Cockpit and its plugins |
| 4 | `tasks/config.yml` | Writes `/etc/cockpit/cockpit.conf` (session idle timeout) |
| 5 | `tasks/service.yml` | Enables and starts `cockpit.socket` |
| 6 | `tasks/firewall.yml` | Allows the `cockpit` service (TCP 9090) in firewalld |

Big idea: **Cockpit is the web front end, `rhel_kvm` is the engine.** `cockpit-machines` shows and controls the VMs, but the VMs and networks live in libvirt, which `rhel_kvm` sets up. Run `rhel_kvm` first (the orchestrator does).

---

## 1. `tasks/main.yml`

```yaml
- name: Run pre-flight OS validation
  ansible.builtin.include_tasks: preflight.yml
- name: Install Cockpit packages
  ansible.builtin.include_tasks: packages.yml
- name: Configure Cockpit session idle timeout
  ansible.builtin.include_tasks: config.yml
  when: rhel_cockpit_manage_config | bool
- name: Manage Cockpit systemd socket activation
  ansible.builtin.include_tasks: service.yml
- name: Configure firewall rules for Cockpit
  ansible.builtin.include_tasks: firewall.yml
  when: rhel_cockpit_manage_firewall | bool
```
- **What:** runs the step files in order. Config and firewall can be switched off with `rhel_cockpit_manage_config` / `rhel_cockpit_manage_firewall` (both `true` by default).
- **Why:** the order matters: packages first (they create `/etc/cockpit` and the `cockpit.socket` unit), config before the socket is started, firewall last.
- **Error seen:** none.

---

## 2. `tasks/preflight.yml`

```yaml
- name: Validate target operating system
  ansible.builtin.assert:
    that:
      - ansible_facts['os_family'] == 'RedHat'
      - ansible_facts['distribution_major_version'] in ['9', '10']
    fail_msg: "This role only supports RedHat / RHEL 9 and 10. ..."
```
- **What:** fails with a clear message unless the host is RedHat-family 9 or 10.
- **Why:** package names, paths and the firewalld service definition are only known to match on these versions; failing early beats half-configuring another OS.
- **Error seen:** none.

---

## 3. `tasks/packages.yml`

```yaml
- name: Install core Cockpit web console and hypervisor modules
  ansible.builtin.dnf:
    name: "{{ cockpit_packages }}"
    state: present
    update_cache: true
```
- **What:** installs the five packages in `vars/main.yml`:
  - `cockpit`: the web console itself.
  - `cockpit-machines`: the VM management page (create, start/stop, console). This is the reason the role exists.
  - `cockpit-storaged`: storage/disk management pages.
  - `cockpit-networkmanager`: network interface pages.
  - `cockpit-system`: system overview, services, logs.
- **Why the list is in `vars/`, not `defaults/`:** if it were a default, one inventory line `cockpit_packages: [cockpit-podman]` would replace the whole list and drop `cockpit-machines`. Extras go in `rhel_cockpit_extra_packages` instead.
- **`state: present`:** install if missing, never force upgrades.
- **`update_cache: true`:** refresh repo metadata first. Note that dnf refreshes **every enabled repo**, which is how a broken repo file elsewhere can fail this task.
- **Error seen [#10]:** `Cannot find a valid baseurl for repo: epel` (a broken `epel.repo` stub left by the Zabbix role, unrelated to Cockpit; it fails any dnf task that refreshes the cache).
- **Not verified:** whether `cockpit-storaged`, `cockpit-networkmanager` and `cockpit-system` are already pulled in by `cockpit` on RHEL. Listing them explicitly is harmless; check with `dnf repoquery --requires cockpit` on a RHEL host.

```yaml
- name: Install optional user-defined Cockpit packages
  ansible.builtin.dnf:
    name: "{{ rhel_cockpit_extra_packages }}"
    state: present
  when: rhel_cockpit_extra_packages | length > 0
```
- **What:** installs plugins listed in `rhel_cockpit_extra_packages` (e.g. `cockpit-podman`). Skipped when the list is empty.
- **Why:** a separate list so users can add plugins without touching the protected core list.
- **Error seen:** none.

---

## 4. `tasks/config.yml` and `templates/cockpit.conf.j2`

```yaml
- name: Deploy /etc/cockpit/cockpit.conf configuration template
  ansible.builtin.template:
    src: cockpit.conf.j2
    dest: /etc/cockpit/cockpit.conf
    owner: root
    group: root
    mode: "0644"
  notify: Restart cockpit.socket
```
- **What:** renders the template to `/etc/cockpit/cockpit.conf`, owner `root:root`, mode `0644` (owner read/write, everyone else read-only), and restarts `cockpit.socket` only when the file changed.
- **Only when** `rhel_cockpit_manage_config` is true.

The whole file:
```ini
[Session]
IdleTimeout = {{ rhel_cockpit_idle_timeout }}
```
- **`[Session]`:** the section Cockpit reads for session behaviour.
- **`IdleTimeout = 15`:** a web console session is logged out after 15 minutes without activity (minutes; `0` disables). Cockpit has **no** idle timeout unless this is set. Applies to the Cockpit web page only; it does not affect SSH (SSH idle handling is a separate CIS setting, `TMOUT` / `ClientAlive*`).
- **Why:** CIS requires idle administrative sessions to be terminated.
- **Deliberately not set:** port (cannot be set in `cockpit.conf`; it comes from `cockpit.socket`, default 9090), login banner, `AllowUnencrypted` (default is already `false`), root login (Cockpit's default keeps `root` in `/etc/cockpit/disallowed-users`; log in as an admin user such as `frqadmin`).
- **Error seen:** none. An earlier version wrote options Cockpit ignores (`Port`, a text `Banner`, a `[WebService]` `IdleTimeout`); they were removed after checking `man cockpit.conf` (orchestrator lessons item 14).

---

## 5. `tasks/service.yml`

```yaml
- name: Enable and start Cockpit systemd socket
  ansible.builtin.systemd_service:
    name: cockpit.socket
    enabled: true
    state: started
```
- **What:** `enabled: true` starts the socket at every boot; `state: started` starts it now.
- **Why the socket, not the service:** `cockpit.socket` listens on TCP 9090 and starts the web daemon only when someone connects, so an unused console uses no memory. The unit is not enabled by default after installation, so the role has to enable it.
- **Error seen:** none.

---

## 6. `tasks/firewall.yml`

```yaml
- name: Gather system service facts
  ansible.builtin.service_facts:
```
- **What:** reads the state of all systemd services into `ansible_facts.services`.
- **Why:** used by the next task to find out whether `firewalld` is running, without calling a shell command.

```yaml
- name: Permit Cockpit service through firewalld
  ansible.posix.firewalld:
    service: cockpit
    zone: "{{ rhel_cockpit_firewall_zone }}"
    permanent: true
    immediate: true
    state: enabled
  when:
    - "'firewalld.service' in ansible_facts.services"
    - "ansible_facts.services['firewalld.service']['state'] == 'running'"
```
- **What:** allows the predefined `cockpit` service (TCP 9090) in zone `public` (`rhel_cockpit_firewall_zone`).
  - `permanent: true`: written to the saved configuration, survives reboot.
  - `immediate: true`: also applied to the running firewall now, so no reload is needed.
- **`when`:** only if firewalld is installed and running. The firewalld module fails when the service is not running; this skips cleanly instead. `service_facts` reads systemd directly, so no `command: systemctl ...` is needed.
- **Why:** CIS hardening uses a strict firewall. Opening the service explicitly means the console is reachable regardless of how the base image was set up.
- **Reachability check:** from another VM, `https://192.168.20.30:9090` opens after the play and CIS.
- **Not verified:** whether the default `public` zone on RHEL already allows `cockpit`, in which case this task changes nothing. To check on a fresh host: `firewall-cmd --permanent --zone=public --list-services`.
- **Error seen:** none.

---

## 7. Supporting files

### `handlers/main.yml`
```yaml
- name: Restart cockpit.socket
  ansible.builtin.systemd_service:
    name: cockpit.socket
    state: restarted
```
- **What/Why:** runs only when `cockpit.conf` changed (notified by `config.yml`), so a new session starts from the new file. Not verified whether the restart is strictly required for Cockpit to pick up the change.

### `defaults/main.yml` (what users may override)
| Variable | Default | Meaning |
| :--- | :--- | :--- |
| `rhel_cockpit_extra_packages` | `[]` | extra Cockpit plugins |
| `rhel_cockpit_manage_firewall` | `true` | run `firewall.yml` |
| `rhel_cockpit_firewall_zone` | `public` | zone that gets the `cockpit` service |
| `rhel_cockpit_manage_config` | `true` | run `config.yml` |
| `rhel_cockpit_idle_timeout` | `15` | idle timeout in minutes (CIS) |

### `vars/main.yml`
`cockpit_packages`: the five mandatory packages (see section 3).

### `meta/main.yml`
Galaxy metadata (author, platforms EL 9/10, `min_ansible_version` 2.15) and required collections `ansible.posix` (firewalld module) and `community.general`.

---

## Review notes: points a reviewer may question

1. **`cockpit_packages` has no `rhel_cockpit_` prefix.** `ansible-lint` flags it (`var-naming[no-role-prefix]`). Renaming is a two-file change.
2. **`community.general` in `meta/main.yml`:** no task in this role uses it (only `ansible.builtin` and `ansible.posix.firewalld`).
3. **Firewall task may be a no-op** on a stock RHEL host (see section 6).
4. **`Restart cockpit.socket` handler:** restarting the socket does not necessarily restart a running `cockpit-ws` process; see the note in section 7.
5. **Cockpit and libvirt state:** on one test VM, the Cockpit machines page showed libvirt as not active while `libvirtd` was active. A reboot of the VM cleared it; the cause was not traced. This is a Cockpit/`libvirt-dbus` connection matter, not something a task in this role controls.
