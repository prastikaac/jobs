"""
html_generator.py — Job HTML page generator + main page updater (Steps 4 & 5).

Step 4: For each job → create /jobs/{job-id}/index.html  (+ image.png already there)
Step 5: Regenerate index.html and jobs.html job listings sections
Also regenerates sitemap-jobs.xml for SEO.
"""

import html
import logging
import os
import re
from datetime import date, datetime
from typing import List

import config

logger = logging.getLogger("html_generator")


# ── Utilities ─────────────────────────────────────────────────────────────────

def _esc(text) -> str:
    """HTML-escape a value safely."""
    return html.escape(str(text or ""), quote=True)


def _desc_preview(text: str, chars: int = 200) -> str:
    """Return a short, escaped description preview for cards."""
    clean = re.sub(r"\s+", " ", str(text or "")).strip()
    preview = clean[:chars]
    if len(clean) > chars:
        preview += "…"
    return html.escape(preview)


def _display_date(date_str: str) -> str:
    try:
        return datetime.strptime(date_str[:10], "%Y-%m-%d").strftime("%B %d, %Y")
    except Exception:
        return str(date_str)


def _job_page_url(job: dict) -> str:
    category = _category_label(job)
    cat_slug = config.slugify_category(category)
    job_id = job.get("job_id", job.get("id", "unknown"))
    return f"{config.GITHUB_PAGES_BASE_URL}/jobs/{cat_slug}/{job_id}.html"


def _category_label(job: dict) -> str:
    return job.get("job_category", "Other")


def _location_label(job: dict) -> str:
    locs = job.get("jobLocation", ["Finland"])
    return ", ".join(locs[:2])


# ── Step 4: Individual job page ───────────────────────────────────────────────

# Load external template
def _load_job_template() -> str:
    template_path = os.path.join(os.path.dirname(__file__), "job_template.html")
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()


def generate_job_page(job: dict) -> bool:
    """
    Generate /jobs/{job-id}/index.html for a single job.
    Returns True on success.
    """
    job_id    = job["id"]
    title     = _esc(job.get("title", ""))
    company   = _esc(job.get("company", ""))
    location  = _location_label(job)
    category  = _category_label(job)
    desc_raw  = str(job.get("description") or "")
    desc_esc  = _esc(desc_raw)
    # Prefer dedicated meta_description field; fallback to truncated description
    meta_desc_raw = str(job.get("meta_description") or "")
    if not meta_desc_raw:
        meta_desc_raw = _desc_preview(desc_raw, 155)
    desc_meta = _esc(meta_desc_raw)
    page_url  = _job_page_url(job)
    job_link  = _esc(job.get("jobapply_link", ""))
    date_str  = str(job.get("date_posted", date.today()))
    display_d = _display_date(date_str)
    image_url = _esc(job.get("image_url") or f"{config.GITHUB_PAGES_BASE_URL}/images/jobs/other/default.png")

    company_part = f" — {company}" if company else ""

    cat_slug = config.slugify_category(category)
    job_id = job.get("job_id", job.get("id", "unknown"))
    output_dir  = os.path.join(config.JOBS_OUTPUT_DIR, cat_slug)
    output_path = os.path.join(output_dir, f"{job_id}.html")
    os.makedirs(output_dir, exist_ok=True)

    # Load the template dynamically
    try:
        template_str = _load_job_template()
    except Exception as exc:
        logger.error("Failed to load job_template.html: %s", exc)
        return False

    # Since the template contains CSS curly braces (e.g. body { margin: 0; }),
    # we can't use standard .format() easily without escaping all CSS braces.
    # Instead, we do simple string replacements for the placeholders.
    content = template_str
    
    from datetime import timedelta
    try:
        dt_posted = datetime.strptime(date_str[:10], "%Y-%m-%d")
        valid_date = (dt_posted + timedelta(days=30)).strftime("%Y-%m-%d") + "T23:59"
    except Exception:
        valid_date = ""

    # Build rich content lists
    rich_html = []

    # What we offer
    if job.get("what_we_offer"):
        rich_html.append(
            "<section>"
            "<h3>What We Offer</h3>"
            "<p>The benefits, resources, and supportive opportunities we provide to our employees "
            "to ensure a positive work experience, professional development, and long-term growth "
            "within the organization are as mentioned below:</p>"
            "<ul>"
        )
        for item in job["what_we_offer"]:
            rich_html.append(f"<li>{_esc(item)}</li>")
        rich_html.append("</ul></section>")

    # What we expect
    if job.get("what_we_expect"):
        rich_html.append(
            "<section>"
            "<h3>What We Expect</h3>"
            "<p>The qualities, work ethics, attitudes, and professional standards we expect from our team members "
            "to maintain a respectful, productive, and high-performing workplace environment are as mentioned below:</p>"
            "<ul>"
        )
        for item in job["what_we_expect"]:
            rich_html.append(f"<li>{_esc(item)}</li>")
        rich_html.append("</ul></section>")

    # Job responsibilities
    if job.get("job_responsibilities"):
        rich_html.append(
            "<section>"
            "<h3>Responsibilities</h3>"
            "<p>The primary duties, responsibilities, and contributions expected from individuals in this role "
            "to support daily operations, maintain organizational standards, and contribute to overall team "
            "and company success are as mentioned below:</p>"
            "<ul>"
        )
        for item in job["job_responsibilities"]:
            rich_html.append(f"<li>{_esc(item)}</li>")
        rich_html.append("</ul></section>")

    # Experience
    if job.get("experience"):
        items = job["experience"]
        if isinstance(items, str):
            items = [items]
        rich_html.append(
            "<section>"
            "<h3>Experience</h3>"
            "<p>The knowledge, skills, and professional background that candidates bring to the role, "
            "which help them contribute effectively and grow within the organization, are as mentioned below:</p>"
            "<ul>"
        )
        for item in items:
            rich_html.append(f"<li>{_esc(item)}</li>")
        rich_html.append("</ul></section>")

    # Who is this for
    if job.get("who_is_this_for"):
        rich_html.append(
            "<section>"
            "<h3>Who Is This For?</h3>"
            "<p>This opportunity is intended for individuals who demonstrate motivation, responsibility, "
            "and a willingness to learn, and who possess the qualities and interests suitable for working "
            "in a professional and team-oriented environment, as mentioned below:</p>"
            "<ul>"
        )
        for item in job["who_is_this_for"]:
            rich_html.append(f"<li>{_esc(item)}</li>")
        rich_html.append("</ul></section>")

    rich_content_str = "\n".join(rich_html)

    # Job Info values
    language_req = ", ".join(job.get("language_requirements") or []) or "Finnish or English"
    employment_type = ", ".join(job.get("employment_type") or []) or "Full-time, Permanent"
    salary = job.get("salary_range") or job.get("salary") or "Competitive hourly wage based on Finnish collective agreements"

    # ── Application method: direct URL or email-only ─────────────────────────
    employer_email = job.get("job_employer_email", "")
    raw_apply = job.get("jobapply_link", "") or ""

    # Detect email-based applications: either the apply link is already mailto:
    # (set by the scraper), or there's no useful apply URL but we have an email.
    is_email_apply = raw_apply.startswith("mailto:")
    if not is_email_apply and employer_email and (
        not raw_apply or "tyomarkkinatori.fi" in raw_apply
    ):
        is_email_apply = True

    if is_email_apply and employer_email:
        email_instructions = (
            f"<p>\n"
            f"Since there is no direct online application portal for this position, "
            f"interested candidates are encouraged to submit their applications, "
            f"including a cover letter and CV, via email to "
            f"<b><a href=\"mailto:{_esc(employer_email)}\">{_esc(employer_email)}</a></b>.\n"
            f"</p>"
        )
        job_link = f"mailto:{_esc(employer_email)}"
    else:
        email_instructions = ""

    replacements = {
        # Title
        "{-job title-}": title,
        # Company
        "{-company name-}": company,
        # Meta description (short, SEO — used in <meta>, OG, Twitter, JSON-LD)
        "{-meta_description-}": desc_meta,
        # Job description (long, 2-3 paragraphs — used in page body)
        "{-job description-}": desc_esc,
        # Rich HTML Content
        "{-rich content-}": rich_content_str,
        # Apply link
        "{-job apply link-}": job_link,
        # Location (single canonical placeholder)
        "{-job location name-}": _esc(location),
        # Dates
        "{-job date-}": date_str[:10],
        "{-scraped_at-}": _display_date(str(job.get("scraped_at") or date_str)),
        "{-job valid date-}": str(job.get("date_expires") or valid_date),
        # Image
        "{-job image-}": image_url,
        # Industry / category
        "{-job industry name-}": _esc(category.replace("_", " ").title()),
        "{-job industry slug-}": cat_slug,
        "{-job industry id-}": _esc(category),
        # Language
        "{-job language-}": _esc(language_req),
        # Salary
        "{-job salary-}": _esc(salary),
        # Job type
        "{-job type-}": _esc(employment_type),
        # URL / slug used in breadcrumbs
        "{-job url-}": job_id,
        # Full canonical page URL
        "{-page url-}": _esc(page_url),
        # Email instructions (conditional)
        "{-email_instructions-}": email_instructions,
        "{-job-employer-email-}": _esc(employer_email),
    }

    for key, val in replacements.items():
        content = content.replace(key, str(val))

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info("Generated page: /jobs/%s/%s", cat_slug, job_id)
        return True
    except OSError as exc:
        logger.error("Failed to write page for %s: %s", job_id, exc)
        return False


def generate_job_pages(jobs: List[dict]) -> int:
    """Generate individual pages for all jobs. Returns count of pages written."""
    count = 0
    for job in jobs:
        if generate_job_page(job):
            count += 1
    logger.info("Job pages generated: %d / %d", count, len(jobs))
    return count


# ── Job card HTML (used in index.html / jobs.html) ────────────────────────────

def _job_card(job: dict) -> str:
    title      = _esc(job.get("title", ""))
    company    = _esc(job.get("company", ""))
    location   = _esc(_location_label(job))
    category   = _esc(_category_label(job))
    desc_prev  = _esc(job.get("meta_description") or _desc_preview(job.get("description", ""), 180))
    page_url   = _esc(_job_page_url(job))
    image_url  = _esc(job.get("image_url") or f"{config.GITHUB_PAGES_BASE_URL}/images/jobs/other/default.png")
    date_str   = _display_date(str(job.get("date_posted", "")))
    scraped_at = _display_date(str(job.get("scraped_at") or job.get("date_posted", "")))
    job_link   = _esc(job.get("jobapply_link", ""))
    job_id     = _esc(job.get("job_id", job.get("id", "")))
    
    emp_type       = ", ".join(job.get("employment_type") or []) or "full-time"
    search_keywords = _esc(job.get("search_keywords") or title.lower())
    
    # Determine region-aware data-location for frontend filtering
    import re
    locs_lower = [str(l).lower().strip() for l in job.get("jobLocation", ["Finland"])]
    
    parts = []
    for loc in locs_lower:
        if loc and loc not in ("finland", "uusimaa", "uusimaa region"):
            slug = re.sub(r'[^a-z0-9]+', '-', loc).strip('-')
            if slug and slug not in parts:
                parts.append(slug)
                
    if any(loc in config.UUSIMAA_CITIES_LOWER for loc in locs_lower) and "uusimaa" not in parts:
        parts.append("uusimaa")
        
    if "finland" not in parts:
        parts.append("finland")
        
    data_loc = "-".join(parts)

    return f"""
        <article class="ntry" data-availability="{_esc(emp_type).lower()}" data-category="{category.lower()}"
                 data-location="{data_loc}" data-title="{search_keywords}">

          <div class="pThmb iyt">
            <a class="thmb" href="{page_url}">
              <img alt="{title}" class="imgThm lazy" src="{image_url}" data-src="{image_url}" loading="lazy" />
            </a>
            <div class="iFxd" style="z-index:1;">
              <span aria-label="Add to favorites" bm-id="{job_id}"
                    bm-img="{image_url}" bm-ttl="{title} - {location}"
                    bm-url="{page_url}" class="bM bmPs" role="button">
                <svg class="line" viewBox="0 0 24 24"><g transform="translate(4.500000, 2.500000)">
                  <path d="M7.47,0 C1.08,0 0,0.932 0,8.429 C0,16.822 -0.15,19 1.44,19 C3.04,19 5.64,15.316 7.47,15.316 C9.3,15.316 11.9,19 13.5,19 C15.09,19 14.94,16.822 14.94,8.429 C14.94,0.932 13.86,0 7.47,0 Z"></path>
                  <line class="svgC v" transform="translate(-4.5,-2.5)" x1="12" x2="12" y1="6" y2="12"></line>
                  <line class="svgC h" transform="translate(-4.5,-2.5)" x1="15" x2="9" y1="9" y2="9"></line>
                </g></svg>
              </span>
            </div>
          </div>

          <div class="pCntn">
            <div class="pHdr pSml">
              <div class="pLbls" style="font-weight:bold;" data-text="In">
                <a data-text="{location}" rel="tag" style="pointer-events:none;color:inherit;text-decoration:none;"></a>
              </div>
            </div>
            <h2 class="pTtl aTtl sml h1font">
              <a data-text="{title}" href="{page_url}" rel="bookmark">{title}</a>
            </h2>
            <div class="pSnpt">
              {desc_prev}
              <div class="pInf pSml" style="color:red;font-weight:bold;">
                <time class="aTtmp pTtmp pbl" data-text="Full-Time"
                      datetime="{job.get('scraped_at', job.get('date_posted', ''))[:10]}"
                      title="Posted: {scraped_at}"></time>
                <a aria-label="Apply Now" class="pJmp" data-text="Apply Now" href="{page_url}"></a>
              </div>
            </div>
          </div>

        </article>"""


# ── Step 5: Update index.html + jobs.html ─────────────────────────────────────

def _inject_cards(html_path: str, container_class: str, cards_html: str, page_name: str) -> bool:
    """Find a div by class and replace its children with new cards HTML."""
    if not os.path.exists(html_path):
        logger.warning("%s not found at %s", page_name, html_path)
        return False

    try:
        from bs4 import BeautifulSoup
        with open(html_path, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f, "html.parser")

        container = soup.find("div", class_=container_class)
        if not container:
            logger.warning("Container div.%s not found in %s", container_class, page_name)
            return False

        new_content = BeautifulSoup(cards_html, "html.parser")
        container.clear()
        container.append(new_content)

        with open(html_path, "w", encoding="utf-8") as f:
            f.write(str(soup))

        logger.info("Updated %s with %d job cards", page_name, cards_html.count("<article"))
        return True
    except Exception as exc:
        logger.error("Failed to update %s: %s", page_name, exc)
        return False


def update_main_pages(jobs: List[dict]) -> None:
    """
    Step 5 — Regenerate job listings in index.html and jobs.html.
    Uses the most recent 50 jobs for index, all jobs for jobs.html.
    """
    # Sort by date_posted descending
    sorted_jobs = sorted(jobs, key=lambda j: j.get("date_posted", ""), reverse=True)

    cards_all    = "\n".join(_job_card(j) for j in sorted_jobs)
    cards_recent = "\n".join(_job_card(j) for j in sorted_jobs[:50])

    website = config.WEBSITE_DIR
    _inject_cards(os.path.join(website, "index.html"), "blogPts", cards_recent, "index.html")
    _inject_cards(os.path.join(website, "jobs.html"),  "blogPts", cards_all,    "jobs.html")


# ── Sitemap ───────────────────────────────────────────────────────────────────

def update_sitemap(jobs: List[dict]) -> None:
    """Regenerate sitemap-jobs.xml with all active jobs."""
    base = config.GITHUB_PAGES_BASE_URL
    today = str(date.today())

    entries = []
    for job in jobs:
        cat = job.get("jobCategory", ["Other"])[0]
        cat_slug = cat.lower().replace(" ", "-")
        job_id = job.get("job_id", job.get("id", "unknown"))
        url = f"{base}/jobs/{cat_slug}/{job_id}.html"
        entries.append(
            f"  <url>\n"
            f"    <loc>{_esc(url)}</loc>\n"
            f"    <lastmod>{job.get('date_posted', today)[:10]}</lastmod>\n"
            f"    <changefreq>weekly</changefreq>\n"
            f"    <priority>0.8</priority>\n"
            f"  </url>"
        )

    sitemap_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(entries) +
        "\n</urlset>\n"
    )

    sitemap_path = os.path.join(config.WEBSITE_DIR, "sitemap-jobs.xml")
    try:
        with open(sitemap_path, "w", encoding="utf-8") as f:
            f.write(sitemap_xml)
        logger.info("Updated sitemap-jobs.xml with %d entries", len(entries))
    except OSError as exc:
        logger.error("Failed to write sitemap: %s", exc)
