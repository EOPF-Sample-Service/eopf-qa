import urllib

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

