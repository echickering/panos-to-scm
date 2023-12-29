# post_utils6.py

import requests
import os
import time
import json
import logging
from token_utils import obtain_api_token
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

# Global Logging
logging.basicConfig(filename='debug-log.txt', level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')

# Global lock for token refresh
token_refresh_lock = Lock()

def create_object(url, headers, item_data, retries=1, delay=5, client_id=None, client_secret=None, tsg_id=None, token_file=None):
    global token_refresh_lock
    access_token = obtain_api_token(client_id, client_secret, tsg_id, token_file, force_refresh=False)
    headers["Authorization"] = f"Bearer {access_token}"

    for attempt in range(retries + 1):
        try:
            with token_refresh_lock:  
                if token_is_expired(access_token, token_file):
                    print(f"Token expired, refreshing token...")
                    logging.debug("Token expired, refreshing token...")
                    access_token = obtain_api_token(client_id, client_secret, tsg_id, token_file, force_refresh=True)
                    headers["Authorization"] = f"Bearer {access_token}"

            response = requests.post(url, headers=headers, json=item_data, timeout=10)
            if response.status_code == 201:
                return ('This object created', item_data['name'])
            elif response.status_code == 400:
                error_response = response.json()
                error_response_str = str(error_response).lower()

                # Log the actual error response for debugging
                # print(f"Error response for '{item_data.get('name', '')}': {error_response}")

                # Check for "Object Already Exists" error
                if "object already exists" in error_response_str:
                    return ('This object exists', item_data['name'])

                # Invalid reference handling
                if "is not a valid reference" in error_response_str:
                    print(f"Invalid reference in object '{item_data.get('name', '')}'")
                    logging.warning(f"Invalid reference in object '{item_data.get('name', '')} -- we do re-attempt, verify this went through properly'")
                    time.sleep(delay)
                    continue

                # print(f"Error response for '{item_data.get('name', '')}': {error_response}")
                logging.error(f"Error response for '{item_data.get('name', '')}': {error_response}")
                return ('error creating object', item_data['name'], "Error: Object creation failed")
            # Handling other status codes...
        except Exception as e:
            # print(f"Error response for '{item_data.get('name', '')}': {error_response}")
            logging.error(f"Error response for '{item_data.get('name', '')}': {error_response}")
            return ('error creating object', item_data['name'], "Exception occurred")

    return ('error creating object', item_data['name'], "Failed after retries")

def create_objects(scope, start_index, object_type, data, client_id, client_secret, tsg_id, token_file, max_workers, object_name_field='name', extra_query_params=''):
    url = f"https://api.sase.paloaltonetworks.com/sse/config/v1/{object_type}{extra_query_params}type=container&folder={scope}"
    headers = {
        "Content-Type": "application/json",
    }

    # Initialize the access token
    access_token = obtain_api_token(client_id, client_secret, tsg_id, token_file, force_refresh=False)
    headers["Authorization"] = f"Bearer {access_token}"

    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(create_object, url, headers, item_data, retries=2, delay=10, client_id=client_id, client_secret=client_secret, tsg_id=tsg_id, token_file=token_file) for item_data in data[start_index:]]

        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            print(result)
            logging.info(result)

    return results

def refresh_token_if_needed(access_token, client_id, client_secret, tsg_id, token_file):
    # Read the token data from the file
    if os.path.exists(token_file):
        with open(token_file, "r") as f:
            token_data = json.load(f)
    else:
        token_data = {'access_token': None, 'expires_at': 0}

    if token_is_expired(access_token, token_file):  # Corrected to pass both arguments
        access_token = obtain_api_token(client_id, client_secret, tsg_id, token_file, force_refresh=True)
        auth_header = f"Bearer {access_token}"
        return access_token, auth_header
    else:
        return access_token, f"Bearer {access_token}"

def token_is_expired(access_token, token_file):
    # Read the token data from the file
    if os.path.exists(token_file):
        with open(token_file, "r") as f:
            token_data = json.load(f)
            current_time = time.time()
            return current_time > (token_data['expires_at'] - 180)  # 180 seconds buffer
    else:
        return True  # Token file does not exist, assume token is expired


#### Functions to create different types of objects and policies
def create_tag_objects(scope, start_index, tags_data, client_id, client_secret, tsg_id, token_file, max_workers, extra_query_params=''):
    return create_objects(scope, start_index, 'tags?', tags_data, client_id, client_secret, tsg_id, token_file, max_workers=max_workers, extra_query_params=extra_query_params)

def create_url_categories(scope, start_index, url_cat_data, client_id, client_secret, tsg_id, token_file, max_workers, extra_query_params=''):
    return create_objects(scope, start_index, 'url-categories?', url_cat_data, client_id, client_secret, tsg_id, token_file, max_workers=max_workers, extra_query_params=extra_query_params)

def create_url_profiles(scope, start_index, url_profiles_data, client_id, client_secret, tsg_id, token_file, max_workers, extra_query_params=''):
    return create_objects(scope, start_index, 'url-access-profiles?', url_profiles_data, client_id, client_secret, tsg_id, token_file, max_workers=max_workers, extra_query_params=extra_query_params)

def create_vulnerability_profiles(scope, start_index, vulnerability_data, client_id, client_secret, tsg_id, token_file, max_workers, extra_query_params=''):
    return create_objects(scope, start_index, 'vulnerability-protection-profiles?', vulnerability_data, client_id, client_secret, tsg_id, token_file, max_workers=max_workers, extra_query_params=extra_query_params)

def create_spyware_profiles(scope, start_index, spyware_data, client_id, client_secret, tsg_id, token_file, max_workers, extra_query_params=''):
    return create_objects(scope, start_index, 'anti-spyware-profiles?', spyware_data, client_id, client_secret, tsg_id, token_file, max_workers=max_workers, extra_query_params=extra_query_params)

def create_virus_profiles(scope, start_index, virus_data, client_id, client_secret, tsg_id, token_file, max_workers, extra_query_params=''):
    return create_objects(scope, start_index, 'wildfire-anti-virus-profiles?', virus_data, client_id, client_secret, tsg_id, token_file, max_workers=max_workers, extra_query_params=extra_query_params)

def create_profile_group_profiles(scope, start_index, group_data, client_id, client_secret, tsg_id, token_file, max_workers, extra_query_params=''):
    return create_objects(scope, start_index, 'profile-groups?', group_data, client_id, client_secret, tsg_id, token_file, max_workers=max_workers, extra_query_params=extra_query_params)

def create_address_objects(scope, start_index, addresses_data, client_id, client_secret, tsg_id, token_file, max_workers, extra_query_params=''):
    return create_objects(scope, start_index, 'addresses?', addresses_data, client_id, client_secret, tsg_id, token_file, max_workers=max_workers, extra_query_params=extra_query_params)

def create_address_group_objects(scope, start_index, address_groups_data, client_id, client_secret, tsg_id, token_file, max_workers, extra_query_params=''):
    return create_objects(scope, start_index, 'address-groups?', address_groups_data, client_id, client_secret, tsg_id, token_file, max_workers=max_workers, extra_query_params=extra_query_params)

def create_service_objects(scope, start_index, services_data, client_id, client_secret, tsg_id, token_file, max_workers, extra_query_params=''):
    return create_objects(scope, start_index, 'services?', services_data, client_id, client_secret, tsg_id, token_file, max_workers=max_workers, extra_query_params=extra_query_params)

def create_service_group_objects(scope, start_index, services_group_data, client_id, client_secret, tsg_id, token_file, max_workers, extra_query_params=''):
    return create_objects(scope, start_index, 'service-groups?', services_group_data, client_id, client_secret, tsg_id, token_file, max_workers=max_workers, extra_query_params=extra_query_params)

def create_edl_objects(scope, start_index, edl_data, client_id, client_secret, tsg_id, token_file, max_workers, extra_query_params=''):
    return create_objects(scope, start_index, 'external-dynamic-lists?', edl_data, client_id, client_secret, tsg_id, token_file, max_workers=max_workers, extra_query_params=extra_query_params)

def create_app_filter_objects(scope, start_index, app_filter_data, client_id, client_secret, tsg_id, token_file, max_workers, extra_query_params=''):
    return create_objects(scope, start_index, 'application-filters?', app_filter_data, client_id, client_secret, tsg_id, token_file, max_workers=max_workers, extra_query_params=extra_query_params)

def create_app_group_objects(scope, start_index, app_group_data, client_id, client_secret, tsg_id, token_file, max_workers, extra_query_params=''):
    return create_objects(scope, start_index, 'application-groups?', app_group_data, client_id, client_secret, tsg_id, token_file, max_workers=max_workers, extra_query_params=extra_query_params)

def create_security_rules(scope, start_index, security_rules_data, client_id, client_secret, tsg_id, token_file, max_workers, extra_query_params=''):
    return create_objects(scope, start_index, 'security-rules?', security_rules_data, client_id, client_secret, tsg_id, token_file, max_workers=max_workers, extra_query_params=extra_query_params)

def create_nat_rules(scope, start_index, nat_rules_data, client_id, client_secret, tsg_id, token_file, max_workers, extra_query_params=''):
    return create_objects(scope, start_index, 'nat-rules?', nat_rules_data, client_id, client_secret, tsg_id, token_file, max_workers=max_workers, extra_query_params=extra_query_params)