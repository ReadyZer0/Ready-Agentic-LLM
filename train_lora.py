# Auto-generated Unsloth Training Script for ReadyAI Agent
from unsloth import FastLanguageModel
import torch

# 1. Load Model
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct",
    max_seq_length=2048,
    dtype=None,
    load_in_4bit=True
)

# 2. Add LoRA Adapters
model = FastLanguageModel.get_peft_model(
    model,
    r=16, # Rank
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    lora_alpha=16,
    lora_dropout=0,
    bias="none",
    use_gradient_checkpointing="unsloth"
)

print("\n✅ Model loaded from deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct and wrapped for LoRA training.")
print("👉 TODO: Add your custom SFTTrainer dataset logic here.")
print("👉 Once trained, use this to export to GGUF:")
print("   model.save_pretrained_gguf('readyai_agent_model', tokenizer, quantization_method='q4_k_m')\n")
