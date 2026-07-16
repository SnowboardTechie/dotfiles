# Apple Silicon model and quantization selection

Use this note when recommending a local model for an Apple Silicon endpoint, especially MLX versus Ollama.

## Decision sequence

1. Get the **exact model ID and serving command** before recommending a replacement. Similar names can refer to an upstream checkpoint, an MLX conversion, an Ollama/GGUF package, or a third-party fine-tune.
2. Separate three decisions:
   - base model and training;
   - quantization format and precision;
   - serving runtime/API.
   A model name containing `NVFP4` does not by itself establish that NVIDIA hardware or an MLX runtime is in use.
3. Verify the conversion's metadata and runtime support. For MLX repositories, inspect the model card, `config.json` quantization block, and weight size. Check MLX source/docs for the relevant Metal kernels rather than inferring support from the quantization name.
4. Compare candidates for the agent workload: native tool-call parsing, schema adherence, long-horizon reliability, context behavior, active parameters, weight bytes, and measured throughput. Total parameter count alone is a weak selector for MoE agents.
5. Do not recommend higher precision solely because unified memory can hold it. Apple Silicon inference is often memory-bandwidth constrained; doubling weight bytes can reduce throughput while producing only a small quality gain.
6. Keep a working lower-bit model unless an A/B test shows meaningful failures. Escalate precision when it measurably improves malformed/missed tool calls, large-schema adherence, reasoning stability, or task completion.

## Qwen3.6 35B-A3B example

As observed in July 2026:

- `mlx-community/Qwen3.6-35B-A3B-nvfp4` is an MLX conversion using 4-bit `nvfp4` mode and occupies about 20.4 GB of weights.
- `mlx-community/Qwen3.6-35B-A3B-8bit` occupies about 37.7 GB.
- Both use the same 35B-total / 3B-active base model. The 8-bit build is a quality-comparison option, not an automatic upgrade on a 128 GB Mac.
- MLX contains Metal FP4 kernels, so `nvfp4` in an MLX conversion can be Apple-compatible despite the name.
- `nvidia/Qwen3.6-35B-A3B-NVFP4` is a different NVIDIA ModelOpt checkpoint whose card targets vLLM and Hopper/Blackwell. Do not conflate it with the MLX-community conversion.
- If a similarly named model is installed through Ollama, it is served by Ollama's runtime, not MLX. Quantization labels and serving runtimes are independent.

## Practical A/B test

Run both candidates through the same OpenAI-compatible client and representative Hermes prompts. Record:

- prompt-processing and generation speed;
- malformed, missed, or repeated tool calls;
- correctness across multi-step tool sequences;
- context length and memory pressure;
- final task completion, not just prose quality.

Prefer the smaller/faster quantization when task reliability is equivalent.