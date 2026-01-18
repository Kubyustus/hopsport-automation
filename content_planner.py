import os
import json
import time
import requests
from openai import OpenAI

# --- Configuration ---
SHOP_DOMAIN = os.environ["SHOP_DOMAIN"]
ACCESS_TOKEN = os.environ["SHOPIFY_TOKEN"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
BLOG_ID_RUNNING = os.environ["BLOG_ID_RUNNING"]

client = OpenAI(api_key=OPENAI_API_KEY)

# --- Helpers ---

def get_existing_titles(blog_id):
    query = """
    query getArticles($blogId: ID!) {
      blog(id: $blogId) {
        articles(first: 100, reverse: true) {
          edges { node { title } }
        }
      }
    }
    """
    url = f"https://{SHOP_DOMAIN}/admin/api/2024-01/graphql.json"
    headers = {"X-Shopify-Access-Token": ACCESS_TOKEN, "Content-Type": "application/json"}
    
    try:
        resp = requests.post(url, json={"query": query, "variables": {"blogId": blog_id}}, headers=headers)
        if resp.status_code != 200:
            print(f"   [Error] Shopify Title Check Failed (Status {resp.status_code}): {resp.text}")
            return set()
        data = resp.json()
        edges = data.get("data", {}).get("blog", {}).get("articles", {}).get("edges", [])
        return {edge["node"]["title"].strip().lower() for edge in edges}
    except Exception as e:
        print(f"   [Error] Exception checking titles: {e}")
        return set()

def poll_for_image_url(file_id):
    query = """
    query getFile($id: ID!) {
      node(id: $id) {
        ... on MediaImage {
          image { url }
          status
        }
      }
    }
    """
    url = f"https://{SHOP_DOMAIN}/admin/api/2024-01/graphql.json"
    headers = {"X-Shopify-Access-Token": ACCESS_TOKEN, "Content-Type": "application/json"}
    
    for attempt in range(12): 
        time.sleep(5) 
        resp = requests.post(url, json={"query": query, "variables": {"id": file_id}}, headers=headers)
        data = resp.json()
        node = data.get("data", {}).get("node", {})
        
        # Debug: Print status if waiting
        status = node.get("status", "UNKNOWN") if node else "UNKNOWN"
        if status != "READY":
             print(f"   ... Image status: {status} (Attempt {attempt+1})")

        if node and node.get("image") and node["image"].get("url"):
            return node["image"]["url"]
            
    print("   [Error] Image timed out processing on Shopify.")
    return None

def upload_image_to_shopify(image_url):
    print("   -> Uploading image to Shopify...")
    query = """
    mutation fileCreate($files: [FileCreateInput!]!) {
      fileCreate(files: $files) {
        files { ... on MediaImage { id } }
        userErrors { field message }
      }
    }
    """
    variables = {"files": [{"originalSource": image_url, "contentType": "IMAGE"}]}
    endpoint = f"https://{SHOP_DOMAIN}/admin/api/2024-01/graphql.json"
    headers = {"X-Shopify-Access-Token": ACCESS_TOKEN, "Content-Type": "application/json"}
    
    try:
        resp = requests.post(endpoint, json={"query": query, "variables": variables}, headers=headers)
        data = resp.json()
        
        # DEBUG: Print exact error if it fails
        if "errors" in data:
            print(f"   [SHOPIFY API ERROR]: {data['errors']}")
            return None
            
        file_create = data.get("data", {}).get("fileCreate", {})
        if file_create.get("userErrors"):
            print(f"   [SHOPIFY USER ERROR]: {file_create['userErrors']}")
            return None

        files = file_create.get("files", [])
        if files and files[0]:
            return poll_for_image_url(files[0]["id"])
        else:
            print(f"   [Error] No file ID returned. Response: {data}")
            
    except Exception as e:
        print(f"   [Exception] Upload failed: {e}")
    return None

# --- AI Logic ---

def generate_topics(count, existing_titles):
    print(f"   Generating {count} Hebrew topics...")
    prompt = (
        f"Generate {count} unique, engaging blog titles in HEBREW for a Running & Fitness blog. "
        "Focus on: Running tips, marathon training, running accessories (specifically phone armbands), and healthy lifestyle. "
        "Rules:\n"
        "1. Output strictly a JSON array of objects.\n"
        "2. Keys: 'title' (Hebrew string), 'image_prompt' (English visual description for DALL-E), 'keywords' (list of Hebrew keywords).\n"
        "3. Do NOT use these titles: " + ", ".join(list(existing_titles)[:20])
    )
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        return json.loads(resp.choices[0].message.content.strip().replace("```json", "").replace("```", ""))
    except Exception as e:
        print(f"   [AI Error] Topic Generation Failed: {e}")
        return []

def generate_image(prompt):
    print("   -> Generating AI image...")
    try:
        resp = client.images.generate(
            model="dall-e-3",
            prompt=f"A high quality, photorealistic image related to running and fitness. {prompt}",
            n=1,
            size="1024x1024"
        )
        return resp.data[0].url
    except Exception as e:
        print(f"   [AI Error] Image Generation Failed: {e}")
        return None

# --- Main ---

def main():
    # Ensure file exists
    if not os.path.exists("content_calendar.json"):
        with open("content_calendar.json", "w") as f:
            json.dump({"running": []}, f)

    with open("content_calendar.json", "r") as f:
        calendar = json.load(f)

    # Init key if missing
    if "running" not in calendar:
        calendar["running"] = []

    # Configuration for the single blog
    blog_config = {
        "key": "running",
        "id": BLOG_ID_RUNNING
    }

    print("--- Planning for Hopsport Running Blog ---")
    existing = get_existing_titles(blog_config['id'])
    
    # Generate 10 topics
    new_topics = generate_topics(10, existing)
    
    if not new_topics:
        print("No topics generated. Exiting.")
        return

    for topic in new_topics:
        print(f"Processing: {topic['title']}")
        
        # 1. AI Image
        openai_url = generate_image(topic['image_prompt'])
        if not openai_url:
            print("   [Skip] Image generation failed.")
            continue

        # 2. Upload to Shopify
        shopify_url = upload_image_to_shopify(openai_url)
        if not shopify_url:
            print("   [Skip] Shopify upload failed.")
            continue

        entry = {
            "title": topic['title'],
            "keywords": topic.get('keywords', []),
            "image_url": shopify_url,
            "status": "pending"
        }
        calendar['running'].append(entry)
        print("   [Success] Saved to calendar.")
        
        # Save after every successful item
        with open("content_calendar.json", "w") as f:
            json.dump(calendar, f, indent=2)
        
        time.sleep(2)

if __name__ == "__main__":
    main()
