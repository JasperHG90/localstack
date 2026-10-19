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
  - id: inventory
    resource: bootstrap/inventory/cluster.ini
  - id: configure-nvidia-ctk
    resource: bootstrap/playbooks/configure_nvidia_ctk.yml
---

# Flashing a Jetson Orin Nano

Notes kept while setting up the Jetson Orin Nano worker (`jetson_nano` in
`bootstrap/inventory/cluster.ini`). They hold links only. Unlike the other
practices, no count or measurement backs them: the only code they tie to is
that inventory entry and the NVIDIA runtime set-up in
`bootstrap/playbooks/configure_nvidia_ctk.yml`. What the node runs is
[jetson-orin-nano, the GPU node](/nodes/jetson-orin-nano.md).

Firmware was already above 36.0, so it needed no update.

## Flashing from NVMe after SD card setup

- GH repo (contains link to NVIDIA forum) https://github.com/cranky-cyborg/Jetson-Flash-Manager

Useful guide

https://github.com/ajeetraina/jetson-orin-nano-super-guide

## Hold snap

https://forums.developer.nvidia.com/t/chromium-other-browsers-not-working-after-flashing-or-updating-heres-why-and-quick-fix/338891

## Outside network access

https://netbird.io/

## Evidence

Built or recorded from these, which a `sources` entry cannot point at:

- `docs/jetson_nano_orin_init.md` as of commit `3ec5d1e`, the page this concept was moved from
