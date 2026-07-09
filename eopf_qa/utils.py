import requests
import urllib
from typing import Dict, Optional, Tuple

def __init__():
    # see warning in https://docs.python.org/3/library/urllib.request.html#module-urllib.request for mac
    os.environ["no_proxy"] = "*"

def check_file_exists(url) -> bool:
    # Checks that a given URL is reachable.

    request = urllib.request.Request(url)
    request.get_method = lambda: 'HEAD'

    try:
        urllib.request.urlopen(request)
        return True
    except urllib.request.HTTPError as err:
        #print(err)
        return False

def fetch_and_parse_file(input_path: str, headers: Optional[Dict] = None) -> Dict:
    """Fetches and parses a JSON file from a URL or local file.

    Given a URL or local file path to a JSON file, this function fetches the file,
    and parses its contents into a dictionary. If the input path is a valid URL, the
    function uses the requests library to download the file, otherwise it opens the
    local file with the json library.

    Args:
        input_path: A string representing the URL or local file path to the JSON file.
        headers: For URLs: HTTP headers to include in the request

    Returns:
        A dictionary containing the parsed contents of the JSON file.

    Raises:
        ValueError: If the input is not a valid URL or local file path.
        requests.exceptions.RequestException: If there is an error while downloading the file.
    """
    try:
        if is_url(input_path):
            resp = requests.get(input_path, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        else:
            with open(input_path) as f:
                data = json.load(f)

        return data
    except (ValueError, requests.exceptions.RequestException) as e:
        raise e
