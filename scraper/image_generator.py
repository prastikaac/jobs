"""
image_generator.py — Job image processor (Step 3 of the pipeline).

For each job:
  1. Detect job category
  2. Pick a random numbered image (1.png – 50.png) from:
       images/jobs/{category}/
  3. Resize & center-crop to 1280×630 px
  4. Save as /jobs/{job-id}/image.png inside the website directory

The public image URL is stored on the job dict as "image_url".

Image pool convention:
  Each category folder MUST contain images named 1.png, 2.png … up to N.png
  (up to 50 supported). The generator picks a random index in 1–50 and falls
  back to index 1 if the chosen number is missing.
"""

import logging
import os
import random
from typing import Optional

from PIL import Image

import config

logger = logging.getLogger("image_generator")

TARGET_W = 1280
TARGET_H = 630
MAX_IMAGES = 50  # images per category named 1.png … 50.png


# ── Category folder lookup ────────────────────────────────────────────────────

def _category_to_folder(category: str) -> str:
    """
    Map a job's category string to a source-image folder name.
    Uses config.get_safe_category_slug to ensure it maps to an existing folder.
    Returns 'other' as the final fallback.
    """
    if not category:
        return "other"
    
    return config.get_safe_category_slug(category)


def _pick_source_image(folder: str) -> Optional[str]:
    """
    Select a random image from the category source folder.

    Images must be named 1.png, 2.png … up to MAX_IMAGES.
    Picks a random number in [1, MAX_IMAGES].  If that file doesn't exist,
    scans downward from MAX_IMAGES to 1 and returns the first found.
    Returns None if no numbered image exists at all.
    """
    folder_path = os.path.join(config.IMAGES_JOBS_DIR, folder)

    # Discover how many images actually exist (1.png … N.png)
    available = [
        n for n in range(1, MAX_IMAGES + 1)
        if os.path.isfile(os.path.join(folder_path, f"{n}.png"))
    ]

    if not available:
        logger.warning("No numbered images found in '%s'", folder_path)
        return None

    chosen = random.choice(available)
    return os.path.join(folder_path, f"{chosen}.png")


# ── Image processing ──────────────────────────────────────────────────────────

def _crop_and_save(source_path: str, output_path: str) -> bool:
    """Resize + center-crop to TARGET_W × TARGET_H and save as PNG."""
    try:
        with Image.open(source_path) as img:
            img = img.convert("RGB")

            # Compute scale to cover the target dimensions
            w_scale = TARGET_W / img.width
            h_scale = TARGET_H / img.height
            scale   = max(w_scale, h_scale)

            new_w = int(img.width  * scale)
            new_h = int(img.height * scale)
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

            # Center crop
            left   = (new_w - TARGET_W) // 2
            top    = (new_h - TARGET_H) // 2
            right  = left + TARGET_W
            bottom = top  + TARGET_H
            img    = img.crop((left, top, right, bottom))

            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            img.save(output_path, "PNG", optimize=True)
        return True
    except Exception as exc:
        logger.error("Image processing failed (%s): %s", source_path, exc)
        return False


# ── Public API ────────────────────────────────────────────────────────────────

def generate_job_image(job: dict) -> Optional[str]:
    """
    Select a random image from the category folder and return its PUBLIC URL.
    """
    category = job.get("job_category", "other")
    folder = _category_to_folder(category)
    
    number = random.randint(1, 30)
    public_url = f"{config.GITHUB_PAGES_BASE_URL}/images/jobs/{folder}/{number}.png"
    
    logger.info("Assigned image for [%s] → %s", job["id"], public_url)
    return public_url


def generate_images_for_jobs(jobs: list[dict]) -> int:
    """
    Generate images for all jobs that don't already have one.
    Updates each job dict in-place with "image_url".
    Returns the number of new images created.
    """
    count = 0
    for job in jobs:
        if job.get("image_url"):
            continue  # already has an image
        url = generate_job_image(job)
        if url:
            job["image_url"] = url
            count += 1
    logger.info("https://findjobsinfinland.fi/images generated: %d", count)
    return count
