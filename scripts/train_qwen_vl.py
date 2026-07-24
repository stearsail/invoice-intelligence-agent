from collections import Counter

import psutil
from unsloth import FastVisionModel
import torch
from unsloth.trainer import UnslothVisionDataCollator
from trl import SFTTrainer, SFTConfig
from transformers import EarlyStoppingCallback, TrainerCallback
import mlflow
from pathlib import Path

from scripts.training_data import JsonlImageDataset, load_jsonl_data

data_dir = Path(__file__).parent.parent / "data" / "processed"
output_dir = Path(__file__).parent.parent / "outputs"

hyperparams = {
    "r": 8,
    "lr": 2e-4,
    "epochs": 3,
}

lora_config = {
    "finetune_vision_layers": True,
    "finetune_language_layers": True,
    "finetune_attention_modules": True,
    "finetune_mlp_modules": True,
    "r": hyperparams["r"],
    "lora_alpha": hyperparams["r"] * 2,
    "lora_dropout": 0,
    "bias": "none",
}


class SystemMemoryCallback(TrainerCallback):
    """Logs system (not GPU) RAM usage alongside the usual training metrics.
    Added after a training run got OOM-killed by the kernel — GPU memory was
    already tracked, but nothing surfaced system RAM climbing beforehand."""

    def on_log(self, args, state, control, logs=None, **kwargs):
        if not state.is_world_process_zero:
            return
        vm = psutil.virtual_memory()
        process_rss_gb = psutil.Process().memory_info().rss / (1024**3)
        mlflow.log_metrics(
            {
                "system_ram_used_gb": vm.used / (1024**3),
                "system_ram_percent": vm.percent,
                "process_ram_rss_gb": process_rss_gb,
            },
            step=state.global_step,
        )


model, tokenizer = FastVisionModel.from_pretrained(
    "unsloth/Qwen3-VL-4B-Instruct-unsloth-bnb-4bit",
    load_in_4bit=True,  # Use 4bit to reduce memory use. False for 16bit LoRA.
    use_gradient_checkpointing="unsloth",  # True or "unsloth" for long context
)

model = FastVisionModel.get_peft_model(
    model,
    **lora_config,
    random_state=3407,
)

train_rows = load_jsonl_data(data_dir / "train.jsonl")
val_rows = load_jsonl_data(data_dir / "val.jsonl")

train_data = JsonlImageDataset(train_rows, data_dir)
val_data = JsonlImageDataset(val_rows, data_dir)

dataset_composition = {
    "train_total": len(train_rows),
    "val_total": len(val_rows),
    **{
        f"train_{source}": count
        for source, count in Counter(row["source"] for row in train_rows).items()
    },
    **{
        f"val_{source}": count
        for source, count in Counter(row["source"] for row in val_rows).items()
    },
}

mlflow.set_experiment("qwen3-vl-fullds-finetune")

FastVisionModel.for_training(model)
trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    data_collator=UnslothVisionDataCollator(model, tokenizer),
    train_dataset=train_data,
    eval_dataset=val_data,
    args=SFTConfig(
        per_device_train_batch_size=4,
        gradient_accumulation_steps=4,
        warmup_steps=5,
        num_train_epochs=hyperparams["epochs"],
        learning_rate=2e-4,
        logging_steps=1,
        optim="adamw_8bit",
        weight_decay=0.001,
        lr_scheduler_type="linear",
        seed=3407,
        output_dir=output_dir
        / f"r{hyperparams['r']}-lr{hyperparams['lr']}-epochs{hyperparams['epochs']}",
        report_to="mlflow",  # For MLFlow
        run_name=f"r{hyperparams['r']}-lr{hyperparams['lr']}-epochs{hyperparams['epochs']}",
        eval_strategy="steps",
        eval_steps=15,
        per_device_eval_batch_size=4,
        save_strategy="steps",
        save_steps=15,  # must align with eval_steps for load_best_model_at_end
        save_total_limit=2,  # save_steps=15 means ~40 checkpoints/run otherwise; best is always kept
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        # You MUST put the below items for vision finetuning:
        remove_unused_columns=False,
        dataset_text_field="",
        dataset_kwargs={"skip_prepare_dataset": True},
        max_length=2048,
    ),
    callbacks=[
        EarlyStoppingCallback(early_stopping_patience=5),
        SystemMemoryCallback(),
    ],
)

with mlflow.start_run(
    run_name=f"r{hyperparams['r']}-lr{hyperparams['lr']}-epochs{hyperparams['epochs']}"
):
    mlflow.log_params({f"lora_{k}": v for k, v in lora_config.items()})
    mlflow.log_params(dataset_composition)

    gpu_stats = torch.cuda.get_device_properties(0)
    start_gpu_memory = round(torch.cuda.max_memory_reserved() / 1024 / 1024 / 1024, 3)
    max_memory = round(gpu_stats.total_memory / 1024 / 1024 / 1024, 3)
    print(f"GPU = {gpu_stats.name}. Max memory = {max_memory} GB.")
    print(f"{start_gpu_memory} GB of memory reserved.")

    trainer_stats = trainer.train()

    used_memory = round(torch.cuda.max_memory_reserved() / 1024 / 1024 / 1024, 3)
    used_memory_for_lora = round(used_memory - start_gpu_memory, 3)
    used_percentage = round(used_memory / max_memory * 100, 3)
    lora_percentage = round(used_memory_for_lora / max_memory * 100, 3)
    print(f"{trainer_stats.metrics['train_runtime']} seconds used for training.")
    print(
        f"{round(trainer_stats.metrics['train_runtime'] / 60, 2)} minutes used for training."
    )
    print(f"Peak reserved memory = {used_memory} GB.")
    print(f"Peak reserved memory for training = {used_memory_for_lora} GB.")
    print(f"Peak reserved memory % of max memory = {used_percentage} %.")
    print(f"Peak reserved memory for training % of max memory = {lora_percentage} %.")

    mlflow.log_metrics(
        {
            "peak_gpu_memory_reserved_gb": used_memory,
            "peak_gpu_memory_for_training_gb": used_memory_for_lora,
            "peak_gpu_memory_percent": used_percentage,
            "peak_gpu_memory_for_training_percent": lora_percentage,
        }
    )

    print(f"Best {trainer.args.metric_for_best_model}: {trainer.state.best_metric}")
    mlflow.log_metric("best_eval_loss", trainer.state.best_metric)

    merged_dir = (
        Path(__file__).parent.parent
        / "models"
        / f"qwen3-vl-fullds-merged-r{hyperparams['r']}-epochs{hyperparams['epochs']}"
    )
    model.save_pretrained_merged(str(merged_dir), tokenizer)
    print(f"Saved merged model to {merged_dir}")
