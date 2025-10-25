# README

## Setup for *every node*

The following setup needs to be executed on every node, *before* running ansible commands.

### Create SSH keys

1. Run `just ssh_keygen`. This will generate keys in /home/vscode/workspace.
2. Copy them to all your nodes:

```shell
# Example
ssh-copy-id -i ${HOME}/workspace/.ssh/id_rsa.pub localstack@192.168.2.31
```

3. Log into the device:

```shell
ssh localstack@192.168.2.31
```

4. Modify ssh config:

```shell
# Should contain
# PubkeyAuthentication yes
# PasswordAuthentication no
# ChallengeResponseAuthentication no
# UsePAM no
sudo nano /etc/ssh/sshd_config
```

5. Restart service

```shell
sudo systemctl restart ssh
```

6. Test

```shell
ssh -i /home/vscode/workspace/.ssh/id_rsa localstack@192.168.2.31
```

### Enable passwordless `sudo`

1. Create new sudoers file:

```shell
# This command uses your current sudo password one last time
# For different users: replace 'localstack'
sudo visudo -f /etc/sudoers.d/90-localstack-nopasswd
```

2. Paste the following:

```shell
# NB: mind the user
localstack ALL=(ALL) NOPASSWD: ALL
```

3. Verify:

```shell
sudo ls -l /etc/sudoers.d/
```

4. Test:

```shell
sudo whoami
```
