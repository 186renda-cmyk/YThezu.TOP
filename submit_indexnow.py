import urllib.request
import json
import ssl
import xml.etree.ElementTree as ET
import os

def get_urls_from_sitemap(sitemap_path):
    """Parse local sitemap.xml to extract URLs."""
    urls = []
    try:
        if not os.path.exists(sitemap_path):
            print(f"Warning: Sitemap not found at {sitemap_path}")
            return []

        tree = ET.parse(sitemap_path)
        root = tree.getroot()
        
        # Handle the default namespace in sitemap.xml
        # Standard sitemap namespace is usually http://www.sitemaps.org/schemas/sitemap/0.9
        namespace = ''
        if '}' in root.tag:
            namespace = root.tag.split('}')[0] + '}'
            
        for url in root.findall(f'{namespace}url'):
            loc = url.find(f'{namespace}loc')
            if loc is not None and loc.text:
                urls.append(loc.text.strip())
        
        print(f"Found {len(urls)} URLs in sitemap.")
        return urls
    except Exception as e:
        print(f"Error parsing sitemap: {e}")
        return []

def submit_to_indexnow():
    # Configuration
    host = "ythezu.top"
    key = "94f28ee04780468888bc7c96238dc868"
    key_location = f"https://{host}/{key}.txt"
    
    # Get directory of current script to locate sitemap.xml
    current_dir = os.path.dirname(os.path.abspath(__file__))
    sitemap_path = os.path.join(current_dir, "sitemap.xml")
    
    # Get URLs from sitemap
    print(f"Reading sitemap from: {sitemap_path}")
    url_list = get_urls_from_sitemap(sitemap_path)
    
    if not url_list:
        print("No URLs found to submit. Exiting.")
        return

    # IndexNow API Endpoint (Bing is a major provider for IndexNow)
    endpoint = "https://api.indexnow.org/indexnow"

    # Prepare the payload
    data = {
        "host": host,
        "key": key,
        "keyLocation": key_location,
        "urlList": url_list
    }

    json_data = json.dumps(data).encode('utf-8')

    # Create request
    req = urllib.request.Request(
        endpoint, 
        data=json_data, 
        headers={'Content-Type': 'application/json; charset=utf-8'}
    )

    try:
        # Create a context that doesn't verify certificates (optional, depends on env)
        # context = ssl._create_unverified_context()
        
        with urllib.request.urlopen(req) as response:
            status_code = response.getcode()
            response_body = response.read().decode('utf-8')
            
            print(f"Submission Status Code: {status_code}")
            if status_code == 200 or status_code == 202:
                print("✅ Successfully submitted URLs to IndexNow!")
                print("Submitted URLs:")
                for url in url_list:
                    print(f" - {url}")
            else:
                print(f"❌ Submission failed. Response: {response_body}")

    except urllib.error.HTTPError as e:
        print(f"❌ HTTP Error: {e.code} - {e.reason}")
        print(e.read().decode('utf-8'))
    except urllib.error.URLError as e:
        print(f"❌ URL Error: {e.reason}")
    except Exception as e:
        print(f"❌ An error occurred: {str(e)}")

if __name__ == "__main__":
    print("Starting IndexNow submission...")
    submit_to_indexnow()
