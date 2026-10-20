"""Run inside the hermes image as the hermes user: drive the gateway's inbound
voice path (GatewayInboundMixin._enrich_message_with_transcription) on one .ogg."""
import asyncio, json, os, sys, time, types, importlib.util
sys.path.insert(0, "/opt/hermes")
os.chdir("/opt/hermes")
import logging
logging.basicConfig(level=logging.INFO, stream=sys.stdout, format='LOG %(name)s %(levelname)s %(message)s')
from gateway.run_inbound import GatewayInboundMixin
from tools.transcription_tools import _get_provider, _load_stt_config
print('stt config:', _load_stt_config(), '-> provider:', _get_provider(_load_stt_config()))

class Runner(GatewayInboundMixin):
    pass

r = object.__new__(Runner)
r.config = types.SimpleNamespace(stt_enabled=True)
had_fw = importlib.util.find_spec("faster_whisper") is not None
t0 = time.monotonic()
text, transcripts = asyncio.run(r._enrich_message_with_transcription("", [sys.argv[1]]))
elapsed = time.monotonic() - t0
hwm = [l for l in open("/proc/self/status") if l.startswith("VmHWM")][0].split()[1]
def cg(name):
    try: return int(open(f"/sys/fs/cgroup/{name}").read().split()[0])
    except Exception as e: return str(e)
print(json.dumps({"faster_whisper_before": had_fw, "seconds": round(elapsed, 1),
    "process_peak_rss_mb": int(hwm) // 1024, "cgroup_peak_mb": cg("memory.peak") // 2**20 if isinstance(cg("memory.peak"), int) else cg("memory.peak"),
    "cgroup_max": open("/sys/fs/cgroup/memory.max").read().strip(),
    "enriched_text": text, "transcripts": transcripts}))
low = " ".join(transcripts).lower()
sys.exit(0 if all(w in low for w in ("brown", "fox", "lazy")) else 3)
