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

def get_blog_gid(numeric_id):
    # Ensures ID is in the correct Global format for Shopify GraphQL
    if "gid://" in str(numeric_id):
        return numeric_id
    return f"gid://shopify/Blog/{numeric_id}"

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
    
    # Use formatted ID
    gid = get_blog_gid(blog_id)
    
    try:
        resp = requests.post(url, json={"query": query, "variables": {"blogId": gid}}, headers=headers)
        if resp.status_code != 200:
            print(f"   [Error] Shopify Title Check Failed: {resp.text}")
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
        
        if node and node.get("image") and node["image"].get("url"):
            return node["image"]["url"]
            
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
        
        files = data.get("data", {}).get("fileCreate", {}).get("files", [])
        if files and files[0]:
            return poll_for_image_url(files[0]["id"])
    except Exception as e:
        print(f"   [Exception] Upload failed: {e}")
    return None

# --- AI Logic ---

def generate_topics(count, existing_titles):
    print(f"   Generating {count} Hebrew topics...")
    prompt = (
        f"Generate {count} unique, engaging blog titles in HEBREW for a Running & Fitness blog. "
        "Focus on: Running tips, marathon training, running accessories, and healthy lifestyle. "
        "Rules:\n"
        "1. Output strictly a JSON array of objects.\n"
        "2. Keys: 'title' (Hebrew string), 'image_prompt' (English visual description), 'image_alt' (Hebrew alt text), 'keywords' (list of Hebrew keywords).\n"
        "3. Image Prompts MUST specify: 'professional runner wearing athletic t-shirt/jersey and shorts', 'realistic photo style', 'outdoor setting'.\n"
        "4. Do NOT use these titles: " + ", ".join(list(existing_titles)[:20])
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
    # Enforcing strict clothing rules in the prompt
    safe_prompt = f"A high quality, photorealistic image of a runner wearing a full athletic shirt and shorts. Professional sports photography style. {prompt}"
    try:
        resp = client.images.generate(
            model="dall-e-3",
            prompt=safe_prompt,
            n=1,
            size="1024x1024"
        )
        return resp.data[0].url
    except Exception as e:
        print(f"   [AI Error] Image Generation Failed: {e}")
        return None

# --- Main ---

def main():
    if not os.path.exists("content_calendar.json"):
        with open("content_calendar.json", "w", encoding='utf-8') as f:
            json.dump({"running": []}, f, ensure_ascii=False)

    with open("content_calendar.json", "r", encoding='utf-8') as f:
        calendar = json.load(f)

    if "running" not in calendar:
        calendar["running"] = []

    print("--- Planning for Hopsport Running Blog ---")
    existing = get_existing_titles(BLOG_ID_RUNNING)
    
    new_topics = generate_topics(10, existing)
    
    if not new_topics:
        return

    for topic in new_topics:
        print(f"Processing: {topic['title']}")
        
        openai_url = generate_image(topic['image_prompt'])
        if not openai_url: continue

        shopify_url = upload_image_to_shopify(openai_url)
        if not shopify_url: continue

        entry = {
            "title": topic['title'],
            "keywords": topic.get('keywords', []),
            "image_url": shopify_url,
            "image_alt": topic.get('image_alt', topic['title']),
            "status": "pending"
        }
        calendar['running'].append(entry)
        
        # FIX: ensure_ascii=False ensures Hebrew is readable in the file
        with open("content_calendar.json", "w", encoding='utf-8') as f:
            json.dump(calendar, f, indent=2, ensure_ascii=False)
        
        time.sleep(2)

if __name__ == "__main__":
    main()
