# Print the Go toolchain version from a Go binary's buildinfo header.
import re, sys
d = open(sys.argv[1], "rb").read()
i = d.find(b"\xff Go buildinf:")
hdr = d[i:i+64]
flags = hdr[15]
if flags & 2:  # inline varint-prefixed strings (Go >= 1.18)
    j = i + 32
    n = d[j]; print(d[j+1:j+1+n].decode())
else:
    print("pointer-format buildinfo; fallback:", sorted(set(re.findall(rb"go1\.\d+(?:\.\d+)?", d))))
