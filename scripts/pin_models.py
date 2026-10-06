"""
pin_models.py - records the exact tag + digest of every model pulled into Ollama.
The brief says: "Pin each candidate by its exact Ollama tag and digest".

Usage:   python scripts/pin_models.py            (Ollama must be running on localhost:11434)
Output:  models_pinned.json  -> commit this, and copy the table into Slide 5
"""
import json
import urllib.request

with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=10) as r:
    models = json.loads(r.read())["models"]
with urllib.request.urlopen("http://localhost:11434/api/version", timeout=10) as r:
    version = json.loads(r.read())["version"]

pinned = [{
    "tag": m["name"],
    "digest": m["digest"],
    "size_gb": round(m["size"] / 1e9, 2),
    "parameter_size": m.get("details", {}).get("parameter_size"),
    "quantization": m.get("details", {}).get("quantization_level"),
} for m in models]

json.dump({"ollama_version": version, "models": pinned}, open("models_pinned.json", "w"), indent=2)
print(f"Ollama {version}")
for m in pinned:
    print(f"{m['tag']:<28} {m['parameter_size']:>6} {m['quantization']:<8} {m['digest']}")
