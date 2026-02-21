# from propertia_api_scraper import run as run_propertia

# if __name__ == "__main__":
#     run_propertia()

from propertia_api_scraper import run as run_propertia

if __name__ == "__main__":
    run_propertia(max_pages=2, max_listings=20)