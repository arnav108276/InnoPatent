from flask import Flask, request, jsonify, render_template
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import logging
import time

app = Flask(__name__, static_folder='static', template_folder='templates')

# Configure logging to suppress unwanted messages
logging.basicConfig(level=logging.ERROR)

# Fitness function to calculate relevance of a result to the target query
def fitness(result, target_query):
    title_score = target_query.lower() in result['title'].lower()
    description_score = target_query.lower() in result['description'].lower()
    return title_score * 2 + description_score

# Grey Wolf Optimization (GWO) to optimize the search results
def gwo_optimize_results(results, target_query):
    if not results:
        print("No results to optimize.")
        return []  # Return empty list if no results are available
    
    wolves = results.copy()
    wolves_fitness = [(wolf, fitness(wolf, target_query)) for wolf in wolves]
    wolves_fitness.sort(key=lambda x: x[1], reverse=True)
    
    alpha = wolves_fitness[0][0]
    beta = wolves_fitness[1][0] if len(wolves_fitness) > 1 else None
    delta = wolves_fitness[2][0] if len(wolves_fitness) > 2 else None
    rest = [wolf[0] for wolf in wolves_fitness[3:]]
    return [alpha, beta, delta] + rest if beta and delta else [alpha]

# Setup Chrome WebDriver using webdriver-manager
def get_chrome_driver():
    chrome_options = Options()
    chrome_options.add_argument('--headless')  # Headless mode


    # Automatically fetch and setup the right ChromeDriver version
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver
# Scrape Google Patents data
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
def scrape_google_patents(query, page_num):
    results = []
    driver = get_chrome_driver()
    try:
        url = f"https://patents.google.com/?q={query}&oq={query}&page={page_num}"
        driver.get(url)
        time.sleep(1.5)  # Allow page to load
        # Locate all result items
        result_items = driver.find_elements(By.CSS_SELECTOR, 'search-result-item')
        for item in result_items:
            try:
                title = item.find_element(By.CSS_SELECTOR, '#htmlContent').text.strip()
                description = item.find_element(By.CSS_SELECTOR, '#htmlContent').text.strip()
                patent_id = item.find_element(By.CSS_SELECTOR, '[data-proto="OPEN_PATENT_PDF"]').text.strip()
                authors = item.find_elements(By.CSS_SELECTOR, '.style-scope.search-result-item')[0].text.strip()
                patent_url = f"https://patents.google.com/patent/{patent_id}/en"
                image_url = item.find_element(By.CSS_SELECTOR, 'img').get_attribute('src') if item.find_elements(By.CSS_SELECTOR, 'img') else None
                # Extract filing date
                filing_date = item.find_element(By.CSS_SELECTOR, 'h4.dates.style-scope.search-result-item').text
                filing_date = filing_date.split('Filed ')[1].split(' ')[0]  # Extract "Filed YYYY-MM-DD"
                # Add data to results
                results.append({
                    'title': title,
                    'description': description,
                    'authors': authors,
                    'id': f'<span style="color: red;">{patent_id}</span>',
                    'url': patent_url,
                    'image': image_url,  # Include the image URL in the result
                    'filing_date': filing_date  # Add filing date to dictionary
                })
            except Exception as e:
                print(f"Error extracting patent info: {e}")
                pass
    finally:
        driver.quit()
    
    return results
# Scrape Espacenet data and map to Google Patents
from selenium.webdriver.common.by import By
import time
def scrape_espacenet(query, page_num):
    results = []
    driver = get_chrome_driver()
    try:
        # Navigate to the Espacenet search results page
        url = f"https://worldwide.espacenet.com/patent/search?q={query}&page={page_num}"
        driver.get(url)
        time.sleep(1.5)  # Allow the page to load
        # Locate all search result items
        items = driver.find_elements(By.CSS_SELECTOR, 'article.item--wSceB4di')
        for item in items:
            try:
                # Extract title and description
                title = item.find_element(By.CSS_SELECTOR, 'header.h2--2VrrSjFb').text.strip()
                description = item.find_element(By.CSS_SELECTOR, '.copy-text--uk738M73').text.strip()
                # Extract patent ID and construct the patent URL
                patent_id = item.find_element(By.TAG_NAME, 'a').get_attribute('href').split('/')[-1]
                patent_url = f"https://patents.google.com/patent/{patent_id}/en"

                # Extract image URL if present
                image_element = item.find_elements(By.CSS_SELECTOR, 'img')
                image_url = image_element[0].get_attribute('src') if image_element else None

                # Extract filing date (CSS based on the second screenshot)
                filing_date = item.find_element(By.CSS_SELECTOR, 'span').text.strip()

                # Append result to the list
                results.append({
                    'title': title,
                    'description': description,
                    'id': f'<span style="color: red;">{patent_id}</span>',
                    'url': patent_url,
                    'image': image_url,  # Include the image URL if available
                    'filing_date': filing_date  # Add the filing date to the result
                })
            except Exception as e:
                print(f"Error extracting patent info: {e}")
                pass
    finally:
        driver.quit()
    return results
@app.route('/')
def home():
    return render_template('index.html')
@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('query')
    page = request.args.get('page', 1, type=int)  
    if not query:
        return jsonify({"error": "Query parameter is required"}), 400
    try:
        # Fetch results based on query and page
        espacenet_results = scrape_espacenet(query, page);
        google_results = scrape_google_patents(query, page);
        combined_results = google_results + espacenet_results
        # Optimize results using GWO
        optimized_results = gwo_optimize_results(combined_results, query)
        return jsonify({
            'results': optimized_results,
            'page': page 
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5044)
