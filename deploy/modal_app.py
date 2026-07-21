import os
import subprocess
import modal

app = modal.App(
    "vllm-serve-qwen",
    image=modal.Image.from_registry(
        "vllm/vllm-openai:v0.19.1",
        add_python="3.11",
    ).entrypoint([]),
)

volume = modal.Volume.from_name("qwen3-vl-cord-weights", create_if_missing=True)
MODEL_DIR = "/models/qwen3-vl-cord-merged"


@app.function(
    gpu="L4",
    volumes={"/models": volume},
    secrets=[modal.Secret.from_name("vllm-api-key")],
    scaledown_window=300,
    timeout=3600,
    max_containers=1,
)
@modal.web_server(port=8000, startup_timeout=300)
def serve():
    subprocess.Popen(
        [
            "vllm",
            "serve",
            MODEL_DIR,
            "--served-model-name",
            "qwen3-vl-cord-merged",
            "--host",
            "0.0.0.0",
            "--port",
            "8000",
            "--limit-mm-per-prompt",
            '{"image":1,"video":0}',
            "--max-model-len",
            "4096",
            "--api-key",
            os.environ["VLLM_API_KEY"],
        ]
    )
