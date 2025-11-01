# Technical Guide: Migrating Orange Pi OS to a Bootable NVMe Drive

This guide provides a step-by-step procedure for migrating a live Orange Pi operating system from an SD card to an NVMe drive. This process dramatically improves system performance by leveraging the superior speed of NVMe storage.

### Prerequisites

*   An Orange Pi with an OS running on an SD card.
*   An NVMe drive installed and recognized by the system.
*   A backup of any critical data on both the SD card and the NVMe drive. **This process is destructive to the data on the NVMe drive.**
*   Terminal access to the Orange Pi with `sudo` privileges.

---

## Phase 1: System Identification and Preparation

Before starting, we need to identify the storage devices and prepare the NVMe drive.

### Step 1: Identify Your Devices

Use the `lsblk` command to list all block devices. This is crucial for identifying the source (SD card) and destination (NVMe).

```bash
lsblk
```

The output will look similar to this:
*   `mmcblk0`: Your SD card. The OS is likely on a partition like `mmcblk0p1`.
*   `nvme0n1`: Your NVMe drive.

### Step 2: Prepare the NVMe Drive

This step will erase the NVMe drive and create a new partition for the OS.

```bash
# 1. Unmount the NVMe drive if it's currently mounted
sudo umount /dev/nvme0n1p1

# 2. Open the drive with the fdisk partitioning tool
sudo fdisk /dev/nvme0n1

# 3. Inside fdisk, create a new partition table and a single partition:
#    - Press 'g' to create a new, empty GPT partition table.
#    - Press 'n' to create a new partition.
#    - Press Enter four times to accept the default values (Partition 1, full size).
#    - Press 'w' to write the changes to the disk and exit fdisk.

# 4. Format the new partition with the ext4 filesystem
sudo mkfs.ext4 /dev/nvme0n1p1
```

---

## Phase 2: OS Migration

Now we will clone the running OS from the SD card to the newly prepared NVMe drive.

### Step 1: Mount the New Partition

```bash
# 1. Create a temporary mount point
sudo mkdir -p /mnt/new_root

# 2. Mount the new NVMe partition at this location
sudo mount /dev/nvme0n1p1 /mnt/new_root
```

### Step 2: Clone the Filesystem

We will use `rsync` to perform a file-by-file copy, which preserves permissions, ownership, and symbolic links.

```bash
# This command copies the entire root filesystem to the new drive,
# excluding virtual and temporary filesystems that shouldn't be copied.
sudo rsync -aAXv --exclude={"/dev/*","/proc/*","/sys/*","/tmp/*","/run/*","/mnt/*","/media/*","/lost+found"} / /mnt/new_root
```
**Note:** This process can take a significant amount of time, depending on the size of your OS.

---

## Phase 3: Boot Configuration

This is the final and most critical phase. We will tell the Orange Pi's bootloader to use the OS on the NVMe drive.

### Step 1: Update the Filesystem Table (`fstab`)

We need to edit the `fstab` on the *new* NVMe drive so it knows where to find its own root partition upon booting.

```bash
# 1. Get the unique identifier (UUID) of the new NVMe partition
sudo blkid /dev/nvme0n1p1

#    Copy the full UUID value from the output (e.g., "xxxxxxxx-xxxx-...").

# 2. Edit the fstab file on the NVMe drive
sudo nano /mnt/new_root/etc/fstab

# 3. In the editor, find the line for the root mount point (/).
#    It will have the UUID of your old SD card. Replace that old UUID
#    with the new UUID of your NVMe partition that you just copied.
#    Save the file and exit (Ctrl+O, Enter, Ctrl+X).
```

### Step 2: Reconfigure the Bootloader

Now we edit the bootloader configuration on the **SD card** to point it to the new OS location.

```bash
# 1. Get the UUID of the NVMe partition again if you don't have it
sudo blkid /dev/nvme0n1p1

# 2. Edit the boot configuration file on the SD card's /boot directory
sudo nano /boot/orangepiEnv.txt

# 3. Find the line that starts with 'rootdev=UUID='.
#    Replace the existing UUID with the UUID of your NVMe partition.
#    The line should look like this:
#    rootdev=UUID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

# 4. Save the file and exit.
```

---

## Phase 4: Final Reboot and Verification

The migration is complete. Reboot the system to boot from the NVMe drive.

```bash
sudo reboot
```

After the system reboots, you can verify that the migration was successful by running `lsblk` again. The output should now show the root mount point (`/`) on your `nvme0n1p1` partition.

```bash
lsblk
```
Your system is now running on the high-speed NVMe drive.
