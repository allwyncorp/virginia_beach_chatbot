"""
Advanced Data Ingestion Lambda for crawling Virginia Beach website
"""
import json
import os
import re
from datetime import datetime
from urllib.parse import urljoin, urlparse
import boto3
import requests
from bs4 import BeautifulSoup

# Initialize AWS S3 client
s3_client = boto3.client('s3', region_name=os.environ.get('AWS_REGION'))
BUCKET_NAME = os.environ.get('PROCESSED_DATA_BUCKET')
START_URL = 'https://www.virginiabeach.gov/'
MAX_PAGES_TO_CRAWL = 50  # Safety limit to avoid excessive crawling


def handler(event, context):
    """Main Lambda handler function"""
    print(f'Advanced Data Ingestion Lambda triggered: {json.dumps(event, indent=2)}')
    
    urls_to_crawl = [START_URL]
    visited_urls = set()
    pages_crawled = 0

    while urls_to_crawl and pages_crawled < MAX_PAGES_TO_CRAWL:
        current_url = urls_to_crawl.pop(0)

        if current_url in visited_urls:
            continue

        try:
            print(f'Crawling: {current_url}')
            visited_urls.add(current_url)
            pages_crawled += 1

            response = requests.get(current_url, timeout=10)
            response.raise_for_status()
            html = response.text
            soup = BeautifulSoup(html, 'html.parser')

            # --- Extract content and save to S3 ---
            title = soup.find('title')
            title_text = title.get_text() if title else ''
            
            body = soup.find('body')
            raw_text = body.get_text() if body else ''
            cleaned_text = re.sub(r'\s+', ' ', raw_text).strip()

            document = {
                'title': title_text,
                'url': current_url,
                'publish_date': datetime.now().isoformat(),
                'content': cleaned_text,
            }
            
            # Create a safe filename from the URL
            url_path = urlparse(current_url).path.replace('/', '_')
            if not url_path or url_path == '_':
                url_path = 'homepage'
            key = f'vb-kb/processed/{url_path}.json'

            s3_client.put_object(
                Bucket=BUCKET_NAME,
                Key=key,
                Body=json.dumps(document),
                ContentType='application/json',
            )
            print(f'Successfully stored content from {current_url} to s3://{BUCKET_NAME}/{key}')

            # --- Find and queue new links ---
            for link in soup.find_all('a', href=True):
                href = link['href']
                try:
                    absolute_url = urljoin(START_URL, href)
                    # Only crawl pages within the same domain and haven't been visited
                    if absolute_url.startswith(START_URL) and absolute_url not in visited_urls:
                        urls_to_crawl.append(absolute_url)
                except Exception as url_error:
                    # Ignore invalid URLs
                    pass

        except Exception as error:
            print(f'Failed to crawl {current_url}: {str(error)}')

    print(f'Crawling finished. Visited {pages_crawled} pages.')
    return {
        'statusCode': 200,
        'body': json.dumps({'message': f'Ingestion successful. Crawled {pages_crawled} pages.'}),
    } 