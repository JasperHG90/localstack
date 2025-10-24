# Compile RISCV Minio docker image

This will build the minio and mc docker images and pushes them to the local docker registry. Minio does not provide risv64 architecture docker images so we need to do this ourselves.

Clone minio repository

1. `just clone`

Log into docker registry

2. `just docker_login`

Build and push to registry

3. `just push`

## Minio setup on Orange PI Rv2 (RISCV64)

This document outlines the end-to-end process for creating a robust, auto-starting MinIO object storage server on a Raspberry Pi 4B. It uses an external USB drive for storage and leverages Podman with a Quadlet systemd service for modern, reliable container management.

**Prerequisites:**
*   A Raspberry Pi 4B (or newer) running Raspberry Pi OS (or another Debian-based Linux distribution).
*   Podman installed (`sudo apt install podman`).
*   An external USB SSD or HDD with a USB 3.0 enclosure.
*   The `pi` user (or your primary user) has been enabled for `linger` to allow services to run after logout (`loginctl enable-linger your_username`).

*   Ensure that your podman service is configured for insecure docker registries, and that minio is available on localstack.local:5000

---

### **Stage 1: Prepare the External Storage Drive**

This stage involves formatting the USB drive with a native Linux filesystem and configuring the system to mount it automatically and reliably on boot.

> [!NOTE]
> You can do this for multiple drives. The Qubelet config below assumes you're doing it for two drives.

1.  **Connect and Identify the Drive:**
    Connect the USB drive to one of the blue USB 3.0 ports on the Raspberry Pi. Open a terminal and list the block devices to find its identifier.
    ```bash
    lsblk
    ```
    Look for a device like `/dev/sda` with a partition like `/dev/sda1`. This partition identifier (e.g., `/dev/sda1`) will be used in the next step.

2.  **Format the Drive:**
    **WARNING:** This step will permanently erase all data on the drive.
    Format the partition with the `ext4` filesystem. Using a label is recommended for easy identification.
    ```bash
    sudo mkfs.ext4 -L minio-data /dev/sda1
    ```

3.  **Create a Mount Point:**
    Create a permanent directory on the Raspberry Pi's filesystem where the external drive will be mounted.
    ```bash
    sudo mkdir /mnt/minio-data
    ```

4.  **Configure Automatic Mounting (`fstab`):**
    To ensure the drive is mounted automatically every time the Pi boots, we will add it to the `/etc/fstab` file using its unique identifier (UUID).

    *   First, find the UUID of the newly formatted partition:
        ```bash
        sudo blkid
        ```
        Find the entry for `/dev/sda1` and copy its `UUID` value.

    *   Next, edit the `fstab` file:
        ```bash
        sudo nano /etc/fstab
        ```

    *   Add the following line to the end of the file, replacing `YOUR_UUID` with the value you just copied.
        ```
        UUID=YOUR_UUID /mnt/minio-data ext4 defaults,nofail 0 2
        ```
        The `nofail` option is critical; it prevents the Pi from failing to boot if the drive is not connected.

5.  **Mount and Set Permissions:**
    *   Mount all devices listed in `/etc/fstab` to apply the changes immediately.
        ```bash
        sudo mount -a
        ```
    *   Change the ownership of the mount point to your user (e.g., `pi`) so that your rootless Podman container can read and write to it.
        ```bash
        sudo chown -R localstack:localstack /mnt/minio-data
        ```

### **Stage 2: Create the MinIO Quadlet Service File**

Instead of running a manual `podman run` command, we will create a declarative Quadlet file. This allows `systemd` to manage the container's lifecycle.

1.  **Create the Quadlet Directory:**
    Quadlet files reside in a specific user directory. Create it if it doesn't exist.
    ```bash
    mkdir -p ~/.config/containers/systemd/
    ```

2.  **Create the `.container` File:**
    Using a text editor, create a file that defines the MinIO container.
    ```bash
    nano ~/.config/containers/systemd/minio.container
    ```

3.  **Populate the File:**
    Copy and paste the following content into the file. **Replace the placeholder credentials with your own secure username and password.**

```ini
# ~/.config/systemd/user/minio.container
#
# Quadlet definition for a rootless MinIO server container

[Unit]
Description=MinIO Object Storage Container
# Start after the network is available
After=network-online.target

[Container]
# The name of the container
ContainerName=minio-server

# The image to pull
Image=localstack.local:5000/minio

# Map the host's SSD mount point to the container's data directory
# The :Z tells Podman to handle SELinux labels, which is good practice.
Volume=/mnt/minio-data:/data:Z

# Set environment variables for credentials
Environment=MINIO_ROOT_USER=minioadmin
Environment=MINIO_ROOT_PASSWORD=<REDACTED_MINIO_ROOT_PASSWORD>

# Map the ports
PublishPort=9000:9000
PublishPort=9001:9001

# The command to run inside the container
Exec=server /data --console-address :9001

[Service]
# Restart the container if it stops unexpectedly
Restart=on-failure

[Install]
# This makes the service start automatically on boot for the user
WantedBy=default.target
```

### **Stage 3: Enable and Run the Service

1.  **Reload the systemd Daemon:**
    This command makes `systemd` detect the new `minio.container` file and allows the Quadlet generator to create the service file in the background.
    ```bash
    systemctl --user daemon-reload

2.  **Start the service**
    ```bash
    systemctl --user start minio.service
    ```

### **Stage 4: Verification and Management**

Verify that the container is running correctly and that data is being stored on the external drive.

1.  **Check Service Status:**
    ```bash
    systemctl --user status minio.service
    ```
    Look for a green `active (running)` status. The output should also confirm the service is `enabled`.

2.  **Check the Podman Container:**
    ```bash
    podman ps
    ```
    You should see the `minio-server` container listed with a status of "Up".

3.  **Check the Data Directory:**
    Confirm that MinIO is writing its system files to your external drive.
    ```bash
    ls -l /mnt/minio-data
    ```
    You should see several directories created by MinIO, such as `.minio.sys/`.

4.  **Access the MinIO Web Console:**
    Open a web browser on another computer on the same network and navigate to:
    `http://<your-raspberry-pi-ip>:9001`
    Log in with the admin credentials you set in the `minio.container` file.

**Day-to-Day Management:**
*   **Stop the service:** `systemctl --user stop minio.service`
*   **Start the service:** `systemctl --user start minio.service`
*   **Restart the service:** `systemctl --user restart minio.service`
*   **View logs:** `podman logs minio-server`

Of course. Here is a new section, "Stage 5: User Management," written in the same technical documentation style. You can append this directly to the document created previously.

### **Stage 5: User Management with the MinIO Client (mc)**

The initial root user is created through the Quadlet service file. All subsequent users and permission policies must be managed using the MinIO Client (`mc`), a command-line tool that acts as the primary administration interface for your server.

This stage should be performed on the Raspberry Pi host system.

#### **1. Install the MinIO Client (`mc`)**

If `mc` is not already installed, download and prepare it.

*   **Download the ARM64 Binary:**
    ```bash
    wget https://dl.min.io/client/mc/release/linux-arm64/mc
    ```

*   **Make it Executable and Move to System Path:**
    ```bash
    chmod +x mc
    sudo mv mc /usr/local/bin/
    ```

#### **2. Configure an Admin Alias**

An alias is a stored connection profile. You must first configure an alias to connect to your MinIO server with your root/admin credentials.

*   **Set the Admin Alias:**
    This command creates a connection profile named `myminio`. Use the `MINIO_ROOT_USER` and `MINIO_ROOT_PASSWORD` credentials that are defined in your `minio.container` file.
    ```bash
    mc alias set myminio http://127.0.0.1:9000 YOURADMIN YOURSTRONGPASSWORD
    ```
    *   `myminio`: A convenient name for this connection.
    *   `http://127.0.0.1:9000`: The local API endpoint of your MinIO server.
    *   `YOURADMIN`/`YOURSTRONGPASSWORD`: Your root credentials.

*   **Verify the Connection:**
    Confirm that `mc` can communicate with the server as an administrator.
    ```bash
    mc admin info myminio
    ```
    This command should successfully return status information about your MinIO server instance.

#### **3. Create a New User**

New users are defined by an "Access Key" (their username) and a "Secret Key" (their password).

*   **Add the User:**
    Use the `mc admin user add` command, specifying the alias, a new access key, and a new secret key.
    ```bash
    # Syntax: mc admin user add <alias> <new_access_key> <new_secret_key>
    # Example:
    mc admin user add myminio data-scientist S3cur3P@ssw0rd2025
    ```
    Upon success, you will see the message: `Added user `data-scientist` successfully.`

#### **4. Attach a Policy to the User**

By default, a new user has no permissions. You must attach a policy to grant them access. MinIO provides several built-in policies for common use cases.

*   **Common Built-in Policies:**
    *   `readonly`: Allows downloading and listing.
    *   `readwrite`: Allows all S3 actions (listing, downloading, uploading, deleting).
    *   `writeonly`: Allows uploading but not reading/listing.

*   **Attach the `readwrite` Policy:**
    Use the `mc admin policy attach` command to grant the new user standard read-write permissions.
    ```bash
    # Syntax: mc admin policy attach <alias> <policy_name> --user <username>
    # Example:
    mc admin policy attach myminio readwrite --user data-scientist
    ```
    Upon success, you will see the message: `Policy `readwrite` is attached to user `data-scientist``

The new user `data-scientist` is now fully configured and can be used to connect to MinIO via the Web Console or any S3-compatible application using their new Access Key and Secret Key. Repeat steps 3 and 4 to create additional users with different permissions as needed.

### Step 6: write some data using duckdb

1. Create a new bucket called 'testbucket'
2. Install duckdb using uv `uv tool install duckdb`
3. Run `duckdb -ui`
4. Run the following script:

```sql
INSTALL httpfs;
LOAD httpfs;

SET s3_endpoint='minio.local:9000';
SET s3_url_style='path';
SET s3_access_key_id = 'duckdb';
SET s3_secret_access_key = 'KlMinf2IBy';
SET s3_use_ssl = false;

COPY (
  SELECT
      i AS event_id,
      'sensor_' || (i % 4 + 1)::VARCHAR AS sensor_id,
      (now() - INTERVAL (100 - i) MINUTE) AS event_timestamp,
      (random() * 100 + 20)::DECIMAL(5, 2) AS temperature_celsius
  FROM 
      generate_series(1, 100) AS t(i)
) TO 's3://testbucket/generated_sensor_data.parquet' (FORMAT 'PARQUET');

SELECT * FROM 's3://testbucket/generated_sensor_data.parquet' WHERE sensor_id='sensor_2'
```

### Step 7: shutting down the server gracefully

`sudo shutdown now`
