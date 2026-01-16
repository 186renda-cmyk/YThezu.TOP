import urllib.request
import json
import ssl

def submit_to_indexnow():
    # Configuration
    host = "ythezu.top"
    key = "94f28ee04780468888bc7c96238dc868"
    key_location = f"https://{host}/{key}.txt"
    
    # List of URLs to submit
    # In a production environment, you might want to parse sitemap.xml dynamically
    url_list = [
        f"https://{host}/",
        f"https://{host}/blog/is-youtube-premium-worth-it",
        f"https://{host}/blog/youtube-premium-cheapest-region-guide",
        f"https://{host}/blog/youtube-premium-vs-music-premium",
        f"https://{host}/blog/",
        f"https://{host}/blog/youtube-premium-vs-channel-membership",
        f"https://{host}/blog/how-to-buy-youtube-premium-cheap",
        f"https://{host}/blog/youtube-channel-operation-guide",
        f"https://{host}/support",
        f"https://{host}/privacy"
    ]

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