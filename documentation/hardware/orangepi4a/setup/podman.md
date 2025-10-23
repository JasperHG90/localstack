Here is a summary of the troubleshooting steps in a technical documentation format.

---

### **Technical Documentation: Configuring Rootless Podman on Debian-based Systems**

#### 1. Overview

When setting up Podman in rootless mode on a fresh Debian-based system (such as Armbian on an Orange Pi), users may encounter errors related to user namespace mapping and storage driver configuration. This document outlines the symptoms and provides the step-by-step resolution for two common errors.

---

#### 2. Problem 1: `newuidmap` Executable Not Found

##### Symptom

When running a Podman command as a non-root user (e.g., `podman ps`), the operation fails with the following error:

```
Error: command required for rootless mode with multiple IDs: exec: "newuidmap": executable file not found in $PATH
```

##### Cause

Rootless Podman utilizes user namespaces to map a range of UIDs and GIDs from the host to the container. This allows a user to have administrative privileges *inside* the container without having them on the host. The `newuidmap` and `newgidmap` utilities are required to manage these mappings. This error indicates that the package providing these tools is not installed.

##### Resolution

Install the `uidmap` package, which contains the required utilities.

```bash
sudo apt update
sudo apt install uidmap
```
After installation, you may need to log out and log back in for the system to recognize the new executables in the user's PATH.

---

#### 3. Problem 2: Graph Driver Fallback to `vfs`

##### Symptom

After resolving the `newuidmap` issue, Podman commands may execute but display a recurring error message. The `podman info` command confirms that an inefficient storage driver is in use.

**Error Message:**
```
ERRO[0000] User-selected graph driver "overlay" overwritten by graph driver "vfs" from database - delete libpod local files to resolve
```

**Verification Command:**
```bash
podman info | grep graphDriverName
```

**Verification Output:**
```
  graphDriverName: vfs
```

##### Cause

Podman defaults to the `overlay` (or `overlay2`) storage driver, which is highly efficient for managing container image layers. This driver depends on the `overlayfs` filesystem. If the host kernel does not have `overlayfs` support built-in (common on some single-board computer kernels), Podman falls back to the `vfs` (Virtual File System) storage driver.

The `vfs` driver is a compatibility fallback that has significant performance and disk space disadvantages, as it copies data between layers instead of linking them.

For rootless mode, Podman can use a FUSE-based implementation of `overlayfs` as an alternative. The error occurs because this FUSE implementation is not installed.

##### Resolution

Install the `fuse-overlayfs` package and reset the Podman storage configuration to force it to detect and use the newly available driver.

**Step 1: Install `fuse-overlayfs`**

```bash
sudo apt update
sudo apt install fuse-overlayfs
```

**Step 2: Reset Podman Storage**

This command will destroy all existing Podman containers, images, and volumes. Back up any critical data before proceeding.

```bash
podman system reset
```
Confirm the operation when prompted.

---

#### 4. Verification

After completing the resolutions, verify that Podman is functioning correctly and using the `overlay` storage driver.

1.  Run a Podman command; it should execute without any errors.
    ```bash
    podman ps
    ```
    **Expected Output:**
    ```
    CONTAINER ID  IMAGE       COMMAND     CREATED     STATUS      PORTS       NAMES
    ```

2.  Check the storage driver in use.
    ```bash
    podman info | grep graphDriverName
    ```
    **Expected Output:**
    ```
      graphDriverName: overlay
    ```

The system is now correctly configured for efficient and error-free rootless Podman operation.