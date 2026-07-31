import os
import subprocess
import modal

app = modal.App(
    "vllm-serve-qwen-base",
    image=modal.Image.from_registry(
        "vllm/vllm-openai:v0.26.0",
        add_python="3.11",
    ).entrypoint([]),
)

# NOT the "-unsloth-bnb-4bit" (dynamic quant) checkpoint the fine-tune started
# from: its 79-entry llm_int8_skip_modules list quantizes the language backbone
# selectively at sublayer granularity, which vLLM's bitsandbytes loader cannot
# reconcile with its fused qkv/gate_up params (AssertionError in linear.py
# weight_loader). This standard variant quantizes the backbone uniformly (skip
# list is whole components only) — closest vLLM-servable stand-in for the
# training base.
MODEL_DIR = "unsloth/Qwen3-VL-4B-Instruct-bnb-4bit"


@app.function(
    gpu="L4",
    secrets=[modal.Secret.from_name("vllm-api-key")],
    scaledown_window=3600,
    timeout=3600,
    max_containers=1,
)
@modal.concurrent(max_inputs=16)
@modal.web_server(port=8000, startup_timeout=300)
def serve():
    subprocess.Popen(
        [
            "vllm",
            "serve",
            MODEL_DIR,
            "--served-model-name",
            "qwen3-vl-4b-base",
            "--host",
            "0.0.0.0",
            "--port",
            "8000",
            "--limit-mm-per-prompt",
            '{"image":1,"video":0}',
            "--max-model-len",
            "4096",
            # default 0.9 OOMs at warmup on this checkpoint: the 4-bit weights
            # are small, so vLLM reserves nearly the whole L4 for KV cache and
            # the sampler warmup pass has no scratch headroom left
            "--gpu-memory-utilization",
            "0.85",
            "--api-key",
            os.environ["VLLM_API_KEY"],
        ]
    )
