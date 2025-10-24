#!/bin/bash
set -e # Exit immediately if a command exits with a non-zero status.
set -u # Treat unset variables as an error when substituting.

# --- Configuration ---
# IMPORTANT: Change this to your actual local network CIDR.
LOCAL_NETWORK="192.168.2.0/24"

# Define the ports needed for the HashiStack services.
TCP_PORTS=(9000 9001)
UDP_PORTS=()
TCP_UDP_PORTS=() # Ports that need both TCP and UDP

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
