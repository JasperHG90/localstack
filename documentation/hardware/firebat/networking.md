### **Technical Documentation: Secure Firewall Setup with UFW**

#### **1. Overview**

This document provides the standard operating procedure for configuring a secure firewall on a Linux server using UFW (Uncomplicated Firewall).

The security model is **"Deny by Default, Allow by Exception"**:
1.  **Default Deny Incoming:** All unsolicited incoming network traffic is blocked by default.
2.  **Default Allow Outgoing:** The server is permitted to initiate connections to the outside world (e.g., for system updates).
3.  **Local Network Access Only:** Exceptions are made only for specific ports required by the HashiStack services (Consul, Vault, Nomad) and SSH. These ports will only be accessible from within the defined local network, preventing exposure to the public internet.

This configuration is ideal for a hobby cluster or a private development environment.

#### **2. Prerequisites**

*   A Debian or Ubuntu-based server with `sudo` privileges.
*   The `ufw` package installed (`sudo apt-get install ufw`).
*   Knowledge of your local network's CIDR address (e.g., `192.168.2.0/24`).

---

### **3. Bootstrap Script**

The following Bash script automates the entire firewall configuration. It resets the firewall to a clean state, sets the default policies, and adds the specific rules required for the HashiStack services and SSH, restricted to the local network.

**File:** `setup_firewall.sh`
```bash
#!/bin/bash
set -e # Exit immediately if a command exits with a non-zero status.
set -u # Treat unset variables as an error when substituting.

# --- Configuration ---
# IMPORTANT: Change this to your actual local network CIDR.
LOCAL_NETWORK="192.168.2.0/24"

# Define the ports needed for the HashiStack services.
TCP_PORTS=(8500 8300 8200 8201 4646 4647)
UDP_PORTS=(8301 8600 4648)
TCP_UDP_PORTS=(8301 8600 4648) # Ports that need both TCP and UDP

# --- Main Script ---
echo "🔥 Starting secure firewall configuration..."

# Reset UFW to a clean, disabled state. The --force flag prevents interactive prompts.
echo "🔄 Resetting UFW to default state..."
sudo ufw --force reset

# Set the default policies: Deny incoming, Allow outgoing.
echo "🛡️ Setting default policies: DENY incoming, ALLOW outgoing..."
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow SSH access ONLY from the local network. This is critical.
echo "🔑 Allowing SSH access from local network: ${LOCAL_NETWORK}"
sudo ufw allow from "${LOCAL_NETWORK}" to any port 22 proto tcp

# Add rules for the HashiStack TCP ports.
echo "➕ Adding HashiStack TCP port rules..."
for port in "${TCP_PORTS[@]}"; do
    echo "  -> Allowing TCP port ${port} from ${LOCAL_NETWORK}"
    sudo ufw allow from "${LOCAL_NETWORK}" to any port "${port}" proto tcp
done

# Add rules for the HashiStack TCP/UDP ports.
echo "➕ Adding HashiStack TCP/UDP port rules..."
for port in "${TCP_UDP_PORTS[@]}"; do
    echo "  -> Allowing TCP/UDP port ${port} from ${LOCAL_NETWORK}"
    sudo ufw allow from "${LOCAL_NETWORK}" to any port "${port}"
done

# Enable the firewall.
echo "🚀 Enabling the firewall..."
sudo ufw enable

# Display the final status.
echo -e "\n✅ Firewall setup complete. Final status:"
sudo ufw status verbose
```

#### **4. How to Use the Script**

1.  **Save the Script:** Copy the code above and save it to a file named `setup_firewall.sh` on your `localstack` server.

2.  **Make the Script Executable:**
    ```bash
    chmod +x setup_firewall.sh
    ```

3.  **Run with `sudo`:** Execute the script with `sudo` privileges.
    ```bash
    sudo ./setup_firewall.sh
    ```
    The script will print its progress and display the final `ufw status` output upon completion.

#### **5. Verification**

After the script runs, you can manually verify the configuration at any time.

```bash
sudo ufw status
```
The output should confirm that the firewall is active and that all `ALLOW` rules are restricted to your local network.

**Expected Output:**
```
Status: active

To                         Action      From
--                         ------      ----
22/tcp                     ALLOW       192.168.2.0/24
8500/tcp                   ALLOW       192.168.2.0/24
8300/tcp                   ALLOW       192.168.2.0/24
8200/tcp                   ALLOW       192.168.2.0/24
8201/tcp                   ALLOW       192.168.2.0/24
4646/tcp                   ALLOW       192.168.2.0/24
4647/tcp                   ALLOW       192.168.2.0/24
8301                       ALLOW       192.168.2.0/24
8600                       ALLOW       192.168.2.0/24
4648                       ALLOW       192.168.2.0/24
```

#### **6. Daily Management Operations**

*   **Check Status:** `sudo ufw status`
*   **Disable Firewall:** `sudo ufw disable`
*   **Delete a Specific Rule:** `sudo ufw delete allow from 192.168.2.0/24 to any port 4648`
*   **Rerun the Script:** If you need to restore the firewall to its known-good state, simply run the `setup_firewall.sh` script again.
