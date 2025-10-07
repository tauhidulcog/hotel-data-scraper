import json
import random
from time import sleep

from driver_manager import DriverManager
import pandas as pd
from datetime import datetime
import re


def generate_payload(plugin_state, property_id, page_index=0, page_size=10):
    return [
        {
            "operationName": "PWAReviewsSortingAndFiltersQuery",
            "variables": {
                "productIdentifier": {
                    "id": str(property_id),
                    "type": "PROPERTY_ID",
                    "travelSearchCriteria": {
                        "property": {
                            "primary": {
                                "dateRange": None,
                                "rooms": [{"adults": 2}],
                                "destination": {"regionId": ""},
                            },
                            "secondary": {
                                "selections": [
                                    {"id": "sortBy", "value": "urn:expediagroup:taxonomies:core:#e9f32feb-5946-4b19-a6f2-8206edc7a130"},
                                    {"id": "searchTerm", "value": ""},
                                    {"id": "travelerType", "value": ""},
                                ],
                                "counts": [
                                    {"id": "pageIndex", "value": page_index},
                                    {"id": "size", "value": page_size},
                                ],
                            },
                        }
                    },
                },
                "context": {
                    "siteId": plugin_state['context']['context']['site']['id'],
                    "locale": plugin_state['context']['context']['locale'],
                    "eapid": plugin_state['context']['context']['site']['eapid'],
                    "tpid": plugin_state['context']['context']['site']['tpid'],
                    "currency": plugin_state['context']['context']['currency'],
                    "device": {
                        "type": "DESKTOP"
                    },
                    "identity": {
                        "duaid": plugin_state['context']['context']['deviceId'],
                        "authState": "ANONYMOUS"
                    },
                    "privacyTrackingState": "CAN_TRACK"
                }
            },
            "extensions": {
                "persistedQuery": {
                    "version": 1,
                    "sha256Hash": "6ef916a9f1758506bd39254623a4704123d75898667a06ca7b2c216cf22ee061",
                }
            },
        }
    ]

def fetch_reviews_data(driver, property_id, page_index=0, page_size=10):
    url = 'https://www.expedia.com/graphql'
    plugin_state = driver.execute_script("return window.__PLUGIN_STATE__ || null;")
    if not plugin_state['context']['context']['site'].get('id'):
        sleep(random.uniform(100, 180))
        plugin_state = driver.execute_script("return window.__PLUGIN_STATE__ || null;")
    
    payload = generate_payload(plugin_state, property_id, page_index, page_size)
    headers = {
        "Content-Type": "application/json",
        "client-info": plugin_state['apollo']['clientInfo']
    }
    script = """
        const url = arguments[0];
        const body = arguments[1];
        const headers = arguments[2];
        const callback = arguments[3];
        fetch(url, {
          method: "POST",
          credentials: "include",
          headers: headers,
          body: JSON.stringify(body)
        }).then(r => r.json())
          .then(data => callback(JSON.stringify(data)))
          .catch(e => callback(JSON.stringify({error: String(e)})));
    """

    resp = driver.execute_async_script(script, url, payload, headers)
    
    try:
        parsed_response = json.loads(resp)
        return parsed_response
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}")
        print(f"Response: {resp[:500]}...")  # Print first 500 chars for debugging
        return []


def parse_review_data(review):
    parsed_data = {
        'review_text': None,
        'rating': None,
        'author_name': None,
        'timestamp': None
    }
    
    if review.get('review'):
        review_data = review['review']
        if review_data.get('__typename') == 'ReviewSection' and review_data.get('text'):
            parsed_data['review_text'] = review_data['text']

    if review.get('summary'):
        summary = review['summary']
        
        if summary.get('primary'):
            primary = summary['primary']
            if '/' in primary:
                rating_part = primary.split('/')[0].strip()
                parsed_data['rating'] = rating_part
        
        if summary.get('secondary'):
            parsed_data['author_name'] = summary['secondary']
        
        if summary.get('supportingMessages') and isinstance(summary['supportingMessages'], list):
            for message in summary['supportingMessages']:
                if message.get('text'):
                    text = message['text']
                    try:
                        for date_format in ["%b %d, %Y", "%B %d, %Y", "%m/%d/%Y", "%Y-%m-%d"]:
                            try:
                                parsed_date = datetime.strptime(text, date_format)
                                parsed_data['timestamp'] = parsed_date.strftime("%Y-%m-%d")
                                break
                            except ValueError:
                                continue
                        else:
                            if re.search(r'\b\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}\b|\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2},?\s+\d{2,4}\b', text, re.IGNORECASE):
                                parsed_data['timestamp'] = text
                    except Exception:
                        continue
                    
                    if parsed_data['timestamp']:
                        break
    
    return parsed_data



if __name__ == "__main__":
    with DriverManager() as driver:
        hotel_url = 'https://www.expedia.com/Salem-Hotels-The-Artisan-At-Tuscan-Village.h96727634.Hotel-Information'
        property_id = hotel_url.split('.h')[1].split('.')[0]
        driver.get(hotel_url)
        page_index = -1
        page_size = 50
        has_next_page = True
        review_data = []
        cutoff_date = datetime.strptime("2023-01-01", "%Y-%m-%d")
        cutoff_reached = False

        while has_next_page and not cutoff_reached:
            has_next_page = False
            page_index += 1
            response = fetch_reviews_data(driver, property_id=property_id, page_index=page_index, page_size=page_size)
            
            if not isinstance(response, list):
                response = [response]
            
            for item in response:
                if not isinstance(item, dict):
                    print(f"Warning: Expected dict but got {type(item)}: {item}")
                    continue
                    
                if (
                        item.get('data') and item['data'].get('productReviewDetails')
                        and item['data']['productReviewDetails'].get('reviews')
                        and item['data']['productReviewDetails']['reviews'].get('details')
                ):
                    review_details = item['data']['productReviewDetails']['reviews']['details']

                    for review in review_details:
                        parsed_review = parse_review_data(review)
                        
                        if parsed_review['timestamp']:
                            try:
                                if '/' in parsed_review['timestamp'] or '-' in parsed_review['timestamp']:
                                    review_date = datetime.strptime(parsed_review['timestamp'], "%Y-%m-%d")
                                else:
                                    for date_format in ["%b %d, %Y", "%B %d, %Y", "%m/%d/%Y"]:
                                        try:
                                            review_date = datetime.strptime(parsed_review['timestamp'], date_format)
                                            break
                                        except ValueError:
                                            continue
                                    else:
                                        review_data.append(parsed_review)
                                        continue
                                
                                if review_date < cutoff_date:
                                    print(f"Reached cutoff date. Stopping at review from {parsed_review['timestamp']}")
                                    cutoff_reached = True
                                    break
                                
                            except ValueError:
                                # If date parsing fails, add the review anyway
                                pass
                        
                        review_data.append(parsed_review)
                    
                    if cutoff_reached:
                        break
                    
                    pagination = item['data']['productReviewDetails']['reviews'].get('pagination')
                    if (
                            pagination
                            and pagination.get('button')
                            and pagination['button'].get('primary')
                    ):
                        has_next_page = pagination['button']['primary'] == 'More reviews'
                    
                    if not has_next_page or cutoff_reached:
                        break
                if not has_next_page or cutoff_reached:
                    break
            print(f"Fetched page {page_index} with {len(review_details)} reviews. Total collected: {len(review_data)}")
            if not has_next_page or cutoff_reached:
                break              

            sleep(random.uniform(5, 15))

        df = pd.DataFrame(review_data)
        df.to_csv('./files/stonebridge/fd920788-1a46-47e4-a733-61917a914a91_expedia_reviews.csv', index=False)
        print(f"Saved {len(review_data)} reviews to ./files/stonebridge/fd920788-1a46-47e4-a733-61917a914a91_expedia_reviews.csv")