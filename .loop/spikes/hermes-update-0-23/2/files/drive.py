"""Run inside the hermes image as uid 10000 with HOME=/opt/data (as main-wrapper.sh sets it):
drive the gateway's inbound voice path (GatewayInboundMixin._enrich_message_with_transcription)
on one .ogg and print time, memory and the transcript."""
import asyncio, json, os, sys, time, types, importlib.util, logging
sys.path.insert(0, "/opt/hermes")
os.chdir("/opt/hermes")
logging.basicConfig(level=logging.INFO, stream=sys.stdout, format="LOG %(name)s %(levelname)s %(message)s")
from gateway.run_inbound import GatewayInboundMixin
from tools.transcription_tools import _get_provider, _load_stt_config

def cg(name):
    return int(open(f"/sys/fs/cgroup/{name}").read().split()[0]) // 2**20

cfg = _load_stt_config()
print("stt config:", cfg, "-> provider:", _get_provider(cfg))
class Runner(GatewayInboundMixin):
    pass
r = object.__new__(Runner)
r.config = types.SimpleNamespace(stt_enabled=True)
before = cg("memory.current")
t0 = time.monotonic()
text, transcripts = asyncio.run(r._enrich_message_with_transcription("", [sys.argv[1]]))
elapsed = time.monotonic() - t0
anon = [l for l in open("/sys/fs/cgroup/memory.stat") if l.startswith("anon ")][0].split()[1]
print(json.dumps({"faster_whisper": importlib.util.find_spec("faster_whisper") is not None,
    "seconds": round(elapsed, 1), "cgroup_mb_before": before, "cgroup_peak_mb": cg("memory.peak"),
    "cgroup_anon_mb_after": int(anon) // 2**20,
    "cgroup_max": open("/sys/fs/cgroup/memory.max").read().strip(), "transcripts": transcripts}))
low = " ".join(transcripts).lower()
sys.exit(0 if all(w in low for w in ("brown", "fox", "lazy")) else 3)
