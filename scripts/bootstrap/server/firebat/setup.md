### 1. Assigning a .local Multicast DNS (mDNS) Address

This document outlines the procedure for configuring an Ubuntu device to use a `.local` domain name for network discovery using the Avahi daemon, which implements the Zeroconf protocol.

#### 1.1. Objective

To allow network clients to resolve the Ubuntu device's IP address using a human-readable hostname in the format `hostname.local` without a conventional DNS server.

#### 1.2. Prerequisites

*   An Ubuntu-based system.
*   Administrative (sudo) privileges.
*   Network connectivity.

#### 1.3. Required Packages

*   `avahi-daemon`: The system daemon that broadcasts and responds to mDNS queries.
*   `libnss-mdns`: A Name Service Switch (NSS) module that enables local resolution of `.local` hostnames.

#### 1.4. Configuration Steps

1.  **Install Avahi Services**

    Update the package index and install the required packages.
    ```bash
    sudo apt update
    sudo apt install avahi-daemon libnss-mdns
    ```
    The `avahi-daemon` service will start automatically upon installation.

2.  **Verify Hostname**

    The `.local` address is derived from the system's hostname. To check the current hostname, execute:
    ```bash
    hostnamectl
    ```
    If a change is required, set a new static hostname. For example, to set the hostname to `ubuntu-server`:
    ```bash
    sudo hostnamectl set-hostname ubuntu-server
    ```
    This change will make the device accessible at `ubuntu-server.local`.

3.  **Ensure NSS Configuration**

    The installation of `libnss-mdns` should automatically configure the Name Service Switch file (`/etc/nsswitch.conf`). Verify that the `hosts` line includes `mdns4_minimal` to enable mDNS lookups.
    ```bash
    cat /etc/nsswitch.conf | grep hosts
    ```
    The output should resemble the following:
    `hosts: files mdns4_minimal [NOTFOUND=return] dns`

4.  **Firewall Configuration (If Applicable)**

    If a firewall (e.g., UFW) is active, ensure it allows mDNS traffic on UDP port 5353.
    ```bash
    sudo ufw allow 5353/udp
    ```

#### 1.5. Verification

From a separate client on the same local network, use the `ping` utility to verify resolution of the `.local` address.
```bash
ping ubuntu-server.local
```
A successful reply indicates that the Avahi configuration is correct and the device is discoverable on the network.

***

### 2. Configuring Passwordless Sudo Access

This document describes the recommended method for granting a user the ability to execute commands with `sudo` privileges without being prompted for a password.

#### 2.1. Objective

To configure passwordless `sudo` for a specific user to streamline administrative tasks.

#### 2.2. Security Warning

Disabling the password prompt for `sudo` reduces the security of the system. This configuration should only be applied in trusted environments and for users who understand the implications. Unauthorized access to such a user account grants unrestricted root-level access to the system.

#### 2.3. Procedure

The standard and safest method is to add a custom configuration file to the `/etc/sudoers.d/` directory. This approach is modular and avoids direct modification of the main `/etc/sudoers` file.

1.  **Create a User-Specific Sudoers File**

    Use the `visudo` command to create and edit the configuration file. `visudo` locks the sudoers file and performs a syntax check before saving, preventing configuration errors that could lead to a loss of administrative access. Replace `username` with the actual target username.

    ```bash
    sudo visudo -f /etc/sudoers.d/90-nopasswd-username
    ```
    *Note: The filename must not contain a `.` or `~`.*

2.  **Add the NOPASSWD Rule**

    Inside the editor, add the following line. This rule specifies that the user can execute any command (`ALL`) as any user (`(ALL)`) on any host (`ALL`) without providing a password (`NOPASSWD`).

    ```
    username ALL=(ALL) NOPASSWD: ALL
    ```

3.  **Save and Exit**

    *   Press `Ctrl + X` to exit the nano editor.
    *   Press `Y` to confirm that you want to save the changes.
    *   Press `Enter` to write to the specified filename.

    `visudo` will validate the syntax. If no errors are found, the changes will be applied immediately.

#### 2.4. Verification

Log in as the specified user (or switch to their shell) and execute a `sudo` command.
```bash
sudo apt update
```The command should execute without a password prompt.
