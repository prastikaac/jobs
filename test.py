import shutil
from pathlib import Path

# Base directory
BASE_DIR = Path("images/jobs")

# Source folder
SOURCE_FOLDER = BASE_DIR / "administration-and-office-work"

# Images to copy (1.png to 30.png)
images = [f"{i}.png" for i in range(1, 31)]

# ONLY new folders (your output list)
new_folders = [
    "web-development",
    "mobile-development",
    "frontend-development",
    "backend-development",
    "full-stack-development",
    "data-engineering",
    "data-analytics-and-bi",
    "cloud-and-devops",
    "qa-and-testing",
    "it-support-and-helpdesk",
    "systems-and-network-administration",
    "product-management",
    "technical-writing",
    "mechanical-engineering",
    "electrical-engineering",
    "automation-and-controls",
    "process-engineering",
    "civil-engineering",
    "cad-and-bim",
    "machining-and-cnc",
    "welding",
    "assembly-and-installation",
    "printing-and-packaging",
    "quality-control-and-assurance",
    "painting-and-finishing",
    "tiling-and-flooring",
    "roofing",
    "earthworks-and-infrastructure",
    "surveying-and-site-engineering",
    "construction-cleaning",
    "moving-jobs",
    "courier-jobs",
    "courier-and-last-mile-delivery",
    "food-delivery-driver",
    "forklift-driver",
    "forklift-and-material-handling",
    "picker-and-packer",
    "terminal-worker",
    "procurement-and-sourcing",
    "customs-and-import-export",
    "taxi-and-ride-services",
    "bus-driver",
    "truck-driver",
    "doctor-and-physician-jobs",
    "dentistry",
    "pharmacy",
    "laboratory-healthcare",
    "medical-imaging",
    "physiotherapy-and-rehabilitation",
    "occupational-therapy",
    "childcare-and-family-support",
    "industrial-cleaning",
    "office-cleaning",
    "hotel-cleaning",
    "janitor",
    "caretaker",
    "waste-management-and-recycling",
    "cooking-and-kitchen-staff",
    "fast-food-jobs",
    "pizza-kebab-workers",
    "bakery-jobs",
    "bakery-and-pastry",
    "dishwasher",
    "bar-and-nightlife",
    "coffee-shop-and-cafe-jobs",
    "reception-and-front-desk",
    "call-center-and-phone-support",
    "technical-customer-support",
    "field-service-and-installation",
    "installation-jobs",
    "complaints-and-back-office-support",
    "banking-and-insurance",
    "digital-marketing",
    "e-commerce",
    "recruitment-and-talent-acquisition",
    "operations-management",
    "executive-and-leadership",
    "real-estate-and-property-management",
    "special-education",
    "school-support-and-assistant-jobs",
    "higher-education-and-research-teaching",
    "ngo-and-nonprofit",
    "copywriting-and-editing",
    "journalism-and-publishing",
    "translation-and-localization",
    "farm-worker",
    "greenhouse-work",
    "berry-picking",
    "seasonal-agriculture",
    "animal-care-and-veterinary",
    "energy-and-utilities",
    "security-jobs",
    "occupational-health-and-safety",
    "automotive",
    "vehicle-maintenance-and-repair",
    "maintenance-technician",
    "service-technician",
    "repair-technician",
    "marine-and-aviation",
    "apprenticeships",
    "summer-jobs",
    "bilingual-and-multilingual-jobs",
    "no-experience-jobs",
    "english-speaking-jobs",
    "finnish-speaking-jobs",
    "wolt-jobs",
    "foodora-jobs",
    "bolt-jobs",
    "uber-jobs"
]

def main():
    copied = 0
    skipped = 0

    for folder in new_folders:
        dest_folder = BASE_DIR / folder

        for img in images:
            src = SOURCE_FOLDER / img
            dst = dest_folder / img

            if not src.exists():
                print(f"Missing source image: {src}")
                continue

            if dst.exists():
                skipped += 1
                continue

            shutil.copy2(src, dst)
            copied += 1

    print("\n=== DONE ===")
    print(f"Images copied: {copied}")
    print(f"Skipped (already existed): {skipped}")

if __name__ == "__main__":
    main()