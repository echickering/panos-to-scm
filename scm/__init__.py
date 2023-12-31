# /project/scm/__init__.py
"""
ISC License

Copyright (c) 2023 Eric Chickering <eric.chickering@gmail.com>

Permission to use, copy, modify, and/or distribute this software for any
purpose with or without fee is hereby granted, provided that the above
copyright notice and this permission notice appear in all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION
OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN
CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

"""
import logging
import time
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

class PanApiHandler:
    BASE_URL = "https://api.sase.paloaltonetworks.com"

    def __init__(self, session):
        self.session = session

    def ensure_valid_token(self):
        """ Ensure the session token is valid. """
        self.session.ensure_valid_token()

    def list_objects(self, endpoint, folder_scope, position, limit=10000):
        """Retrieve a list of objects."""

        self.ensure_valid_token()

        url = f"{self.BASE_URL}/{endpoint}?position={position}&folder={folder_scope}&limit={limit}&offset=0"

        try:
            response = self.session.get(url=url)
        except Exception as err:
            logging.error(f"Error in list_objects: {err}")
            return []  # Return empty list in case of exception

        if response.status_code == 200:
            return response.json().get("data", [])
        else:
            logging.error(f"Error retrieving list: Status Code {response.status_code}, Response: {response.text}")
            return []  # Return empty list in case of non-200 response

    def move_security_rule(self, rule_id, folder, destination, destination_rule=None, rulebase="pre"):
        """Move a security rule to a specified position."""
        endpoint = f"/sse/config/v1/security-rules/{rule_id}:move"
        url = f"{self.BASE_URL}/{endpoint}"
        payload = {
            "destination": destination,
            "rulebase": rulebase
        }
        if destination_rule is not None:
            payload["destination_rule"] = destination_rule

        self.ensure_valid_token()  # Ensure token is valid before making the request

        response = self.session.post(url, json=payload)
        if response.status_code != 200:
            logging.error(f"Error moving rule {rule_id}: {response.text}")
            return False  # Indicates failure
        else:
            logging.info(f"Successfully moved rule {rule_id}")
            return True  # Indicates success

    def get_object(self, endpoint, retries=1, delay=0.5):
        """ Retrieve a specific object from the API. """
        url = f"{self.BASE_URL}{endpoint}"
        for attempt in range(retries + 1):
            try:
                self.ensure_valid_token()
                response = self.session.get(url, timeout=10)
                if response.status_code == 200:
                    return response.json()['data']
                else:
                    logging.error(f"API Error when retrieving object: {response.json()}, Status Code: {response.status_code}")
                    if attempt < retries:
                        time.sleep(delay)
            except Exception as e:
                logging.error(f"Exception occurred when retrieving object: {str(e)}")
                if attempt < retries:
                    time.sleep(delay)

        return []

    def create_object(self, endpoint, item_data, retries=1, delay=0.5):
        """ Create an object via the API. """
        url = f"{self.BASE_URL}{endpoint}"
        # print(url)
        for attempt in range(retries + 1):
            try:
                self.ensure_valid_token()
                response = self.session.post(url, json=item_data, timeout=10)
                # print(item_data)
                if response.status_code == 201:
                    return 'This object created', item_data['name']
                else:
                    error_response = response.json()
                    if response.status_code == 400:
                        if "object already exists" in str(error_response).lower():
                            logging.info(f"Object already exists for '{item_data.get('name', '')}'")
                            return 'This object exists', item_data['name']
                        if "is not a valid reference" in str(error_response).lower():
                            logging.warning(f"Invalid reference in object '{item_data.get('name', '')}'")
                            time.sleep(delay)
                            continue
                        if "max retries exceeded" in str(error_response).lower():
                            logging.warning(f"You might be hitting rate limiter with object '{item_data.get('name', '')}")
                            time.sleep(delay)
                            continue
                        else:
                            logging.error(f"API Error for '{item_data.get('name', '')}': Response: {response.text}, Status Code: {response.status_code}")
                    return 'error creating object', item_data['name'], "Error: Object creation failed"
            except Exception as e:
                logging.error(f"Exception occurred for '{item_data.get('name', '')}': {str(e)}")
                if attempt < retries:
                    time.sleep(delay)
                else:
                    return 'error creating object', item_data['name'], f"Exception: {str(e)}"

        return 'error creating object', item_data['name'], "Failed after retries"

    def create_objects(self, scope, start_index, object_type, data, max_workers, object_name_field='name', extra_query_params=''):
        """ Create multiple objects via the API in parallel. """
        endpoint = f"{object_type}{extra_query_params}&type=container&folder={scope}"
        results = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            print(f'Running with {max_workers} workers.')
            logging.info(f'Running with {max_workers} workers.')
            futures = [executor.submit(self.create_object, endpoint, item_data, retries=2, delay=0.5) for item_data in data[start_index:]]
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                print(result)
                logging.info(result)

        return results

    def update_object(self, endpoint, item_data, retries=1, delay=0.5):
        """ Update an object via the API. """
        # Similar logic to create_object, but using session.put

    def delete_object(self, endpoint, retries=1, delay=0.5):
        """ Delete an object via the API. """
        # Similar logic to get_object, but using session.delete
