import json
import os
import re
import time
from typing import Any, Dict, List

import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "qwen2.5:1.5b"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_FILE = os.path.join(BASE_DIR, "data", "translated_raw_jobs.json")
OUTPUT_FILE = os.path.join(BASE_DIR, "data", "formatted_jobs.json")

REQUEST_TIMEOUT = 300
SLEEP_BETWEEN_REQUESTS = 0.5


def load_json_file(file_path: str) -> Any:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Input file not found: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json_file(file_path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def extract_jobs(data: Any) -> List[Dict[str, Any]]:
    if isinstance(data, dict) and "jobs" in data and isinstance(data["jobs"], list):
        return data["jobs"]
    if isinstance(data, list):
        return data
    raise ValueError("Unsupported JSON structure. Expected either a list or a dict with a 'jobs' key.")


def rebuild_output(original_data: Any, jobs: List[Dict[str, Any]]) -> Any:
    if isinstance(original_data, dict) and "jobs" in original_data:
        output_data = dict(original_data)
        output_data["jobs"] = jobs
        return output_data
    return jobs


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(v).strip() for v in value if str(v).strip())
    return str(value).strip()


def normalize_whitespace(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text


def trim_to_sentence_boundary(text: str, min_len: int = 150, max_len: int = 160) -> str:
    text = normalize_whitespace(text)

    if len(text) <= max_len and len(text) >= min_len:
        return text

    if len(text) <= max_len:
        return text

    truncated = text[:max_len]
    last_punct = max(truncated.rfind("."), truncated.rfind("!"), truncated.rfind("?"))
    if last_punct >= min_len - 1:
        return truncated[: last_punct + 1].strip()

    last_space = truncated.rfind(" ")
    if last_space > 0:
        return truncated[:last_space].rstrip(" ,;-") + "..."
    return truncated[: max_len - 3].rstrip() + "..."


def make_meta_fallback(job: Dict[str, Any], formatted_description: str) -> str:
    title = clean_text(job.get("title"))
    location = clean_text(job.get("jobLocation"))
    company = clean_text(job.get("company"))

    parts = []
    if title:
        parts.append(title)
    if location:
        parts.append(f"in {location}")
    if company:
        parts.append(f"at {company}")

    intro = " ".join(parts).strip()
    if intro:
        intro += ". "

    base = intro + normalize_whitespace(formatted_description)
    base = re.sub(r"\s+", " ", base).strip()

    if len(base) < 150:
        extra = " Apply now for this opportunity in Finland."
        if extra not in base:
            base += extra

    return trim_to_sentence_boundary(base, 150, 160)


def build_description_prompt(job: Dict[str, Any]) -> str:
    title = clean_text(job.get("title"))
    company = clean_text(job.get("company"))
    location = clean_text(job.get("jobLocation"))
    work_time = clean_text(job.get("workTime"))
    continuity = clean_text(job.get("continuityOfWork"))
    salary = clean_text(job.get("salary_range"))
    languages = clean_text(job.get("language_requirements"))
    expectations = clean_text(job.get("what_we_expect"))
    responsibilities = clean_text(job.get("job_responsibilities"))
    offers = clean_text(job.get("what_we_offer"))
    content = clean_text(job.get("translated_content") or job.get("jobcontent"))

    return f"""
You are rewriting a job post into one clean, professional, natural English paragraph for a Finland jobs website.

Your task:
- Write ONLY one single paragraph.
- Make it read smoothly and professionally, like a polished job summary.
- Keep it concise but informative.
- Do not use bullet points.
- Do not use headings.
- Do not use HTML.
- Do not use markdown.
- Do not copy broken links, raw URLs, mailto text, duplicate lines, or messy formatting.
- Do not invent facts that are not present.
- Preserve important details such as role, duties, requirements, benefits, salary if available, and start timing if available.
- Use clear, human-sounding English.
- Start naturally, for example with phrases like "We are looking for..." when appropriate.
- Output ONLY the final paragraph and nothing else.

Job Title: {title}
Company: {company}
Location: {location}
Work Time: {work_time}
Continuity of Work: {continuity}
Salary: {salary}
Language Requirements: {languages}
What We Expect: {expectations}
Job Responsibilities: {responsibilities}
What We Offer: {offers}

Raw Job Content:
\"\"\"
{content}
\"\"\"
""".strip()


def build_meta_prompt(job: Dict[str, Any], formatted_description: str) -> str:
    title = clean_text(job.get("title"))
    company = clean_text(job.get("company"))
    location = clean_text(job.get("jobLocation"))

    return f"""
Write a concise SEO meta description for a job posting.

Rules:
- Length MUST be between 150 and 160 characters.
- Do NOT exceed 160 characters.
- Include the job title and location naturally if possible.
- Make it clear, clickable, and professional.
- Use natural English.
- Do not use quotes.
- Do not use HTML.
- Do not use markdown.
- Output ONLY the meta description text.

Job Title: {title}
Company: {company}
Location: {location}

Job Summary:
{formatted_description}
""".strip()


def call_ollama(prompt: str, num_predict: int = 300) -> str:
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.2,
            "top_p": 0.9,
            "num_predict": num_predict
        }
    }

    response = requests.post(OLLAMA_URL, json=payload, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()

    data = response.json()
    return data.get("response", "").strip()


def sanitize_ai_output(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z0-9_-]*", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    return normalize_whitespace(text)


def print_full_output(job_title: str, description: str, meta_description: str) -> None:
    print("\n" + "=" * 100)
    print(f"JOB: {job_title}")
    print("-" * 100)
    print("DESCRIPTION:\n")
    print(description)
    print("\nMETA DESCRIPTION:\n")
    print(meta_description)
    print(f"\nMETA LENGTH: {len(meta_description)} characters")
    print("=" * 100 + "\n")


def format_job_description(job: Dict[str, Any], index: int, total: int) -> Dict[str, Any]:
    title = job.get("title", "Untitled Job")
    print(f"[{index}/{total}] Formatting: {title}")

    try:
        description_prompt = build_description_prompt(job)
        formatted_description = call_ollama(description_prompt, num_predict=300)
        formatted_description = sanitize_ai_output(formatted_description)

        meta_prompt = build_meta_prompt(job, formatted_description)
        meta_description = call_ollama(meta_prompt, num_predict=80)
        meta_description = sanitize_ai_output(meta_description)
        meta_description = trim_to_sentence_boundary(meta_description, 150, 160)

        if len(meta_description) < 150:
            meta_description = make_meta_fallback(job, formatted_description)

        job["formatted_description"] = formatted_description
        job["meta_description"] = meta_description
        job["format_status"] = "success"
        job["format_error"] = ""

        print_full_output(title, formatted_description, meta_description)

    except Exception as e:
        error_message = str(e)
        print(f"ERROR while formatting '{title}': {error_message}\n")

        fallback_description = normalize_whitespace(job.get("translated_content") or job.get("jobcontent") or "")
        fallback_meta = make_meta_fallback(job, fallback_description)

        job["formatted_description"] = fallback_description
        job["meta_description"] = fallback_meta
        job["format_status"] = "error"
        job["format_error"] = error_message

    return job


def main() -> None:
    print(f"Loading jobs from: {INPUT_FILE}")
    original_data = load_json_file(INPUT_FILE)
    jobs = extract_jobs(original_data)

    total_jobs = len(jobs)
    print(f"Found {total_jobs} jobs\n")

    formatted_jobs = []

    for index, job in enumerate(jobs, start=1):
        formatted_job = format_job_description(job, index, total_jobs)
        formatted_jobs.append(formatted_job)

        time.sleep(SLEEP_BETWEEN_REQUESTS)

    output_data = rebuild_output(original_data, formatted_jobs)
    save_json_file(OUTPUT_FILE, output_data)

    success_count = sum(1 for job in formatted_jobs if job.get("format_status") == "success")
    failed_count = total_jobs - success_count

    print("Done.")
    print(f"Successful: {success_count}")
    print(f"Failed: {failed_count}")
    print(f"Saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()