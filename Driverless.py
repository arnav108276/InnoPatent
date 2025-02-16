
from flask import Flask, request, jsonify, render_template
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import logging
import time
import os

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
    chrome_options.add_argument('--no-sandbox')

    # Automatically fetch and setup the right ChromeDriver version
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

# Scrape Google Patents data
def scrape_google_patents(query):
    results = []
    driver = get_chrome_driver()

    try:
        for page_num in range(1, 2):  # Adjust page range as needed
            url = f"https://patents.google.com/?q={query}&oq={query}&page={page_num}"
            driver.get(url)
            time.sleep(2)  # Allow page to load
            result_items = driver.find_elements(By.CSS_SELECTOR, 'search-result-item')
            
            for item in result_items:
                try:
                    title = item.find_element(By.CSS_SELECTOR, '#htmlContent').text.strip()
                    description = item.find_element(By.CSS_SELECTOR, '#htmlContent').text.strip()
                    patent_id = item.find_element(By.CSS_SELECTOR, '[data-proto="OPEN_PATENT_PDF"]').text.strip()
                    authors = item.find_elements(By.CSS_SELECTOR, '.style-scope.search-result-item')[0].text.strip()
                    patent_url = f"https://patents.google.com/patent/{patent_id}/en"
                    image_url = item.find_element(By.CSS_SELECTOR, 'img').get_attribute('src')

                    results.append({
                        'title': title,
                        'description': description,
                        'authors': authors,
                        'id': patent_id,
                        'url': patent_url,
                        'image': image_url  # Include the image URL in the result
                    })
                except Exception as e:
                    print(f"Error extracting patent info: {e}")
                    pass
    finally:
        driver.quit()
    return results

# Scrape Espacenet data and map to Google Patents
def scrape_espacenet(query):
    results = []
    driver = get_chrome_driver()

    try:
        for page_num in range(1, 2):  # Adjust page range as needed
            url = f"https://worldwide.espacenet.com/patent/search?q={query}&page={page_num}"
            driver.get(url)
            time.sleep(2)  # Allow page to load
            items = driver.find_elements(By.CSS_SELECTOR, 'article.item--wSceB4di')

            for item in items:
                try:
                    title = item.find_element(By.CSS_SELECTOR, 'header.h2--2VrrSjFb').text.strip()
                    description = item.find_element(By.CSS_SELECTOR, '.copy-text--uk738M73').text.strip()
                    patent_id = item.find_element(By.TAG_NAME, 'a').get_attribute('href').split('/')[-1]
                    patent_url = f"https://patents.google.com/patent/{patent_id}/en"
                    image_url = item.find_element(By.CSS_SELECTOR, 'img').get_attribute('src') if item.find_element(By.CSS_SELECTOR, 'img') else None

                    results.append({
                        'title': title,
                        'description': description,
                        'id': patent_id,
                        'url': patent_url,
                        'image': image_url  # Include the image URL in the result if available
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
    if not query:
        return jsonify({"error": "Query parameter is required"}), 400

    google_results = scrape_google_patents(query)
    espacenet_results = scrape_espacenet(query)
    combined_results = google_results + espacenet_results
    optimized_results = gwo_optimize_results(combined_results, query)

    return jsonify({'results': optimized_results})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5013))
    app.run(debug=True, host='0.0.0.0', port=port)
