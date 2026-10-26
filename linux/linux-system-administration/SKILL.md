---
name: linux-system-administration
description: SSH failures, service mgmt, user creation, shell config.
tags: [linux, ssh, systemd, useradd, bash, sh]
author: curator
---

# Linux System Administration

## When to Use

- SSH connection errors (No route to host, Connection refused, timeout)
- systemd service management (start, enable, list, troubleshoot)
- User creation with proper home directory setup
- Shell switching (sh vs bash, source vs `.`)
- Service name confusion across distros (ssh vs sshd)

## SSH Troubleshooting

### Diagnose SSH failures by error message

| Error | Cause | Fix |
|-------|-------|-----|
| `No route to host` | Network layer unreachable (wrong IP, no route, firewall DROP) | Check IP is correct; `ip route get <ip>`; `ping <ip>` |
| `Connection refused` | Host reachable but sshd not listening on port 22 | Install/start sshd on remote |
| `Connection timed out` | Firewall silently dropping packets or host down | Check firewall rules, verify host is up |
| `Permission denied` | Auth failure (wrong password/key) | Check credentials, key permissions |
| `Host key verification failed` | Remote host key changed | `ssh-keygen -R <host>` to clear old key |

**Key distinction**: `No route to host` = network problem; `Connection refused` = service problem (sshd down). Always `ping` first to separate network from service issues.

### Service name: ssh vs sshd

- Ubuntu/Debian: service is called **`ssh`** (not `sshd`)
- CentOS/RHEL: service is called **`sshd`**

```bash
# Check which exists
systemctl list-unit-files | grep ssh

# Ubuntu/Debian
sudo systemctl enable --now ssh

# CentOS/RHEL
sudo systemctl enable --now sshd
```

### Install sshd

```bash
# Ubuntu/Debian
sudo apt update && sudo apt install -y openssh-server

# CentOS/RHEL
sudo yum install -y openssh-server
```

## User Management

### useradd pitfalls

```bash
# WRONG — no home directory created
sudo useradd username

# RIGHT — -m creates home directory
sudo useradd -m username

# Set password
sudo passwd username

# If home dir was missed, fix manually:
sudo mkdir /home/username
sudo chown username:username /home/username
```

### su vs su -

```bash
su username    # Switches user but stays in current dir, uses sh
su - username  # Switches user, cd to home, loads login shell (bash)
```

Always use `su - username` for a proper login session.

## Shell Configuration

### source not found in sh

`source` is a **bash built-in**. `sh` (dash) does not have it. Use `.` instead:

```bash
# In sh/dash:
. .bashrc

# In bash:
source .bashrc
# or
. .bashrc
```

### Change default shell

```bash
sudo chsh -s /bin/bash username
# or
sudo usermod -s /bin/bash username
```

After changing, `su - username` will use bash automatically.

## Service Management

### List all services

```bash
# All services (loaded units)
systemctl list-units --type=service --all

# Only running
systemctl list-units --type=service --state=running

# All installed (including disabled)
systemctl list-unit-files --type=service
```

### Common pitfall: service name mismatch

Distro patches rename services. If `systemctl start X` says "not found", search for it:

```bash
systemctl list-unit-files | grep <keyword>
```