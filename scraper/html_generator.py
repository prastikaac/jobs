"""
html_generator.py — Job HTML page generator + main page updater (Steps 4 & 5).

Step 4: For each job → create /jobs/{job-id}/index.html  (+ image.png already there)
Step 5: Regenerate index.html and jobs.html job listings sections
Also regenerates sitemap-jobs.xml for SEO.
"""

import html
import json
import logging
import os
import re
from datetime import date, datetime
from typing import List

import config

logger = logging.getLogger("html_generator")

# Load municipality codes and build a name -> region map for display enrichment
MUNICIPALITY_MAP = {}
try:
    map_path = os.path.join(os.path.dirname(__file__), "municipalities_codes.json")
    if os.path.exists(map_path):
        with open(map_path, "r", encoding="utf-8") as f:
            muni_data = json.load(f)
            for code, data in muni_data.items():
                name = data.get("KUNTANIMIFI")
                region = data.get("MAAKUNTANIMIFI")
                if name:
                    MUNICIPALITY_MAP[name.lower()] = region
except Exception as e:
    logger.warning("Could not load municipalities_codes.json for HTML generation: %s", e)


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
    if not locs or (len(locs) == 1 and locs[0].lower() == "finland"):
        return "Finland"
    
    # Filter out 'finland' from cities list if present for cleaner joining
    clean_cities = [c for c in locs if c.lower() != "finland"]
    if not clean_cities:
        return "Finland"
    
    unique_regions = []
    for city in clean_cities:
        region = MUNICIPALITY_MAP.get(city.lower())
        if region and region not in unique_regions:
            unique_regions.append(region)
    
    # Combine cities, unique regions, and Finland
    parts = clean_cities + unique_regions + ["Finland"]
    return ", ".join(parts)


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
            "<p>The benefits, resources, and opportunities we offer to support a positive work experience and long-term growth are listed below:</p>"
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
            "<p>The qualities, work ethics, and standards we expect to maintain a productive and respectful workplace are listed below:</p>"
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
            "<p>This opportunity is for motivated, responsible individuals eager to learn and thrive in a team-oriented environment, who possess the qualities mentioned below:</p>"
            "<ul>"
        )
        for item in job["job_responsibilities"]:
            rich_html.append(f"<li>{_esc(item)}</li>")
        rich_html.append("</ul></section>")


    # Who is this for
    if job.get("who_is_this_for"):
        rich_html.append(
            "<section>"
            "<h3>Who Is This For?</h3>"
            "<p>This opportunity is for motivated, responsible individuals eager to learn and thrive in a team-oriented environment, who possess the qualities mentioned below:</p>"
            "<ul>"
        )
        for item in job["who_is_this_for"]:
            rich_html.append(f"<li>{_esc(item)}</li>")
        rich_html.append("</ul></section>")

    rich_content_str = "\n".join(rich_html)

    # Job Info values
    language_req = ", ".join(job.get("language_requirements") or []) or "Finnish or English"
    work_time = job.get("workTime") or "Full-time"
    continuity_of_work = job.get("continuityOfWork") or "Permanent"
    salary = job.get("salary_range") or job.get("salary") or "Competitive hourly wage based on Finnish collective agreements"

    # ── Application method: direct URL or email-only ─────────────────────────
    employer_email = job.get("job_employer_email", "")
    raw_apply = job.get("jobapply_link", "") or ""

    # Detect email-based applications: either the apply link is already mailto:
    # (set by the scraper), or there's no useful apply URL but we have an email.
    is_email_apply = raw_apply.startswith("mailto:")
    if is_email_apply and not employer_email:
        import urllib.parse
        extracted = raw_apply[7:].split('?')[0]
        employer_email = urllib.parse.unquote(extracted).strip()

    if not is_email_apply and employer_email and (
        not raw_apply or "tyomarkkinatori.fi" in raw_apply
    ):
        is_email_apply = True

    if is_email_apply and employer_email:
        contact_name = job.get("job_employer_name", "")
        contact_phone = job.get("job_employer_phone_no", "")
        
        contact_info = ""
        if contact_name or contact_phone:
            c_name = _esc(contact_name) if contact_name else ""
            c_phone = f" ({_esc(contact_phone)})" if contact_phone else ""
            colon = " : " if c_name or c_phone else ""
            contact_info = f" Also, you may reach out to the contact person for the job{colon}{c_name}{c_phone}."

        import urllib.parse
        subject_raw = f"Application for the Job - {title}"
        body_raw = f"Dear Hiring Manager,\n\nI hope this message finds you well.\n\nI am writing to express my interest in the {title}. I am motivated, reliable, and eager to contribute my skills and experience to your team.\n\nI have experience in relevant tasks and a strong ability to adapt quickly to new environments. I take pride in being hardworking, detail-oriented, and maintaining a positive attitude at work. I am confident that I can add value to your organization.\n\nPlease find my CV & Cover Letter attached for your review. I would welcome the opportunity to discuss how my skills and experience align with your needs.\n\nThank you for your time and consideration. I look forward to hearing from you.\n\nKind regards,\nYOUR_NAME"
        
        subject_encoded = urllib.parse.quote(subject_raw)
        body_encoded = urllib.parse.quote(body_raw)
        mailto_link = f"mailto:{_esc(employer_email)}?subject={subject_encoded}&body={body_encoded}"

        email_instructions = (
            f"<p>\n"
            f"Since there is no direct online application portal for this position, "
            f"interested candidates are encouraged to submit their application, "
            f"including a cover letter and CV, via email to "
            f"<b><a href=\"{mailto_link}\">{_esc(employer_email)}</a></b>."
            f"{contact_info}\n"
            f"</p>"
        )
        job_link = mailto_link
    else:
        email_instructions = ""

    replacements = {
        # Title
        "{-job title-}": title,
        # Open Positions
        "{-job open position-}": str(job.get("open_positions", 1)),
        # Company
        "{-company name-}": company,
        "{-company-}": company,
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
        # Work time / continuity (template placeholders)
        "{-workTime-}": _esc(work_time),
        "{-continuityOfWork-}": _esc(continuity_of_work),
        # Legacy placeholder — kept blank so it doesn't appear in output
        "{-job type-}": _esc(f"{work_time}, {continuity_of_work}"),
        # URL / slug used in breadcrumbs
        "{-job url-}": job_id,
        # Full canonical page URL
        "{-page url-}": _esc(page_url),
        # Email instructions (conditional)
        "{-email_instructions-}": email_instructions,
        "{-job-employer-email-}": _esc(employer_email),
        
        # New Recruiter Information Section
        "{-job_employer_name-}": _esc(job.get("job_employer_name", "")),
        "{-employer_email-}": _esc(employer_email),
        "{-job_employer_phone_no-}": _esc(job.get("job_employer_phone_no", "")),
        "{-display_contact_person-}": "" if job.get("job_employer_name", "") else 'style="display: none;"',
        "{-display_employer_email-}": "" if employer_email else 'style="display: none;"',
        "{-display_employer_phone-}": "" if job.get("job_employer_phone_no", "") else 'style="display: none;"',
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
    
    work_time_card = (job.get("workTime") or "Full-time").lower()
    search_keywords = _esc(job.get("search_keywords") or title.lower())
    
    # Determine region-aware data-location for frontend filtering
    import re
    locs_raw = job.get("jobLocation", ["Finland"])
    locs_lower = [str(l).lower().strip() for l in locs_raw]
    
    parts = []
    # 1. Add Cities
    for loc in locs_lower:
        if loc and loc not in ("finland",):
            slug = re.sub(r'[^a-z0-9]+', '-', loc).strip('-')
            if slug and slug not in parts:
                parts.append(slug)
                
    # 2. Add Regions (dynamic lookup from municipalities_codes.json)
    for city in locs_lower:
        region = MUNICIPALITY_MAP.get(city)
        if region:
            r_slug = re.sub(r'[^a-z0-9]+', '-', region.lower()).strip('-')
            if r_slug and r_slug not in parts:
                parts.append(r_slug)
                
    # 3. Add Finland
    if "finland" not in parts:
        parts.append("finland")
        
    data_loc = "-".join(parts)

    continuity_card = (job.get("continuityOfWork") or "Permanent").lower().replace(" ", "-")
    date_published = _esc(job.get("date_posted", ""))
    date_deadline = _esc(job.get("date_expires", ""))
    language_req = _esc(", ".join(job.get("language_requirements") or []) or "Finnish or English")

    return f"""
        <article class="ntry" data-category="{category.lower()}"
                 data-location="{data_loc}" data-published="{date_published}"
                 data-time="{_esc(work_time_card)}" data-language="{language_req}"
                 data-continuityofwork="{_esc(continuity_card)}" data-title="{search_keywords}">

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

def _inject_index_cards(html_path: str, sections_data: dict, page_name: str) -> bool:
    """Find specific HTML comments and replace the content immediately after them until the next comment."""
    if not os.path.exists(html_path):
        logger.warning("%s not found at %s", page_name, html_path)
        return False

    try:
        from bs4 import BeautifulSoup, Comment
        with open(html_path, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f, "html.parser")
            
        comments = soup.find_all(string=lambda text: isinstance(text, Comment))
        for c in comments:
            # Normalize whitespace/case (e.g. 'Nursing Jobs  ' -> 'nursing jobs')
            key = c.strip().lower()
            key = " ".join(key.split())
            
            if key in sections_data:
                # Remove existing articles immediately after this comment
                sibling = c.next_sibling
                while sibling:
                    next_sib = sibling.next_sibling
                    if sibling.name == 'article':
                        sibling.extract()
                    elif isinstance(sibling, Comment):
                        break # Stop if we hit another comment
                    sibling = next_sib
                
                # Insert new content
                new_content = BeautifulSoup(sections_data[key], "html.parser")
                c.insert_after(new_content)
                
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(str(soup))
            
        logger.info("Updated %s with specific sections", page_name)
        return True
    except Exception as exc:
        logger.error("Failed to update index logic: %s", exc)
        return False


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
    Uses categorical sections for index.html, all jobs for jobs.html.
    """
    import random
    
    # Sort by date_posted descending
    sorted_jobs = sorted(jobs, key=lambda j: j.get("date_posted", ""), reverse=True)

    cards_all = "\n".join(_job_card(j) for j in sorted_jobs)
    
    # 1) Top jobs: random categories, max length 25 titles, up to 9
    short_title_jobs = [j for j in sorted_jobs if len(j.get("title", "")) <= 25]
    random.shuffle(short_title_jobs)
    top_jobs = short_title_jobs[:9]

    # 2) Specific category buckets
    it_jobs = [j for j in sorted_jobs if j.get("job_category") == "it-and-tech"][:6]
    nursing_jobs = [j for j in sorted_jobs if j.get("job_category") == "healthcare-and-social-care"][:6]
    cleaning_jobs = [j for j in sorted_jobs if j.get("job_category") == "cleaning-and-facility-services"][:6]
    restaurant_jobs = [j for j in sorted_jobs if j.get("job_category") == "food-and-restaurant"][:6]

    sections_data = {
        "top jobs": "\n".join(_job_card(j) for j in top_jobs),
        "it & technology jobs": "\n".join(_job_card(j) for j in it_jobs),
        "nursing jobs": "\n".join(_job_card(j) for j in nursing_jobs),
        "cleaning jobs": "\n".join(_job_card(j) for j in cleaning_jobs),
        "restaurant jobs": "\n".join(_job_card(j) for j in restaurant_jobs)
    }

    website = config.WEBSITE_DIR
    _inject_index_cards(os.path.join(website, "index.html"), sections_data, "index.html")
    _inject_cards(os.path.join(website, "jobs.html"),  "blogPts", cards_all, "jobs.html")


# ── Sitemap ───────────────────────────────────────────────────────────────────

def update_sitemap(jobs: List[dict]) -> None:
    """Regenerate sitemap-jobs.xml with all active jobs and update master sitemap.xml."""
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
        logger.error("Failed to write sitemap-jobs.xml: %s", exc)

    # Automatically also update the master sitemap.xml lastmod dates
    master_sitemap_path = os.path.join(config.WEBSITE_DIR, "sitemap.xml")
    try:
        if os.path.exists(master_sitemap_path):
            with open(master_sitemap_path, "r", encoding="utf-8") as f:
                master_content = f.read()
            
            import re
            master_content = re.sub(r"<lastmod>.*?</lastmod>", f"<lastmod>{today}</lastmod>", master_content)
            
            with open(master_sitemap_path, "w", encoding="utf-8") as f:
                f.write(master_content)
            logger.info("Updated master sitemap.xml <lastmod> flags to %s", today)
    except Exception as exc:
        logger.error("Failed to update master sitemap.xml: %s", exc)
