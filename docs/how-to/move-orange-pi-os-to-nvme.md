---
description: Move a running Orange Pi's operating system from its SD card to an NVMe drive and point the bootloader at it.
stale_after: 2027-01-19
sources:
  - resource: bootstrap/inventory/cluster.ini
---

# How to move the Orange Pi OS to an NVMe drive

## Introduction

This moves a running Orange Pi's operating system from its SD card to an
NVMe drive, which is much faster. The SD card keeps the bootloader, and the
bootloader then loads the OS from the NVMe drive.

## Prerequisites

*   An Orange Pi with an OS running on an SD card.
*   An NVMe drive installed and recognized by the system.
*   A backup of any critical data on both the SD card and the NVMe drive.
    **This erases everything on the NVMe drive.**
*   Terminal access to the Orange Pi with `sudo` privileges.

## Directions

### Step 1: Identify your devices

List the block devices, to tell the source (SD card) from the destination
(NVMe):

```bash
lsblk
```

The output will look similar to this:
*   `mmcblk0`: Your SD card. The OS is likely on a partition like `mmcblk0p1`.
*   `nvme0n1`: Your NVMe drive.

### Step 2: Prepare the NVMe drive

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

### Step 3: Mount the new partition

Mount the new partition so the next step can copy the OS onto it.

```bash
# 1. Create a temporary mount point
sudo mkdir -p /mnt/new_root

# 2. Mount the new NVMe partition at this location
sudo mount /dev/nvme0n1p1 /mnt/new_root
```

### Step 4: Clone the filesystem

Copy the files with `rsync`, which keeps permissions, ownership and symbolic
links.

```bash
# This command copies the entire root filesystem to the new drive,
# excluding virtual and temporary filesystems that shouldn't be copied.
sudo rsync -aAXv --exclude={"/dev/*","/proc/*","/sys/*","/tmp/*","/run/*","/mnt/*","/media/*","/lost+found"} / /mnt/new_root
```
The copy can take a long time, depending on the size of your OS.

### Step 5: Update the filesystem table (`fstab`)

Edit the `fstab` on the *new* NVMe drive so it finds its own root partition
at boot. A mistake here or in step 6 leaves the board unable to boot from the
NVMe drive.

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

### Step 6: Reconfigure the bootloader

Edit the bootloader configuration on the **SD card** so it points at the new
root partition.

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

### Step 7: Reboot and verify

Reboot, to boot from the NVMe drive.

```bash
sudo reboot
```

After the reboot, run `lsblk` again. The root mount point (`/`) should now
be on `nvme0n1p1`.

```bash
lsblk
```

## Additional resources

- [`bootstrap/inventory/cluster.ini`](../../bootstrap/inventory/cluster.ini)
  lists the Orange Pi worker (`orange_pi_4a`) and its address.
