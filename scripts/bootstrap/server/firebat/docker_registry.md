## Deploying a Secure Docker Registry with Podman-Compose and Systemd

### 1. Overview

This document provides step-by-step instructions for deploying a local, password-protected Docker registry and a web-based user interface. This guide uses Podman and `podman-compose` for container management and `systemd` to ensure the services automatically start on boot.

The final setup will consist of two rootless containers:
*   **Docker Registry (`registry:3`):** The core service for storing Docker images.
*   **Registry UI (`joxit/docker-registry-ui`):** A graphical interface for viewing and managing images in the registry.

Authentication is handled by the registry itself, and access can be restricted by IP address using UFW (Uncomplicated Firewall).

### 2. Prerequisites

Before you begin, ensure the following components are installed on your Linux system:

*   **Podman:** The daemonless container engine.
*   **`podman-compose`:** A script to run `docker-compose.yml` files with Podman. (`pip install podman-compose`)
*   **`apache2-utils` (Debian/Ubuntu) or `httpd-tools` (RHEL/CentOS):** Required to generate the password file using the `htpasswd` utility.

```bash
# For Debian/Ubuntu
sudo apt-get update && sudo apt-get install -y podman podman-compose apache2-utils

# For RHEL/CentOS
sudo dnf install -y podman podman-compose httpd-tools
```

### 3. Step-by-Step Instructions

#### Step 3.1: Project Directory and Authentication Setup

First, create a dedicated directory to hold your configuration, registry data, and authentication files.

```bash
# Create the main directory and subdirectories
mkdir local-registry
cd local-registry
mkdir -p data auth
```

Next, create an `htpasswd` file to store the username and password for your registry. You will be prompted to create a password for the specified user.

```bash
# Replace 'your_username' with your desired username
htpasswd -Bc auth/htpasswd your_username
```

#### Step 3.2: Create the Podman-Compose Configuration File

Create a file named `docker-compose.yml` inside the `local-registry` directory. Paste the following content into the file. This configuration uses fully-qualified image names to avoid ambiguity with Podman.

```yaml
version: '3.8'

services:
  registry:
    image: docker.io/library/registry:3
    container_name: local-docker-registry
    restart: always
    ports:
      - "5000:5000"
    environment:
      REGISTRY_AUTH: htpasswd
      REGISTRY_AUTH_HTPASSWD_REALM: Registry Realm
      REGISTRY_AUTH_HTPASSWD_PATH: /auth/htpasswd
      REGISTRY_STORAGE_DELETE_ENABLED: "true"
    volumes:
      - ./data:/var/lib/registry
      - ./auth:/auth
    networks:
      - registry-net

  registry-ui:
    image: docker.io/joxit/docker-registry-ui:main
    container_name: local-docker-registry-ui
    restart: always
    ports:
      - "8080:80"
    environment:
      SINGLE_REGISTRY: "true"
      REGISTRY_TITLE: "Local Docker Registry"
      NGINX_PROXY_PASS_URL: http://registry:5000
      DELETE_IMAGES: "true"
      SHOW_CONTENT_DIGEST: "true"
    depends_on:
      - registry
    networks:
      - registry-net

networks:
  registry-net:
    driver: bridge
```

#### Step 3.3: Configure Firewall Rules (UFW)

For security, configure the firewall to allow access to the registry (port `5000`) and the UI (port `8080`) only from a trusted IP range.

Replace `192.168.2.0/24` with your specific local network range.

```bash
# Allow SSH access so you don't lock yourself out
sudo ufw allow ssh

# Allow traffic from your local network to the registry and UI ports
sudo ufw allow from 192.168.2.0/24 to any port 5000 proto tcp
sudo ufw allow from 192.168.2.0/24 to any port 8080 proto tcp

# Enable the firewall
sudo ufw enable

# Verify the rules are in place
sudo ufw status
```
The output should confirm that access to ports 5000 and 8080 is allowed from your specified source.

#### Step 3.4: Manual Deployment and Verification

Before automating the service, start it manually to ensure everything works correctly.

```bash
# From within the local-registry directory
podman-compose up -d
```

Check that both containers are running without errors:
```bash
podman ps
```
You should see `local-docker-registry` and `local-docker-registry-ui` in the running container list.

*   Access the UI at: `http://<your-server-ip>:8080`
*   Your registry endpoint is: `<your-server-ip>:5000`

Log in to the UI using the credentials you created in Step 3.1.

#### Step 3.5: Create a Systemd User Service for Automatic Startup

To ensure the registry starts on boot, create a `systemd` user service.

1.  **Enable Lingering for your User**
    This critical step allows your user's services to run even when you are not logged in.
    ```bash
    loginctl enable-linger $(whoami)
    ```

2.  **Find the Full Path to `podman-compose`**
    Systemd requires absolute paths for executables.
    ```bash
    which podman-compose
    ```
    Note the output, which will typically be `/usr/bin/podman-compose` or `/usr/local/bin/podman-compose`.

3.  **Create the Service File**
    ```bash
    mkdir -p ~/.config/systemd/user
    nano ~/.config/systemd/user/local-registry.service
    ```

4.  **Add the Service Configuration**
    Paste the following content into the file. **Carefully replace the `WorkingDirectory` and the paths in `ExecStart`/`ExecStop` with your specific paths.**

    ```ini
    [Unit]
    Description=Podman Compose service for Local Docker Registry
    After=network-online.target
    Wants=network-online.target

    [Service]
    Type=oneshot
    RemainAfterExit=yes

    # --- EDIT BELOW ---
    # Replace with the absolute path to your project directory
    WorkingDirectory=/home/your_username/local-registry

    # Replace with the absolute path from the 'which podman-compose' command
    ExecStart=/usr/bin/podman-compose up -d
    ExecStop=/usr/bin/podman-compose down
    # --- EDIT ABOVE ---

    Restart=on-failure

    [Install]
    WantedBy=default.target
    ```

5.  **Enable and Start the Service**
    First, stop the manually started containers.
    ```bash
    # From within the local-registry directory
    podman-compose down
    ```

    Now, enable and start the service with `systemctl`:
    ```bash
    # Reload the systemd daemon to recognize the new file
    systemctl --user daemon-reload

    # Enable the service to start at boot
    systemctl --user enable local-registry.service

    # Start the service now
    systemctl --user start local-registry.service

    # Check the status to ensure it's active and running
    systemctl --user status local-registry.service
    ```

### 4. Conclusion

Your local Docker registry is now fully deployed. It is secured with a password, firewalled to your local network, and configured to launch automatically on system startup using a rootless `systemd` service.
