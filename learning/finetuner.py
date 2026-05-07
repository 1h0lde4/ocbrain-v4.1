"""
learning/finetuner.py — LoRA fine-tuning via Unsloth (QLoRA, ~6 GB VRAM).
Runs only when enough training pairs exist and training is enabled.
"""
from datetime import datetime
from pathlib import Path
from core.config import config


def train(module_name: str, data_path: Path) -> Path | None:
    """
    Fine-tune a LoRA adapter for the given module.
    Returns path to pending weights dir, or None on failure.
    """
    if not config.get("learning.training_enabled", True):
        print(f"[finetuner] Training disabled in settings.")
        return None

    pending = (
        Path(__file__).parent.parent / "modules" / module_name / "weights" / "pending"
    )
    pending.mkdir(parents=True, exist_ok=True)

    state      = config.get_module_state(module_name)
    base_model = state.get("base_model", "mistral:7b")

    try:
        from unsloth import FastLanguageModel
        from trl import SFTTrainer
        from transformers import TrainingArguments
        from datasets import load_dataset

        print(f"[finetuner] Loading base model: {base_model}")
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=base_model,
            max_seq_length=2048,
            load_in_4bit=True,    # QLoRA — halves VRAM usage
            dtype=None,           # auto-detect
        )

        model = FastLanguageModel.get_peft_model(
            model,
            r=16,
            lora_alpha=32,
            target_modules=["q_proj", "v_proj"],
            lora_dropout=0.05,
            bias="none",
            use_gradient_checkpointing=True,
        )

        dataset = load_dataset("json", data_files=str(data_path), split="train")

        trainer = SFTTrainer(
            model=model,
            tokenizer=tokenizer,
            train_dataset=dataset,
            dataset_text_field="output",
            max_seq_length=2048,
            args=TrainingArguments(
                per_device_train_batch_size=4,
                gradient_accumulation_steps=4,
                num_train_epochs=1,
                max_steps=200,
                learning_rate=2e-4,
                fp16=True,
                logging_steps=10,
                output_dir=str(pending),
                save_strategy="no",
            ),
        )

        print(f"[finetuner] Training {module_name}...")
        trainer.train()
        model.save_pretrained(str(pending))
        tokenizer.save_pretrained(str(pending))
        print(f"[finetuner] {module_name} weights saved to {pending}")

        # Update train_pairs count
        config.set_module_state(
            module_name, "train_pairs",
            state.get("train_pairs", 0) + _count_lines(data_path)
        )
        config.set_module_state(module_name, "last_trained", datetime.utcnow().isoformat())
        return pending

    except ImportError:
        print("[finetuner] Unsloth not installed — skipping fine-tuning.")
        return None
    except Exception as e:
        print(f"[finetuner] Training failed for {module_name}: {e}")
        return None


def _count_lines(path: Path) -> int:
    try:
        with open(path) as f:
            return sum(1 for _ in f)
    except Exception:
        return 0
