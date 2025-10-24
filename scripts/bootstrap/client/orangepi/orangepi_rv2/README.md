# README

The orange pi rv2 has a riscv64 architecture, which is a bit painful because not all applications support it (e.g. nomad).

However, it has a massive benefit in terms of price, NVMe slots (2x), CPU (8 cores), and RAM (2GB). As such, this board is used for
minio with a 4TB NVMe SSD. Gitea also runs comfortably here since riscv64 architecture is supported natively.
