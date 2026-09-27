---
type: practice
title: Flashing a Jetson Orin Nano
description: "Scratch notes from setting up the Jetson Orin Nano: firmware version, links for flashing to NVMe after SD card setup, holding the snap, and outside network access."
tags: [jetson, hardware, nvme, flashing]
status: stable
generated:
  by: claude-opus/5.5
  at: 2026-09-26
sources:
  - id: jetson-nano-orin-init
    resource: git:3ec5d1e:docs/jetson_nano_orin_init.md
    last_modified: 2025-11-24
---

# Flashing a Jetson Orin Nano

Notes kept while setting up the Jetson Orin Nano worker (`jetson_nano` in
`bootstrap/inventory/cluster.ini`). They hold links only.

Firmware is already >36.0 so so issues there

## Flashing from NVMe after SD card setup

- GH repo (contains link to NVIDIA forum) https://github.com/cranky-cyborg/Jetson-Flash-Manager

Useful guide

https://github.com/ajeetraina/jetson-orin-nano-super-guide

## Hold snap

https://forums.developer.nvidia.com/t/chromium-other-browsers-not-working-after-flashing-or-updating-heres-why-and-quick-fix/338891

## Outside network access

https://netbird.io/
