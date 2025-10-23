### **Technical Documentation: A Definitive Guide to Bootstrapping the HashiStack**

#### **1. Overview**

This document provides a comprehensive, step-by-step procedure for deploying and securing a complete HashiCorp stack (Consul, Vault, Nomad) on a single Linux server node. The final environment will be a hardened, production-ready control plane suitable for a hobby cluster or development environment.

**Core Architecture & Principles:**

*   **Centralized Control Plane:** A single server node runs the Consul, Vault, and Nomad server agents.
*   **APT-Managed Installation:** All software is installed via the official HashiCorp APT repository for seamless integration, automatic user creation, and `systemd` service management.
*   **Deny-by-Default Security:** The network is secured with UFW, and all HashiCorp services are configured with Access Control Lists (ACLs) enabled and a default-deny policy.
*   **Principle of Least Privilege:** All inter-service communication is authenticated using dedicated, low-privilege tokens. The highly privileged bootstrap tokens are used only for initial setup.
*   **Automation:** A bootstrap script automates the initial server setup, including software installation and firewall configuration.

---

### **Part 2: Server Bootstrap (Automated)**

This script prepares the server by installing all necessary software and configuring the firewall.

**Instructions:**
1.  Save the following code to a file named `bootstrap-server.sh` on your main server node.
2.  **CRITICAL:** Edit the `LOCAL_NETWORK` variable in the script to match your local network's CIDR.
3.  Make the script executable: `chmod +x bootstrap-server.sh`.
4.  Run the script with `sudo`: `sudo ./bootstrap-server.sh`.

**File: `bootstrap-server.sh`**
```bash
#!/bin/bash
set -e
set -u

# --- Configuration ---
# IMPORTANT: Change this to your actual local network CIDR.
LOCAL_NETWORK="192.168.2.0/24"
# --- End Configuration ---

echo "--- [Step 1/5] Installing Prerequisites ---"
apt-get update
apt-get install -y wget gpg ufw

echo "--- [Step 2/5] Adding HashiCorp APT Repository ---"
wget -O - https://apt.releases.hashicorp.com/gpg | gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(grep -oP '(?<=UBUNTU_CODENAME=).*' /etc/os-release || lsb_release -cs) main" | tee /etc/apt/sources.list.d/hashicorp.list

echo "--- [Step 3/5] Installing Consul, Vault, and Nomad ---"
apt-get update
apt-get install -y consul vault nomad

echo "--- [Step 4/5] Configuring Secure Firewall with UFW ---"
# Define HashiStack ports
TCP_PORTS=(8500 8300 8200 8201 4646 4647)
TCP_UDP_PORTS=(8301 8600 4648)

ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow from "${LOCAL_NETWORK}" to any port 22 proto tcp

for port in "${TCP_PORTS[@]}"; do
    ufw allow from "${LOCAL_NETWORK}" to any port "${port}" proto tcp
done
for port in "${TCP_UDP_PORTS[@]}"; do
    ufw allow from "${LOCAL_NETWORK}" to any port "${port}"
done

ufw enable

echo "--- [Step 5/5] Creating systemd Override for Consul ---"
mkdir -p /etc/systemd/system/consul.service.d
cat <<EOF > /etc/systemd/system/consul.service.d/override.conf
[Service]
Type=exec
EOF
systemctl daemon-reload

echo -e "\n✅ Server bootstrap complete. Firewall is active."
echo "Proceed with manual configuration of Consul, Vault, and Nomad."
ufw status
```

---

### **Part 3: Consul Configuration & ACL Bootstrap**

This procedure secures Consul. Execute these commands on the server.

**3.1. Create Initial Consul Configuration**
Create the file `/etc/consul.d/consul.hcl`. **Replace `<YOUR_STATIC_IP>`**.

```hcl
# /etc/consul.d/consul.hcl
datacenter = "localstack"
data_dir   = "/var/lib/consul"

bind_addr      = "0.0.0.0"
client_addr    = "0.0.0.0"
advertise_addr = "<STATIC_IP>"

# Use the modern, block-based syntax for server mode.
server = true
bootstrap_expect = 1

# Enable the Web UI.
ui_config {
  enabled = true
}

# Enable and configure the ACL system itself.
acl {
  enabled                  = true
  default_policy           = "deny"
  enable_token_persistence = true
  #tokens {
  #  agent = "<AGENT_TOKEN>"
  #} # Uncomment after generating token
}
```

**3.2. Start Consul and Bootstrap ACLs**
```bash
sudo systemctl stop consul
sudo rm -rf /var/lib/consul/*
sudo systemctl start consul
sleep 5
```
In a **new terminal**, run the bootstrap command.
```bash
consul acl bootstrap
```
**CRITICAL:** Save the **`SecretID`**. This is your **Consul Bootstrap Token**.

**3.3. Create Consul Agent Token**
*   Set your environment variable to authenticate:
    ```bash
    export CONSUL_HTTP_TOKEN="<Your-Consul-Bootstrap-SecretID>"
    ```
*   Create the agent policy file, `agent-policy.hcl`:
    ```hcl
    agent_prefix "" { policy = "write" }
    node_prefix "" { policy = "write" }
    ```
*   Apply the policy and create the agent token:
    ```bash
    consul acl policy create -name "agent-policy" -rules @agent-policy.hcl
    consul acl token create -description "Token for Consul Agent" -policy-name "agent-policy"
    ```
**CRITICAL:** Save the **`SecretID`**. This is your **Consul Agent Token**.

**3.4. Finalize Consul Configuration**
*   Edit `/etc/consul.d/consul.hcl` and add the `tokens` block **inside** the `acl` block:
    ```hcl
    # ... inside the acl { ... } block
    tokens {
      agent = "<Your-Consul-Agent-Token-SecretID>"
    }
    ```
*   Restart Consul for the final time. It will now start quickly and be fully secured.
    ```bash
    sudo systemctl restart consul
    ```

---

### **Part 4: Vault Configuration & Initialization**

This procedure configures Vault to use the secure Consul backend.

**4.1. Create Consul Token for Vault**
*   Create `vault-policy.hcl`:
    ```hcl
    key_prefix "vault/" { policy = "write" }
    service "vault" { policy = "write" }
    agent_prefix "" { policy = "write" }
    session_prefix "" { policy = "write" }
    node_prefix "" { policy = "read" }
    ```
*   Apply the policy and create the token:
    ```bash
    consul acl policy create -name "vault-policy" -rules @vault-policy.hcl
    consul acl token create -description "Token for Vault" -policy-name "vault-policy"
    ```
**CRITICAL:** Save the **`SecretID`**. This is the **Consul Token for Vault**.

**4.2. Create Vault Configuration**
Create the file `/etc/vault.d/vault.hcl`. **Replace placeholders.**
```hcl
# /etc/vault.d/vault.hcl
ui = true
storage "consul" {
  address = "127.0.0.1:8500"
  path    = "vault/"
  token   = "<Your-Vault-Consul-Token-SecretID>"
}
listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_disable = true
}
api_addr     = "http://<YOUR_STATIC_IP>:8200"
cluster_addr = "http://<YOUR_STATIC_IP>:8201"
```

**4.3. Start and Initialize Vault**
```bash
sudo systemctl start vault
export VAULT_ADDR="http://127.0.0.1:8200"
vault operator init
```
**CRITICAL:** Save the **Unseal Keys** and **Initial Root Token**. Unseal the Vault with 3 keys, then run `vault login <Your-Vault-Root-Token>`.

---

### **Part 5: Nomad Configuration & ACL Bootstrap**

This procedure configures Nomad to integrate with Consul and Vault, then secures Nomad itself.

**5.1. Create Consul Token for Nomad**
*   Create `nomad-policy.hcl`:
    ```hcl
    node_prefix "" { policy = "write" }
    service_prefix "" { policy = "write" }
    agent_prefix "" { policy = "write" }
    session_prefix "" { policy = "write" }
    key_prefix "" { policy = "write" }
    operator = "read"
    ```
*   Apply policy and create token:
    ```bash
    consul acl policy create -name "nomad-policy" -rules @nomad-policy.hcl
    consul acl token create -description "Token for Nomad" -policy-name "nomad-policy"
    ```
**CRITICAL:** Save the **`SecretID`**. This is the **Consul Token for Nomad**.

**5.2. Create Limited Vault Token for Nomad**
*   Create `nomad-vault-policy.hcl`:
    ```hcl
    path "auth/token/create" { capabilities = ["update"] }
    path "auth/token/lookup-accessor" { capabilities = ["update"] }
    path "auth/token/revoke-accessor" { capabilities = ["update"] }
    ```
*   Write policy and create token:
    ```bash
    vault policy write nomad-server nomad-vault-policy.hcl
    vault token create -policy="nomad-server" -description="Token for Nomad Server"
    ```
**CRITICAL:** Save the **`token`** value from the output. This is the **limited Vault Token for Nomad**.

**5.3. Create Nomad Configuration**
Create `/etc/nomad.d/nomad.hcl`. **Replace placeholders.**
```hcl
# /etc/nomad.d/nomad.hcl
datacenter = "localstack"
data_dir   = "/var/lib/nomad"
bind_addr  = "0.0.0.0"

server {
  enabled          = true
  bootstrap_expect = 1
}
client {
  enabled = true
}
acl {
  enabled = true
}
consul {
  address = "127.0.0.1:8500"
  token   = "<Your-Nomad-Consul-Token-SecretID>"
}
vault {
  enabled = true
  address = "http://127.0.0.1:8200"
  token   = "<Your-LIMITED-Vault-Token-for-Nomad>"
}
```

**5.4. Start Nomad and Bootstrap ACLs**
```bash
sudo systemctl start nomad
sleep 5
nomad acl bootstrap
```
**CRITICAL:** Save the **`Secret ID`**. This is your **Nomad Bootstrap Token**.

---

### **Part 6: Operator & Client Configuration (Mac)**

This secures your day-to-day workflow by creating a lower-privileged developer token.

**6.1. Create Nomad Developer Policy**
*   Create `developer-policy.hcl`:
    ```hcl
    job { policy = "write" }
    allocation { policy = "read" }
    node { policy = "read" }
    agent { policy = "read" }
    operator { policy = "read" }
    acl { policy = "deny" }
    ```
*   Authenticate with your Nomad Bootstrap Token: `export NOMAD_TOKEN="<Nomad-Bootstrap-SecretID>"`.
*   Apply the policy:
    ```bash
    nomad acl policy apply -description "Policy for cluster-wide development" developer-policy developer-policy.hcl
    ```

**6.2. Create Nomad Developer Token**
```bash
nomad acl token create -name="dev-token-macbook" -policy="developer-policy"
```
**CRITICAL:** Save the **`Secret ID`**. This is your **Nomad Developer Token**.

**6.3. Configure Mac Environment**
*   Install the Nomad CLI on your Mac: `brew install nomad`.
*   Edit your shell profile (`~/.zshrc` or `~/.bash_profile`) and add the following lines, replacing the placeholders with your server's address and your **new developer token**:
    ```bash
    export NOMAD_ADDR="http://<YOUR_STATIC_IP>:4646"
    export NOMAD_TOKEN="<Your-Nomad-DEVELOPER-SecretID>"
    ```
*   Reload your shell: `source ~/.zshrc`.

---

### **Part 7: Final Verification and Example Job**

1.  **Enable all services to start on boot:**
    ```bash
    sudo systemctl enable consul vault nomad
    ```

2.  **Verify Cluster Status from your Mac:**
    ```bash
    # Set your CONSUL_HTTP_TOKEN to the bootstrap token to run this command
    consul members
    # Set your VAULT_TOKEN to the root token to run this command
    vault status
    # This uses your developer token
    nomad node status
    ```

3.  **Deploy an Example Job:** Create `example.nomad.hcl` on your Mac.
    ```hcl
    job "example" {
      datacenters = ["home-dc"]
      group "web" {
        count = 1
        network { port "http" { to = 80 } }
        task "nginx" {
          driver = "docker"
          config {
            image = "nginx:latest"
            ports = ["http"]
          }
          service {
            name = "example-nginx"
            port = "http"
            check {
              type     = "http"
              path     = "/"
              interval = "10s"
              timeout  = "2s"
            }
          }
        }
      }
    }
    ```
4.  Run the job: `nomad job run example.nomad.hcl`.
5.  Check its status: `nomad job status example`.

The cluster is now fully operational, secure, and ready for use.