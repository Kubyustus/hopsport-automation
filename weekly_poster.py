import os
import json
import requests
import datetime
from openai import OpenAI

# --- Configuration ---
SHOP_DOMAIN = os.environ["SHOP_DOMAIN"]
ACCESS_TOKEN = os.environ["SHOPIFY_TOKEN"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
BLOG_ID_RUNNING = os.environ["BLOG_ID_RUNNING"]
AUTHOR_NAME = os.environ.get("AUTHOR_NAME", "צוות הופספורט")

client = OpenAI(api_key=OPENAI_API_KEY)

# --- PRODUCTS (Hardcoded as requested) ---
# PLEASE UPDATE THE 'image' FIELDS WITH REAL LINKS FROM YOUR STORE IF POSSIBLE
PRODUCTS = [
    {
        "title": "הופספורט - שרוול זרוע ריצה לסמארטפון (מארז 2 יחידות)",
        "url": "https://hopsport.co/products/%D7%94%D7%95%D7%A4%D7%A1%D7%A4%D7%95%D7%A8%D7%98-%D7%A9%D7%A8%D7%95%D7%95%D7%9C-%D7%96%D7%A8%D7%95%D7%A2-%D7%A8%D7%99%D7%A6%D7%94-%D7%9C%D7%A1%D7%9E%D7%90%D7%A8%D7%98%D7%A4%D7%95%D7%9F-%D7%94%D7%93%D7%92%D7%9D-%D7%94%D7%9E%D7%A9%D7%95%D7%A4%D7%A8-%D7%9E%D7%90%D7%A8%D7%96-2-%D7%99%D7%97%D7%99%D7%93%D7%95%D7%AA",
        "image": "https://cdn.shopify.com/s/files/1/0533/2089/files/placeholder.jpg" # <--- PASTE REAL IMAGE URL HERE
    },
    {
        "title": "הופספורט - שרוול זרוע ריצה לסמארטפון (מארז 3 יחידות)",
        "url": "https://hopsport.co/products/%D7%94%D7%95%D7%A4%D7%A1%D7%A4%D7%95%D7%A8%D7%98-%D7%A9%D7%A8%D7%95%D7%95%D7%9C-%D7%96%D7%A8%D7%95%D7%A2-%D7%A8%D7%99%D7%A6%D7%94-%D7%9C%D7%A1%D7%9E%D7%90%D7%A8%D7%98%D7%A4%D7%95%D7%9F-%D7%94%D7%93%D7%92%D7%9D-%D7%94%D7%9E%D7%A9%D7%95%D7%A4%D7%A8-%D7%9E%D7%90%D7%A8%D7%96-%D7%A9%D7%9C-3-%D7%99%D7%97%D7%99%D7%93%D7%95%D7%AA",
        "image": "https://cdn.shopify.com/s/files/1/0533/2089/files/placeholder.jpg" # <--- PASTE REAL IMAGE URL HERE
    }
]

def generate_article_body(title, keywords):
    print(f"   Writing content in Hebrew for: {title}")
    prompt = (
        f"Write a comprehensive SEO blog post in HEBREW (עברית).\n"
        f"Title: {title}\n"
        f"Keywords: {', '.join(keywords)}\n\n"
        "Rules:\n"
        "1. **Language:** Hebrew ONLY.\n"
        "2. **Structure:** Use <h2> and <h3> tags. Start with an engaging summary.\n"
        "3. **Tone:** Energetic, motivating, professional fitness advice.\n"
        "4. **Brand:** Mention 'הופספורט' (Hopsport) naturally as a top brand for running accessories.\n"
        "5. **Format:** HTML Body only (no <html> tags). Use bullet points where appropriate.\n"
        "6. **No Images:** Do not insert <img> tags in the text."
    )
    
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )
    return resp.choices[0].message.content.strip()

def get_product_widget():
    # Returns HTML for the 2 specific products
    p1, p2 = PRODUCTS[0], PRODUCTS[1]
    
    return f"""
    <div style="margin: 40px auto; max-width: 600px; padding: 20px; border: 1px solid #eee; border-radius: 10px; text-align: center; background-color: #f9f9f9; direction: rtl;">
        <h3 style="margin-bottom: 20px; color: #333;">המוצרים המומלצים שלנו לריצה 🏃‍♂️</h3>
        <div style="display: flex; justify-content: center; gap: 20px; flex-wrap: wrap;">
            <div style="flex: 1; min-width: 200px;">
                <a href="{p1['url']}" style="text-decoration: none; color: #333;">
                    <img src="{p1['image']}" alt="{p1['title']}" style="width: 100%; border-radius: 8px; margin-bottom: 10px;">
                    <div style="font-weight: bold;">{p1['title']}</div>
                </a>
            </div>
            <div style="flex: 1; min-width: 200px;">
                <a href="{p2['url']}" style="text-decoration: none; color: #333;">
                    <img src="{p2['image']}" alt="{p2['title']}" style="width: 100%; border-radius: 8px; margin-bottom: 10px;">
                    <div style="font-weight: bold;">{p2['title']}</div>
                </a>
            </div>
        </div>
    </div>
    """

def publish_article(title, body, image_url, tags):
    url = f"https://{SHOP_DOMAIN}/admin/api/2024-01/graphql.json"
    headers = {"X-Shopify-Access-Token": ACCESS_TOKEN}
    
    mutation = """
    mutation CreateArticle($article: ArticleCreateInput!) {
      articleCreate(article: $article) {
        article { id }
        userErrors { field message }
      }
    }
    """
    
    variables = {
        "article": {
            "blogId": BLOG_ID_RUNNING,
            "title": title,
            "author": {"name": AUTHOR_NAME},
            "body": body,
            "image": {"url": image_url, "altText": title},
            "tags": tags,
            "isPublished": True
        }
    }
    
    resp = requests.post(url, json={"query": mutation, "variables": variables}, headers=headers)
    return resp.json()

def main():
    try:
        with open("content_calendar.json", "r") as f:
            calendar = json.load(f)
    except FileNotFoundError:
        print("Calendar not found. Run planner first.")
        return

    # Find next pending article
    article = next((a for a in calendar['running'] if a["status"] == "pending"), None)
    
    if not article:
        print("No pending articles.")
        return

    print(f"Publishing: {article['title']}")
    
    # Generate content
    body_html = generate_article_body(article['title'], article['keywords'])
    
    # Add Widget (after first paragraph or at end)
    widget = get_product_widget()
    if "</p>" in body_html:
        body_html = body_html.replace("</p>", f"</p>{widget}", 1)
    else:
        body_html += widget

    # Publish
    res = publish_article(article['title'], body_html, article['image_url'], article['keywords'])
    
    if res.get('data', {}).get('articleCreate', {}).get('article'):
        print("SUCCESS! Article is live.")
        article["status"] = "published"
        article["published_at"] = str(datetime.date.today())
        
        with open("content_calendar.json", "w") as f:
            json.dump(calendar, f, indent=2)
    else:
        print(f"FAILED: {res}")

if __name__ == "__main__":
    main()
