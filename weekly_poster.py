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

# --- PRODUCTS (Hardcoded) ---
PRODUCTS = [
    {
        "title": "הופספורט - שרוול זרוע ריצה לסמארטפון (מארז 2 יחידות)",
        "url": "https://hopsport.co/products/%D7%94%D7%95%D7%A4%D7%A1%D7%A4%D7%95%D7%A8%D7%98-%D7%A9%D7%A8%D7%95%D7%95%D7%9C-%D7%96%D7%A8%D7%95%D7%A2-%D7%A8%D7%99%D7%A6%D7%94-%D7%9C%D7%A1%D7%9E%D7%90%D7%A8%D7%98%D7%A4%D7%95%D7%9F-%D7%94%D7%93%D7%92%D7%9D-%D7%94%D7%9E%D7%A9%D7%95%D7%A4%D7%A8-%D7%9E%D7%90%D7%A8%D7%96-2-%D7%99%D7%97%D7%99%D7%93%D7%95%D7%AA",
        "image": "https://hopsport.co/cdn/shop/products/main2units_2_1080x1080.jpg" 
    },
    {
        "title": "הופספורט - שרוול זרוע ריצה לסמארטפון (מארז 3 יחידות)",
        "url": "https://hopsport.co/products/%D7%94%D7%95%D7%A4%D7%A1%D7%A4%D7%95%D7%A8%D7%98-%D7%A9%D7%A8%D7%95%D7%95%D7%9C-%D7%96%D7%A8%D7%95%D7%A2-%D7%A8%D7%99%D7%A6%D7%94-%D7%9C%D7%A1%D7%9E%D7%90%D7%A8%D7%98%D7%A4%D7%95%D7%9F-%D7%94%D7%93%D7%92%D7%9D-%D7%94%D7%9E%D7%A9%D7%95%D7%A4%D7%A8-%D7%9E%D7%90%D7%A8%D7%96-%D7%A9%D7%9C-3-%D7%99%D7%97%D7%99%D7%93%D7%95%D7%AA",
        "image": "https://hopsport.co/cdn/shop/products/main-pack-hopsport_720x720.jpg"
    }
]

def get_blog_gid(numeric_id):
    # Fixes the "Invalid Global ID" error automatically
    if "gid://" in str(numeric_id):
        return numeric_id
    return f"gid://shopify/Blog/{numeric_id}"

def generate_article_body(title, keywords):
    print(f"   Writing content in Hebrew for: {title}")
    prompt = (
        f"Write a comprehensive SEO blog post in HEBREW (עברית).\n"
        f"Title: {title}\n"
        f"Keywords: {', '.join(keywords)}\n\n"
        "Rules:\n"
        "1. **Language:** Hebrew ONLY.\n"
        "2. **Structure:** Wrap the entire output in <div dir='rtl' style='text-align: right;'>. Use <h2> and <h3> tags.\n"
        "3. **Tone:** Energetic, motivating, professional fitness advice.\n"
        "4. **Brand:** Mention 'הופספורט' (Hopsport) naturally.\n"
        "5. **Output:** Return HTML body content only. Do NOT use <html>, <head>, or <img> tags in the text."
    )
    
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )
    return resp.choices[0].message.content.strip()

def get_product_widget():
    p1, p2 = PRODUCTS[0], PRODUCTS[1]
    
    return f"""
    <div dir="rtl" style="margin: 40px auto; max-width: 600px; padding: 20px; border: 1px solid #eee; border-radius: 10px; text-align: center; background-color: #f9f9f9;">
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

def publish_article(title, body, image_url, image_alt, tags):
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
    
    # Use the helper to ensure ID is correct
    blog_gid = get_blog_gid(BLOG_ID_RUNNING)

    variables = {
        "article": {
            "blogId": blog_gid,
            "title": title,
            "author": {"name": AUTHOR_NAME},
            "body": body,
            "image": {"url": image_url, "altText": image_alt},
            "tags": tags,
            "isPublished": True
        }
    }
    
    resp = requests.post(url, json={"query": mutation, "variables": variables}, headers=headers)
    return resp.json()

def main():
    try:
        # Open with UTF-8 encoding
        with open("content_calendar.json", "r", encoding='utf-8') as f:
            calendar = json.load(f)
    except FileNotFoundError:
        print("Calendar not found. Run planner first.")
        return

    article = next((a for a in calendar['running'] if a["status"] == "pending"), None)
    
    if not article:
        print("No pending articles.")
        return

    print(f"Publishing: {article['title']}")
    
    body_html = generate_article_body(article['title'], article['keywords'])
    widget = get_product_widget()
    
    # Add RTL widget
    if "</p>" in body_html:
        body_html = body_html.replace("</p>", f"</p>{widget}", 1)
    else:
        body_html += widget

    res = publish_article(
        article['title'], 
        body_html, 
        article['image_url'], 
        article.get('image_alt', article['title']), 
        article['keywords']
    )
    
    if res.get('data', {}).get('articleCreate', {}).get('article'):
        print("SUCCESS! Article is live.")
        article["status"] = "published"
        article["published_at"] = str(datetime.date.today())
        
        with open("content_calendar.json", "w", encoding='utf-8') as f:
            json.dump(calendar, f, indent=2, ensure_ascii=False)
    else:
        print(f"FAILED: {res}")

if __name__ == "__main__":
    main()
