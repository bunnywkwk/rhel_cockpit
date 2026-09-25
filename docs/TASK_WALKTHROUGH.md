# rhel_cockpit: Task Walkthrough

Every task, in the order it runs: **what it does**, **why it is there**, and an **error seen** where a real error is related. "None seen" means the task never caused a failure. This role is small on purpose: it installs Cockpit, sets one CIS setting and starts the socket.

## Execution order

| # | File | Purpose |
| :- | :--- | :--- |
| 1 | `tasks/main.yml` | Runs the steps below in order |
| 2 | `tasks/preflight.yml` | Stops the run on an unsupported OS |
| 3 | `tasks/packages.yml` | Installs Cockpit and its plugins |
| 4 | `tasks/config.yml` | Writes `/etc/cockpit/cockpit.conf` (session idle timeout) |
| 5 | `tasks/service.yml` | Enables and starts `cockpit.socket` |

Big idea: **Cockpit is the web front end, `rhel_kvm` is the engine.** `cockpit-machines` shows and controls the VMs, but the VMs and networks live in libvirt, which `rhel_kvm` sets up. Run `rhel_kvm` first (the orchestrator does).

---

## Where each variable is used

Defaults are in `defaults/main.yml`, the package list is in `vars/main.yml`. Nothing is hidden: this is every place a variable is read.

| Variable | Read in | Effect |
| :--- | :--- | :--- |
| `cockpit_packages` | `tasks/packages.yml` | mandatory packages to install |
| `rhel_cockpit_extra_packages` | `tasks/packages.yml` | optional extra plugins; the task is skipped when the list is empty |
| `rhel_cockpit_idle_timeout` | `templates/cockpit.conf.j2` | value of `[Session] IdleTimeout` |

`tasks/main.yml` reads no variables of its own; everything is read inside the step files or the template.

---

## 1. `tasks/main.yml`

```yaml
- name: Run pre-flight OS validation
  ansible.builtin.include_tasks: preflight.yml
- name: Install Cockpit packages
  ansible.builtin.include_tasks: packages.yml
- name: Configure Cockpit session idle timeout
  ansible.builtin.include_tasks: config.yml
- name: Manage Cockpit systemd socket activation
  ansible.builtin.include_tasks: service.yml
```
- **What:** runs the step files in order. `main.yml` contains **no** variables and no conditions: every step always runs. The idle-timeout config is not optional because it is the CIS requirement the role exists for.
- **Why:** the order matters: packages first (they create `/etc/cockpit` and the `cockpit.socket` unit), config before the socket is started.
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
- **Why:** package names and paths are only known to match on these versions; failing early beats half-configuring another OS.
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
- **Error seen [#8]:** `Cannot find a valid baseurl for repo: epel` (a broken `epel.repo` stub left by the Zabbix role, unrelated to Cockpit; it fails any dnf task that refreshes the cache).
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
- Always runs (not switchable).

The whole file:
```ini
[Session]
IdleTimeout = {{ rhel_cockpit_idle_timeout }}
```
- **`[Session]`:** the section Cockpit reads for session behaviour.
- **`IdleTimeout = 15`:** a web console session is logged out after 15 minutes without activity (minutes; `0` disables). Cockpit has **no** idle timeout unless this is set. Applies to the Cockpit web page only; it does not affect SSH (SSH idle handling is a separate CIS setting, `TMOUT` / `ClientAlive*`).
- **Why:** CIS requires idle administrative sessions to be terminated.
- **Deliberately not set:** port (cannot be set in `cockpit.conf`; it comes from `cockpit.socket`, default 9090), login banner, `AllowUnencrypted` (default is already `false`), root login (Cockpit's default keeps `root` in `/etc/cockpit/disallowed-users`; log in as an admin user such as `frqadmin`).
- **Error seen:** none. An earlier version wrote options Cockpit ignores (`Port`, a text `Banner`, a `[WebService]` `IdleTimeout`); they were removed after checking `man cockpit.conf` (orchestrator lessons item 12).

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

## 6. Firewall: deliberately not managed

The role has no firewall task. Evidence:
- **Stock hosts already allow Cockpit.** On rollback-state hosts (before the role and before CIS), on both rhel9 and rhel10, `sudo firewall-cmd --permanent --zone=public --list-services` returns `cockpit dhcpv6-client ssh`. A task enabling the `cockpit` service would only report `ok`.
- **CIS does not remove it (read from the CIS role code):** RHEL 9 rule 4.2.1 only audits the zone and 4.2.2 adds loopback rich rules; RHEL 10 rule 4.1.4 sets the zone target (`DROP`), which applies to traffic that is not allowed, not to services that are. Nothing in either role removes a service from the zone.
- **Earlier version:** the role had a firewall task (`service_facts` + `ansible.posix.firewalld`, with a `Reload firewalld` handler). It was removed as redundant.
- **To confirm after the full play:** open `https://<host>:9090` from another machine (worked in earlier runs, which still had the task). If it ever fails after CIS, check `firewall-cmd --list-services` and add the task back.
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
| `rhel_cockpit_idle_timeout` | `15` | idle timeout in minutes (CIS) |

### `vars/main.yml`
`cockpit_packages`: the five mandatory packages (see section 3).

### `meta/main.yml`
Galaxy metadata (author, platforms EL 9/10, `min_ansible_version` 2.15). No collections are required: the role only uses `ansible.builtin` modules.

---

## Review notes: points a reviewer may question

1. **`cockpit_packages` has no `rhel_cockpit_` prefix.** `ansible-lint` flags it (`var-naming[no-role-prefix]`). Renaming is a two-file change.
2. **`Restart cockpit.socket` handler:** restarting the socket does not necessarily restart a running `cockpit-ws` process; see the note in section 7.
3. **Cockpit and libvirt state:** on one test VM, the Cockpit machines page showed libvirt as not active while `libvirtd` was active. A reboot of the VM cleared it; the cause was not traced. This is a Cockpit/`libvirt-dbus` connection matter, not something a task in this role controls.
