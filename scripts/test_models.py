#!/usr/bin/env python3
"""Test model API / local inference.

Usage:
    python scripts/test_models.py                  # Test all
    python scripts/test_models.py --embed-only
    python scripts/test_models.py --llm-only

VSCode 调试：直接修改下方 RUN_* 开关，F5 运行即可。
"""

# ----------------------------------------------------------------
# VSCode 调试开关 —— 直接改 True/False，无需传命令行参数
# ----------------------------------------------------------------
RUN_EMBED = True
RUN_LLM   = True
RUN_VLM   = False
# ----------------------------------------------------------------

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

GREEN = "\033[92m"
RED = "\033[91m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"


def ok(msg): print(f"  {GREEN}✓{RESET} {msg}")
def fail(msg): print(f"  {RED}✗{RESET} {msg}")
def info(msg): print(f"  {CYAN}→{RESET} {msg}")
def section(title): print(f"\n{BOLD}{title}{RESET}\n{'─' * 50}")


def test_embedding():
    section("Embedding Model")

    from app.config import get_settings
    settings = get_settings()
    info(f"Backend: {settings.embed_backend}")
    info(f"API base: {settings.embed_api_base}" if settings.embed_backend == "api" else f"Model path: {settings.embed_model_path}")

    if settings.embed_backend == "local" and not Path(settings.embed_model_path).exists():
        fail(f"Model not found at {settings.embed_model_path}")
        return False

    try:
        from app.model_service.embedding import embed_texts

        # API/Ollama 模式无需预加载，直接推理
        if settings.embed_backend == "local":
            from app.model_service.embedding import get_embedder
            start = time.perf_counter()
            model = get_embedder()
            load_time = time.perf_counter() - start
            ok(f"Model loaded in {load_time:.1f}s")
            dim = model.get_sentence_embedding_dimension()
            ok(f"Dimension: {dim}")
            if dim != settings.milvus_dim:
                fail(f"Dimension mismatch! Model={dim}, MILVUS_DIM={settings.milvus_dim}")
                print(f"    → Update MILVUS_DIM={dim} in your .env")

        # Inference
        test_texts = [
            "本周完成了基础设施建设第二阶段",
            "混凝土浇筑已完成80%",
            "钢筋绑扎和模板安装同步推进",
        ]

        start = time.perf_counter()
        embeddings = embed_texts(test_texts)
        infer_time = time.perf_counter() - start
        ok(f"Inference: {len(test_texts)} texts in {infer_time*1000:.0f}ms ({infer_time/len(test_texts)*1000:.1f}ms/text)")

        # Similarity check
        import numpy as np
        e0, e1, e2 = [np.array(e) for e in embeddings]
        sim_01 = np.dot(e0, e1)  # both about construction
        sim_02 = np.dot(e0, e2)  # both about construction
        ok(f"Cosine sim (0,1)={sim_01:.3f}, (0,2)={sim_02:.3f} — should be > 0.5")

        # Throughput benchmark
        bench_texts = [f"测试文本第{i}段，关于项目进度的描述。" for i in range(50)]
        start = time.perf_counter()
        embed_texts(bench_texts)
        bench_time = time.perf_counter() - start
        throughput = len(bench_texts) / bench_time
        ok(f"Throughput: {throughput:.0f} texts/sec (50 texts in {bench_time:.2f}s)")

        if settings.embed_backend == "local":
            from app.model_service.embedding import unload_embedder
            unload_embedder()
        return True

    except Exception as e:
        fail(f"Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_llm():
    section("LLM Model")

    from app.config import get_settings
    settings = get_settings()
    info(f"Backend: {settings.llm_backend}")
    info(f"Model path: {settings.llm_model_path}")
    info(f"Device: {settings.llm_device}")

    if settings.llm_backend == "local" and not Path(settings.llm_model_path).exists():
        fail(f"Model not found at {settings.llm_model_path}")
        return False

    try:
        from app.model_service.llm import llm_generate

        # Simple generation test
        start = time.perf_counter()
        response = llm_generate(
            prompt="用一句话总结：本周项目完成了基础浇筑，进度达到65%。",
            system="你是一个项目周报助手，请简洁回答。",
            max_tokens=100,
        )
        gen_time = time.perf_counter() - start

        ok(f"Generation in {gen_time:.1f}s")
        ok(f"Response ({len(response)} chars): {response[:100]}...")

        # Multi-turn test
        start = time.perf_counter()
        response2 = llm_generate(
            prompt="根据以下信息生成周报摘要：\n- 基础施工完成65%\n- 钢筋到货延迟2天\n- 下周计划开始主体结构",
            system="你是项目周报生成助手。请用3-5句话生成周报摘要。",
            max_tokens=300,
        )
        gen_time2 = time.perf_counter() - start
        ok(f"Report summary in {gen_time2:.1f}s ({len(response2)} chars)")
        print(f"    {response2[:200]}...")

        if settings.llm_backend == "local":
            from app.model_service.llm import unload_llm
            unload_llm()
        return True

    except Exception as e:
        fail(f"Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_vlm():
    section("VLM Model")

    from app.config import get_settings
    settings = get_settings()
    info(f"Enabled: {settings.vlm_enabled}")

    if not settings.vlm_enabled:
        info("VLM disabled, skipping (set VLM_ENABLED=true to test)")
        return True

    info(f"Model path: {settings.vlm_model_path}")
    info(f"Backend: {settings.llm_backend}")

    if settings.llm_backend == "local" and not Path(settings.vlm_model_path).exists():
        fail(f"Model not found at {settings.vlm_model_path}")
        return False

    try:
        from PIL import Image, ImageDraw, ImageFont

        # ── 1. Generate a synthetic test image (no external file needed) ──
        test_img_path = Path("storage/.test_vlm_image.png")
        test_img_path.parent.mkdir(parents=True, exist_ok=True)

        img = Image.new("RGB", (640, 480), color=(135, 206, 235))  # sky blue background
        draw = ImageDraw.Draw(img)

        # Draw simple construction site elements
        # Ground
        draw.rectangle([0, 350, 640, 480], fill=(139, 119, 101))
        # Building frame
        draw.rectangle([100, 150, 300, 350], outline=(80, 80, 80), width=3)
        draw.rectangle([120, 170, 180, 250], outline=(80, 80, 80), width=2)  # window
        draw.rectangle([220, 170, 280, 250], outline=(80, 80, 80), width=2)  # window
        draw.rectangle([160, 270, 240, 350], fill=(139, 90, 43))  # door
        # Crane
        draw.line([400, 50, 400, 350], fill=(255, 165, 0), width=4)
        draw.line([350, 50, 500, 50], fill=(255, 165, 0), width=3)
        draw.line([480, 50, 480, 120], fill=(100, 100, 100), width=2)
        # Text label on image
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
        except (IOError, OSError):
            font = ImageFont.load_default()
        draw.text((320, 400), "Construction Site - Phase 2", fill=(255, 255, 255), font=font)
        draw.text((110, 130), "Building A", fill=(50, 50, 50), font=font)

        img.save(test_img_path)
        ok(f"Test image generated: {test_img_path} ({img.size[0]}x{img.size[1]})")

        # ── 2. Load model and run inference ──────────────────────
        from app.model_service.vlm import vlm_describe

        info("Running VLM inference (this may take a while on first load)...")

        start = time.perf_counter()
        description = vlm_describe(
            test_img_path,
            prompt="请用中文描述这张图片的内容，包括建筑物、设备、环境等信息。",
        )
        infer_time = time.perf_counter() - start

        if description:
            ok(f"VLM inference in {infer_time:.1f}s")
            ok(f"Description ({len(description)} chars):")
            # Print description with indent
            for line in description[:300].splitlines():
                print(f"    {line}")
            if len(description) > 300:
                print(f"    ...")
        else:
            fail(f"VLM returned empty description (took {infer_time:.1f}s)")
            return False

        # ── 3. Test with a different prompt ──────────────────────
        start = time.perf_counter()
        description2 = vlm_describe(
            test_img_path,
            prompt="What objects can you see in this image? List them.",
        )
        infer_time2 = time.perf_counter() - start

        if description2:
            ok(f"English prompt in {infer_time2:.1f}s ({len(description2)} chars)")
        else:
            info("English prompt returned empty (model may be Chinese-only)")

        # ── 4. Cleanup ───────────────────────────────────────────
        test_img_path.unlink(missing_ok=True)
        ok("Test image cleaned up")

        return True

    except Exception as e:
        fail(f"Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    # 命令行参数（CLI 用）；调试时由顶部 RUN_* 开关覆盖
    parser = argparse.ArgumentParser()
    parser.add_argument("--embed-only", action="store_true")
    parser.add_argument("--llm-only", action="store_true")
    parser.add_argument("--vlm-only", action="store_true")
    args = parser.parse_args()

    # 若命令行传了参数则以命令行为准，否则使用顶部调试开关
    cli_specified = args.embed_only or args.llm_only or args.vlm_only
    if cli_specified:
        run_embed = args.embed_only
        run_llm   = args.llm_only
        run_vlm   = args.vlm_only
    else:
        run_embed = RUN_EMBED
        run_llm   = RUN_LLM
        run_vlm   = RUN_VLM

    # 三个开关全为 False 时，默认跑全部
    if not (run_embed or run_llm or run_vlm):
        run_embed = run_llm = run_vlm = True

    print(f"\n{BOLD}{'=' * 50}{RESET}")
    print(f"{BOLD}  Model Verification{RESET}")
    print(f"{BOLD}{'=' * 50}{RESET}")

    results = {}
    if run_embed:
        results["Embedding"] = test_embedding()
    if run_llm:
        results["LLM"] = test_llm()
    if run_vlm:
        results["VLM"] = test_vlm()

    section("Summary")
    all_ok = True
    for name, passed in results.items():
        status = f"{GREEN}PASS{RESET}" if passed else f"{RED}FAIL{RESET}"
        print(f"  {name:12s} {status}")
        if not passed:
            all_ok = False

    print()
    return all_ok


if __name__ == "__main__":
    main()