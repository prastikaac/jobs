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
import expiration

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

AUTHORS_LIST = []
try:
    authors_path = os.path.join(os.path.dirname(__file__), "authors.json")
    if os.path.exists(authors_path):
        with open(authors_path, "r", encoding="utf-8") as f:
            AUTHORS_LIST = json.load(f).get("authors", [])
except Exception as e:
    logger.warning("Could not load authors.json for HTML generation: %s", e)



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
    return f"{config.GITHUB_PAGES_BASE_URL}/jobs/{cat_slug}/{job_id}"


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


    # Optional Description
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
        import urllib.parse
        subject_raw = f"Application for the Job - {title}"
        body_raw = f"Dear Hiring Manager,\n\nI hope this message finds you well.\n\nI am writing to express my interest in the {title}. I am motivated, reliable, and eager to contribute my skills and experience to your team.\n\nI have experience in relevant tasks and a strong ability to adapt quickly to new environments. I take pride in being hardworking, detail-oriented, and maintaining a positive attitude at work. I am confident that I can add value to your organization.\n\nPlease find my CV & Cover Letter attached for your review. I would welcome the opportunity to discuss how my skills and experience align with your needs.\n\nThank you for your time and consideration. I look forward to hearing from you.\n\nKind regards,\nYOUR_NAME"
        
        subject_encoded = urllib.parse.quote(subject_raw)
        body_encoded = urllib.parse.quote(body_raw)
        mailto_link = f"mailto:{_esc(employer_email)}?subject={subject_encoded}&body={body_encoded}"

        email_instructions = (
            f"<p>\n"
            f"There is no direct online application portal for this position. "
            f"So, you can submit your application, "
            f"including a cover letter and CV, via email to "
            f"<b><a href=\"{mailto_link}\">{_esc(employer_email)}</a></b>.\n"
            f"</p>"
        )
        job_link = mailto_link
    else:
        email_instructions = ""

    # Location logic for breadcrumbs and display
    locs_raw = job.get("jobLocation", ["Finland"])
    clean_cities = [c for c in locs_raw if c.lower() != "finland"]
    num_locations = len(clean_cities)
    is_multiple = num_locations > 1
    
    # Text display for the breadcrumb/page ("Multiple Locations" when > 1 city)
    if is_multiple:
        location_display = "Multiple Locations"
    else:
        location_display = _esc(location)
    
    # All city names joined — used in the job-card Location info row
    location_all_names = _esc(location)
    
    # Link parameter (combine cities and regions for the URL parameter)
    import urllib.parse
    link_parts = []
    if clean_cities:
        link_parts.append(clean_cities[0])
        for c in clean_cities[1:]:
            link_parts.append(f"city:{c}")
            
        unique_regions = []
        for city in clean_cities:
            region = MUNICIPALITY_MAP.get(city.lower())
            if region and region not in unique_regions:
                unique_regions.append(region)
                
        for r in unique_regions:
            link_parts.append(f"region:{r}")
            
        raw_location_link = ",".join(link_parts)
    else:
        raw_location_link = "Finland"
        
    location_link = urllib.parse.quote(raw_location_link)

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
        # Location display name — used in breadcrumb visible text
        "{-job location name-}": location_display,
        # All city names joined — used in the job-card Location info row
        "{-job location all names-}": location_all_names,
        # New placeholder for the specific search link
        "{-job location link-}": location_link,
        # Legacy placeholder
        "{-multiple locations-}": "",
        # Dates
        "{-job date-}": date_str[:10],
        "{-scraped_at-}": _display_date(str(job.get("scraped_at") or date_str)),
        "{-job valid date-}": str(job.get("date_expires") or valid_date),
        "{-job deadline-}": _display_date(str(job.get("date_expires") or valid_date)),
        # Image
        "{-job image-}": image_url,
        # Industry / category
        "{-job industry name-}": _esc(category.replace("_", " ").replace("-", " ").title().replace(" And ", " and ").replace("Information Technology", "Information Technology (IT)")),
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
        "{-display_recruiter_info-}": "" if (job.get("job_employer_name", "") or employer_email or job.get("job_employer_phone_no", "")) else 'style="display: none;"',
    }

    if AUTHORS_LIST:
        import random
        author = random.choice(AUTHORS_LIST)
        replacements["{-author_name-}"] = _esc(author.get("name", "findjobsinfinland.fi"))
        # Strip https:// or http:// because template uses url(//{-author_photo-})
        photo_url = author.get("photo", "findjobsinfinland.fi/images/authors/prasiddha-acharya.png")
        if photo_url.startswith("https://"):
            photo_url = photo_url[8:]
        elif photo_url.startswith("http://"):
            photo_url = photo_url[7:]
        replacements["{-author_photo-}"] = _esc(photo_url)
    else:
        replacements["{-author_name-}"] = "Prasiddha Acharya"
        replacements["{-author_photo-}"] = "findjobsinfinland.fi/images/authors/prasiddha-acharya.png"

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
              <img alt="{title}" class="imgThm lazy loaded" data-src="{image_url}" lazied="" src="{image_url}"/>
              <noscript>
                <img alt="{title}" class="imgThm" src="{image_url}"/>
              </noscript>
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
                <time class="aTtmp pTtmp pbl"
                      datetime="{job.get('scraped_at', job.get('date_posted', ''))[:10]}"
                      title="Posted: {scraped_at}">{date_str}</time>
                <a class="pJmp" href="{page_url}">Apply Now</a>
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

def _xml_escape_url(url: str) -> str:
    """Escape XML special characters in a URL string."""
    return (
        url.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("'", "&apos;")
        .replace('"', "&quot;")
    )


def _is_job_active(job: dict) -> bool:
    """Check if a job is active, public, and not expired."""
    return not expiration.is_job_expired(job)


def _get_lastmod_now() -> str:
    """Return current datetime in ISO 8601 format with Finland timezone (+03:00)."""
    now = datetime.now()
    return now.strftime("%Y-%m-%dT%H:%M:%S") + "+03:00"


def _generate_sitemap_jobs(jobs: List[dict], lastmod: str) -> str:
    """Generate sitemap-jobs.xml content with all active job pages."""
    base = config.GITHUB_PAGES_BASE_URL
    seen_urls = set()
    entries = []

    for job in jobs:
        if not _is_job_active(job):
            continue

        category = _category_label(job)
        cat_slug = config.slugify_category(category)
        job_id = job.get("job_id", job.get("id", "unknown"))

        if not job_id or job_id == "unknown":
            continue

        # Canonical URL without .html
        url = f"{base}/jobs/{cat_slug}/{job_id}"

        # Verify the HTML file actually exists
        html_path = os.path.join(config.JOBS_OUTPUT_DIR, cat_slug, f"{job_id}.html")
        if not os.path.exists(html_path):
            continue

        # Deduplicate
        if url in seen_urls:
            continue
        seen_urls.add(url)

        escaped_url = _xml_escape_url(url)
        entries.append(
            f"  <url>\n"
            f"    <loc>{escaped_url}</loc>\n"
            f"    <lastmod>{lastmod}</lastmod>\n"
            f"  </url>"
        )

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(entries)
        + "\n</urlset>\n"
    )


def _generate_sitemap_pages(jobs: List[dict], lastmod: str) -> str:
    """Generate sitemap-pages.xml with homepage, static pages, and category pages."""
    base = config.GITHUB_PAGES_BASE_URL
    seen_urls = set()
    entries = []

    # Static pages (homepage + known pages)
    static_pages = [
        (f"{base}/", lastmod),
        (f"{base}/jobs/", lastmod),
        (f"{base}/about-us", lastmod),
        (f"{base}/contact-us", lastmod),
        (f"{base}/privacy-policy", lastmod),
        (f"{base}/disclaimer", lastmod),
        (f"{base}/terms-and-conditions", lastmod),
    ]

    for url, mod in static_pages:
        if url not in seen_urls:
            seen_urls.add(url)
            entries.append(
                f"  <url>\n"
                f"    <loc>{_xml_escape_url(url)}</loc>\n"
                f"    <lastmod>{mod}</lastmod>\n"
                f"  </url>"
            )

    # Discover category pages dynamically from active jobs
    active_categories = set()
    for job in jobs:
        if _is_job_active(job):
            category = _category_label(job)
            cat_slug = config.slugify_category(category)
            active_categories.add(cat_slug)

    for cat_slug in sorted(active_categories):
        url = f"{base}/jobs/{cat_slug}/"
        if url not in seen_urls:
            seen_urls.add(url)
            entries.append(
                f"  <url>\n"
                f"    <loc>{_xml_escape_url(url)}</loc>\n"
                f"    <lastmod>{lastmod}</lastmod>\n"
                f"  </url>"
            )

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(entries)
        + "\n</urlset>\n"
    )


def _generate_sitemap_blogs(lastmod: str) -> str:
    """Generate sitemap-blogs.xml by scanning the blogs/ directory."""
    base = config.GITHUB_PAGES_BASE_URL
    blogs_dir = os.path.join(config.WEBSITE_DIR, "blogs")
    entries = []
    seen_urls = set()

    if os.path.exists(blogs_dir):
        for filename in sorted(os.listdir(blogs_dir)):
            if filename.endswith(".html"):
                slug = filename.replace(".html", "")
                url = f"{base}/blogs/{slug}"
                if url not in seen_urls:
                    seen_urls.add(url)
                    entries.append(
                        f"  <url>\n"
                        f"    <loc>{_xml_escape_url(url)}</loc>\n"
                        f"    <lastmod>{lastmod}</lastmod>\n"
                        f"  </url>"
                    )

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(entries)
        + "\n</urlset>\n"
    )


def _generate_sitemap_index(lastmod: str) -> str:
    """Generate the master sitemap.xml (sitemap index)."""
    base = config.GITHUB_PAGES_BASE_URL
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"  <sitemap>\n"
        f"    <loc>{base}/sitemap-jobs.xml</loc>\n"
        f"    <lastmod>{lastmod}</lastmod>\n"
        f"  </sitemap>\n"
        f"  <sitemap>\n"
        f"    <loc>{base}/sitemap-pages.xml</loc>\n"
        f"    <lastmod>{lastmod}</lastmod>\n"
        f"  </sitemap>\n"
        f"  <sitemap>\n"
        f"    <loc>{base}/sitemap-blogs.xml</loc>\n"
        f"    <lastmod>{lastmod}</lastmod>\n"
        f"  </sitemap>\n"
        '</sitemapindex>\n'
    )


def update_sitemap(jobs: List[dict]) -> None:
    """Regenerate all sitemap files: sitemap.xml, sitemap-jobs.xml, sitemap-pages.xml, sitemap-blogs.xml."""
    lastmod = _get_lastmod_now()
    website = config.WEBSITE_DIR

    # 1. sitemap-jobs.xml — active job pages only
    jobs_xml = _generate_sitemap_jobs(jobs, lastmod)
    jobs_count = jobs_xml.count("<url>")
    try:
        with open(os.path.join(website, "sitemap-jobs.xml"), "w", encoding="utf-8") as f:
            f.write(jobs_xml)
        logger.info("Updated sitemap-jobs.xml with %d entries", jobs_count)
    except OSError as exc:
        logger.error("Failed to write sitemap-jobs.xml: %s", exc)

    # 2. sitemap-pages.xml — homepage, static pages, category pages
    pages_xml = _generate_sitemap_pages(jobs, lastmod)
    pages_count = pages_xml.count("<url>")
    try:
        with open(os.path.join(website, "sitemap-pages.xml"), "w", encoding="utf-8") as f:
            f.write(pages_xml)
        logger.info("Updated sitemap-pages.xml with %d entries", pages_count)
    except OSError as exc:
        logger.error("Failed to write sitemap-pages.xml: %s", exc)

    # 3. sitemap-blogs.xml — blog pages
    blogs_xml = _generate_sitemap_blogs(lastmod)
    blogs_count = blogs_xml.count("<url>")
    try:
        with open(os.path.join(website, "sitemap-blogs.xml"), "w", encoding="utf-8") as f:
            f.write(blogs_xml)
        logger.info("Updated sitemap-blogs.xml with %d entries", blogs_count)
    except OSError as exc:
        logger.error("Failed to write sitemap-blogs.xml: %s", exc)

    # 4. sitemap.xml — master sitemap index
    index_xml = _generate_sitemap_index(lastmod)
    try:
        with open(os.path.join(website, "sitemap.xml"), "w", encoding="utf-8") as f:
            f.write(index_xml)
        logger.info("Updated master sitemap.xml with lastmod %s", lastmod)
    except OSError as exc:
        logger.error("Failed to write sitemap.xml: %s", exc)
