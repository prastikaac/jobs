import os
import json
import logging
import config
import jobs_store
import html_generator
import image_generator

logger = logging.getLogger("fix_images")
logging.basicConfig(level=logging.INFO)

# Load jobs
all_jobs = jobs_store.load_formatted_jobs_flat()

fixed_jobs = []

for job in all_jobs:
    # If the job has an image from 'other', we want it to get its correct category image now
    img = job.get("image_url", "")
    if "/other/" in img or not img:
        job["image_url"] = ""  # Clear it so it gets regenerated
        fixed_jobs.append(job)

logger.info(f"Found {len(fixed_jobs)} jobs that need a new category image assigned.")

if fixed_jobs:
    # Generate new missing images
    image_generator.generate_images_for_jobs(fixed_jobs)
    
    # Save the data
    jobs_store.save_formatted_jobs_flat(all_jobs)
    jobs_store.save_jobs(all_jobs)
    
    # Re-generate ONLY the HTML pages for these specific jobs!
    html_generator.generate_job_pages(fixed_jobs)
    
    # Re-generate the main index.html to ensure job cards point to right image
    html_generator.update_main_pages(all_jobs)

    logger.info("Fixed images and regenerated affected HTML pages!")

