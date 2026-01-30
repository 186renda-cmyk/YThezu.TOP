import os
import re
import json
import random
import copy
from bs4 import BeautifulSoup, Comment

# Configuration
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
BLOG_DIR = os.path.join(PROJECT_ROOT, 'blog')
INDEX_PATH = os.path.join(PROJECT_ROOT, 'index.html')

class BlogBuilder:
    def __init__(self):
        self.nav_html = None
        self.footer_html = None
        self.favicons = []
        self.posts_metadata = []
        self.global_styles = [] # To store tailwind/font-awesome from index or blog
        self.site_url = "https://ythezu.top"

    def update_static_page(self, filename):
        filepath = os.path.join(PROJECT_ROOT, filename)
        if not os.path.exists(filepath):
            return
            
        print(f"Updating static page {filename}...")
        with open(filepath, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f, 'html.parser')
            
        # Clean up Canonical and Alternates in Head
        if soup.head:
            for link in soup.head.find_all('link'):
                href = link.get('href')
                if href:
                    # Remove .html extension for canonical/alternate
                    if 'canonical' in link.get('rel', []) or 'alternate' in link.get('rel', []):
                        if href.endswith('.html'):
                            link['href'] = href[:-5]
                            
        # Inject Nav
        if self.nav_html and soup.body:
            old_nav = soup.body.find('nav')
            if old_nav:
                old_nav.replace_with(copy.copy(self.nav_html))
            else:
                soup.body.insert(0, copy.copy(self.nav_html))

        # Inject Footer
        if self.footer_html and soup.body:
            old_footer = soup.body.find('footer')
            if old_footer:
                old_footer.replace_with(copy.copy(self.footer_html))
            else:
                soup.body.append(copy.copy(self.footer_html))
                
        # Global Link Cleanup
        for a in soup.find_all('a'):
            if a.get('href'):
                a['href'] = self.clean_link(a['href'])

        self.write_formatted_html(filepath, soup)

    def run(self):
        print("Starting build process...")
        self.extract_assets()
        self.scan_posts()
        # Sort posts by date (newest first)
        self.posts_metadata.sort(key=lambda x: x['date'], reverse=True)
        
        self.process_posts()
        self.update_homepage()
        self.update_blog_index()
        
        # Update static pages
        self.update_static_page('support.html')
        self.update_static_page('privacy.html')
        
        self.update_sitemap()
        print("Build complete.")

    def update_sitemap(self):
        print("Updating sitemap.xml...")
        sitemap_path = os.path.join(PROJECT_ROOT, 'sitemap.xml')
        
        # Static Pages with Priorities
        static_pages = [
            {'url': '/', 'priority': '1.0'},
            {'url': '/blog/', 'priority': '0.9'},
            {'url': '/support', 'priority': '0.5'},
            {'url': '/privacy', 'priority': '0.5'}
        ]
        
        # Determine latest date for homepage
        latest_date = "2026-01-01"
        if self.posts_metadata:
            latest_date = self.posts_metadata[0]['date']
            
        xml_content = ['<?xml version="1.0" encoding="UTF-8"?>']
        xml_content.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
        
        # Add Static Pages
        for page in static_pages:
            url = page['url']
            if url == '/': full_url = self.site_url + '/'
            elif url.endswith('/'): full_url = self.site_url + url
            else: full_url = self.site_url + url
            
            # Use latest post date for homepage and blog index, or today's date
            # For simplicity, let's use the latest post date for dynamic pages
            date = latest_date
            
            xml_content.append('  <url>')
            xml_content.append(f'    <loc>{full_url}</loc>')
            xml_content.append(f'    <lastmod>{date}</lastmod>')
            xml_content.append(f'    <priority>{page["priority"]}</priority>')
            xml_content.append('  </url>')
            
        # Add Blog Posts
        for p in self.posts_metadata:
            full_url = self.site_url + p['url']
            date = p['date']
            
            xml_content.append('  <url>')
            xml_content.append(f'    <loc>{full_url}</loc>')
            xml_content.append(f'    <lastmod>{date}</lastmod>')
            xml_content.append('    <priority>0.8</priority>')
            xml_content.append('  </url>')
            
        xml_content.append('</urlset>')
        
        with open(sitemap_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(xml_content))

    def clean_link(self, url):
        if not url:
            return url
            
        # Split hash/query
        base = url
        fragment = ''
        if '#' in url:
            base, fragment = url.split('#', 1)
            fragment = '#' + fragment
        elif '?' in url:
            base, fragment = url.split('?', 1)
            fragment = '?' + fragment

        # Handle External / Special protocols
        if base.startswith(('http:', 'https:', 'mailto:', 'tel:', 'javascript:')):
            return url

        # Clean relative path parts
        # Treat as root-relative for this specific project structure
        base = base.replace('../', '/').replace('./', '/')
        
        # Ensure it starts with / if it's internal
        if not base.startswith('/'):
            base = '/' + base
            
        # Remove duplicates like //
        while '//' in base:
            base = base.replace('//', '/')
            
        # Remove .html and index
        if base.endswith('/index.html'):
            base = base[:-10]
            if not base: base = '/'
        elif base.endswith('index.html'): 
             base = base[:-10]
        elif base.endswith('.html'):
            base = base[:-5]
            
        return base + fragment

    def extract_assets(self):
        print(f"Extracting assets from {INDEX_PATH}...")
        with open(INDEX_PATH, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f, 'html.parser')

        # 1. Extract Nav
        nav = soup.find('nav')
        if nav:
            # Clean links in Nav
            for a in nav.find_all('a'):
                if a.get('href'):
                    # For nav in blog pages, anchors like #features need to point to home
                    href = a['href']
                    if href.startswith('#'):
                        a['href'] = '/' + href
                    elif href == '/' or href == '/index.html':
                        a['href'] = '/'
                    elif not href.startswith(('http', 'https', '/')):
                         # relative path
                         pass 
            self.nav_html = nav

        # 2. Extract Footer
        footer = soup.find('footer')
        if footer:
            for a in footer.find_all('a'):
                if a.get('href'):
                    href = a['href']
                    if href.startswith('#'):
                        a['href'] = '/' + href
            self.footer_html = footer

        # 3. Extract Brand Assets (Favicons)
        head = soup.find('head')
        if head:
            for link in head.find_all('link'):
                rel = link.get('rel', [])
                if isinstance(rel, list):
                    rel = ' '.join(rel)
                
                if 'icon' in rel:
                    # Force root relative path
                    href = link.get('href')
                    if href and not href.startswith(('http', 'https', '/')):
                        link['href'] = '/' + href
                    
                    # Deduplicate based on href and rel
                    is_duplicate = False
                    for existing_icon in self.favicons:
                        existing_rel = existing_icon.get('rel', [])
                        if isinstance(existing_rel, list): existing_rel = ' '.join(existing_rel)
                        if link.get('href') == existing_icon.get('href') and rel == existing_rel:
                            is_duplicate = True
                            break
                    
                    if not is_duplicate:
                        self.favicons.append(link)

    def scan_posts(self):
        print("Scanning blog posts...")
        if not os.path.exists(BLOG_DIR):
            print("Blog directory not found!")
            return

        for filename in os.listdir(BLOG_DIR):
            if not filename.endswith('.html') or filename == 'index.html':
                continue
            
            filepath = os.path.join(BLOG_DIR, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                soup = BeautifulSoup(f, 'html.parser')
                
                # Extract metadata
                title = soup.title.string.strip() if soup.title and soup.title.string else ""
                desc = soup.find('meta', attrs={'name': 'description'})
                description = desc['content'] if desc else ""
                
                # Extract Date - Try JSON-LD first
                date_str = "2026-01-01" # Default
                
                ld_json = soup.find('script', type='application/ld+json')
                if ld_json and ld_json.string:
                    try:
                        data = json.loads(ld_json.string.strip())
                        if isinstance(data, dict) and '@graph' in data:
                            for item in data['graph']:
                                if item.get('@type') == 'Article' or item.get('@type') == 'BlogPosting':
                                    if 'datePublished' in item:
                                        date_str = item['datePublished']
                    except Exception as e:
                        print(f"Error parsing JSON-LD in {filename}: {e}")
                        pass
                
                # Fallback: Try visual date
                if date_str == "2026-01-01":
                    date_icon = soup.find('i', class_='fa-calendar')
                    if date_icon and date_icon.parent:
                        date_text = date_icon.parent.get_text().strip()
                        # Extract date pattern YYYY-MM-DD
                        match = re.search(r'\d{4}-\d{2}-\d{2}', date_text)
                        if match:
                            date_str = match.group(0)
                            print(f"  Extracted visual date for {filename}: {date_str}")
                
                # Extract Custom Metadata for Homepage Cards
                theme_color = "red" # Default
                icon_class = "fa-file-lines" # Default
                badge_text = "最新发布" # Default
                
                meta_color = soup.find('meta', attrs={'name': 'x-theme-color'})
                if meta_color and meta_color.get('content'): 
                    theme_color = meta_color['content']
                
                meta_icon = soup.find('meta', attrs={'name': 'x-icon'})
                if meta_icon and meta_icon.get('content'): 
                    icon_class = meta_icon['content']
                
                meta_badge = soup.find('meta', attrs={'name': 'x-badge'})
                if meta_badge and meta_badge.get('content'): 
                    badge_text = meta_badge['content']
                
                print(f"  Metadata for {filename}: color={theme_color}, icon={icon_class}, badge={badge_text}")

                # Extract Image
                og_image = soup.find('meta', property='og:image')
                image_url = og_image['content'] if og_image else ""
                
                self.posts_metadata.append({
                    'title': title,
                    'description': description,
                    'date': date_str,
                    'url': f"/blog/{filename.replace('.html', '')}",
                    'image': image_url,
                    'filename': filename,
                    'path': filepath,
                    'theme_color': theme_color,
                    'icon_class': icon_class,
                    'badge_text': badge_text
                })

    def process_posts(self):
        print("Processing posts...")
        for post in self.posts_metadata:
            self.reconstruct_post(post)

    def reconstruct_post(self, post_meta):
        filepath = post_meta['path']
        print(f"  Reconstructing {post_meta['filename']}...")
        
        with open(filepath, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f, 'html.parser')

        # --- Phase 2: Head Reconstruction ---
        
        # 1. Capture existing data
        old_head = soup.head
        title_text = old_head.title.string if old_head.title else post_meta['title']
        
        meta_desc = old_head.find('meta', attrs={'name': 'description'})
        desc_content = meta_desc['content'] if meta_desc else post_meta['description']
        
        meta_kw = old_head.find('meta', attrs={'name': 'keywords'})
        kw_content = meta_kw['content'] if meta_kw else ""
        
        # Canonical - Clean URL
        canonical_link = old_head.find('link', rel='canonical')
        canonical_href = canonical_link['href'] if canonical_link else f"{self.site_url}{post_meta['url']}"
        if canonical_href.endswith('.html'):
            canonical_href = canonical_href[:-5]
        
        # Clean canonical path
        if canonical_href.endswith('/index'):
            canonical_href = canonical_href[:-6]
        
        # JSON-LD
        json_ld = old_head.find('script', type='application/ld+json')
        
        # Styles / Scripts (Tailwind, FontAwesome, Custom Styles)
        styles_scripts = []
        has_local_css = False
        has_tailwind_cdn = False
        
        for tag in old_head.find_all(['script', 'link', 'style']):
            # Skip SEO/Meta tags we already handled or will regenerate
            if tag.name == 'link':
                rel = tag.get('rel', [])
                if isinstance(rel, list): rel = ' '.join(rel)
                if 'canonical' in rel or 'alternate' in rel or 'icon' in rel:
                    continue
                # Extra check for favicons by href just in case rel parsing fails or is weird
                href = tag.get('href', '')
                if 'favicon' in href or 'icon' in href:
                    continue
                if href == '/assets/style.css':
                    has_local_css = True
                    continue # Skip local CSS
            
            if tag.name == 'script':
                if tag.get('type') == 'application/ld+json':
                    continue
                # Keep Tailwind CDN
                if 'cdn.tailwindcss.com' in tag.get('src', ''):
                    has_tailwind_cdn = True
            
            # Keep Tailwind, FontAwesome, Custom CSS
            styles_scripts.append(tag)

        # Inject Tailwind CDN if missing
        if not has_tailwind_cdn:
            tailwind_script = soup.new_tag('script', src='https://cdn.tailwindcss.com')
            styles_scripts.insert(0, tailwind_script)

        # 2. Clear Head
        if soup.head:
            soup.head.clear()
        else:
            new_head = soup.new_tag("head")
            soup.html.insert(0, new_head)

        # 3. Build New Head
        head = soup.head

        # Group A: Basic Metadata
        head.append(soup.new_tag('meta', charset='utf-8'))
        head.append(soup.new_tag('meta', attrs={'name': 'viewport', 'content': 'width=device-width, initial-scale=1'}))
        new_title = soup.new_tag('title')
        new_title.string = title_text
        head.append(new_title)
        head.append(Comment(" Group A: Basic Metadata "))

        # Group B: SEO Core
        if desc_content:
            head.append(soup.new_tag('meta', attrs={'name': 'description', 'content': desc_content}))
        if kw_content:
            head.append(soup.new_tag('meta', attrs={'name': 'keywords', 'content': kw_content}))
        head.append(soup.new_tag('link', attrs={'rel': 'canonical', 'href': canonical_href}))
        
        # OG Tags
        head.append(soup.new_tag('meta', property='og:title', content=title_text))
        head.append(soup.new_tag('meta', property='og:description', content=desc_content))
        head.append(soup.new_tag('meta', property='og:url', content=canonical_href))
        if post_meta['image']:
            head.append(soup.new_tag('meta', property='og:image', content=post_meta['image']))
        head.append(soup.new_tag('meta', property='og:type', content='article'))
        
        head.append(Comment(" Group B: SEO Core "))

        # Group C: Indexing & Geo
        head.append(soup.new_tag('meta', attrs={'name': 'robots', 'content': 'index,follow'}))
        head.append(soup.new_tag('meta', attrs={'http-equiv': 'content-language', 'content': 'zh-CN'}))
        head.append(soup.new_tag('link', attrs={'rel': 'alternate', 'hreflang': 'zh', 'href': canonical_href}))
        head.append(soup.new_tag('link', attrs={'rel': 'alternate', 'hreflang': 'x-default', 'href': canonical_href}))
        head.append(Comment(" Group C: Indexing & Geo "))

        # Group D: Branding & Resources
        # Favicons
        for icon in self.favicons:
            head.append(copy.copy(icon))
            
        # Styles/Scripts
        for item in styles_scripts:
            head.append(item)
        head.append(Comment(" Group D: Branding & Resources "))

        # Group E: Structured Data
        if json_ld:
            head.append(json_ld)
        head.append(Comment(" Group E: Structured Data "))

        # Group F: Custom Metadata
        if post_meta.get('theme_color'):
            head.append(soup.new_tag('meta', attrs={'name': 'x-theme-color', 'content': post_meta['theme_color']}))
        if post_meta.get('icon_class'):
            head.append(soup.new_tag('meta', attrs={'name': 'x-icon', 'content': post_meta['icon_class']}))
        if post_meta.get('badge_text'):
            head.append(soup.new_tag('meta', attrs={'name': 'x-badge', 'content': post_meta['badge_text']}))
        head.append(Comment(" Group F: Custom Metadata "))

        # Safety Net: Deduplicate Favicons in Head
        seen_favicons = set()
        # Collect links to remove
        to_remove = []
        for link in head.find_all('link'):
            rel = link.get('rel', [])
            if isinstance(rel, list): rel = ' '.join(rel)
            if 'icon' in rel:
                href = link.get('href')
                if href in seen_favicons:
                    to_remove.append(link)
                else:
                    seen_favicons.add(href)
        for link in to_remove:
            link.decompose()

        # --- Phase 3: Content Injection ---

        # 1. Inject Nav
        if self.nav_html and soup.body:
            old_nav = soup.body.find('nav')
            if old_nav:
                old_nav.replace_with(copy.copy(self.nav_html))
            else:
                soup.body.insert(0, copy.copy(self.nav_html))

        # 2. Inject Footer
        if self.footer_html and soup.body:
            old_footer = soup.body.find('footer')
            if old_footer:
                old_footer.replace_with(copy.copy(self.footer_html))
            else:
                soup.body.append(copy.copy(self.footer_html))
        
        # 3. Inject Recommendations
        article = soup.find('article')
        if article:
            for div in article.find_all('div', recursive=False):
                if "推荐阅读" in div.get_text():
                    div.decompose()
            
            rec_div = soup.new_tag('div', attrs={'class': 'mt-12 pt-8 border-t border-white/10'})
            rec_h3 = soup.new_tag('h3', attrs={'class': 'text-xl font-bold text-white mb-6'})
            rec_h3.string = "推荐阅读"
            rec_div.append(rec_h3)
            
            grid_div = soup.new_tag('div', attrs={'class': 'grid grid-cols-1 md:grid-cols-2 gap-6'})
            
            other_posts = [p for p in self.posts_metadata if p['filename'] != post_meta['filename']]
            selected_posts = other_posts[:4]
            
            for p in selected_posts:
                a_tag = soup.new_tag('a', href=p['url'], attrs={'class': 'block p-4 rounded-xl bg-white/5 hover:bg-white/10 transition border border-white/5'})
                
                span_tag = soup.new_tag('span', attrs={'class': 'text-xs text-red-400 font-bold mb-2 block'})
                span_tag.string = "精选文章"
                
                h4_tag = soup.new_tag('h4', attrs={'class': 'text-sm font-bold text-white'})
                h4_tag.string = p['title']
                
                a_tag.append(span_tag)
                a_tag.append(h4_tag)
                grid_div.append(a_tag)
                
            rec_div.append(grid_div)
            article.append(rec_div)

        # 3.5 Fix Breadcrumb Case for Audit
        breadcrumb_nav = soup.find('nav', attrs={'aria-label': 'Breadcrumb'})
        if breadcrumb_nav:
            breadcrumb_nav['aria-label'] = 'breadcrumb'

        # 4. Global Link Cleanup
        for a in soup.find_all('a'):
            if a.get('href'):
                a['href'] = self.clean_link(a['href'])
                
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(soup.prettify())

    def write_formatted_html(self, filepath, soup):
        print(f"  Writing formatted HTML to {filepath}...")
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(soup.prettify())

    def update_homepage(self):
        print("Updating homepage...")
        with open(INDEX_PATH, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f, 'html.parser')
            
        guides_section = soup.find('section', id='guides')
        if guides_section:
            grid = guides_section.find('div', class_='grid')
            if grid:
                # Update grid columns to support 4 items
                grid['class'] = "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6"
                grid.clear()
                
                # Show top 4 posts
                for p in self.posts_metadata[:4]:
                    theme = p['theme_color']
                    # Map simple color names to tailwind classes if needed, or use string interpolation
                    # Assuming theme is like 'red', 'green', 'blue', 'purple', 'orange', 'pink'
                    
                    a_tag = soup.new_tag('a', href=p['url'], attrs={'class': f"group block rounded-3xl bg-[#151515] border border-white/5 overflow-hidden hover:border-{theme}-500/30 transition duration-300"})
                    
                    div_img = soup.new_tag('div', attrs={'class': f"h-48 bg-gradient-to-br from-{theme}-900/20 to-black relative"})
                    div_icon_container = soup.new_tag('div', attrs={'class': 'absolute inset-0 flex items-center justify-center'})
                    
                    # Icon
                    icon_cls = p['icon_class']
                    if not icon_cls.startswith('fa-'): icon_cls = f"fa-solid {icon_cls}" # fallback
                    else: icon_cls = f"fa-solid {icon_cls}"
                    
                    icon = soup.new_tag('i', attrs={'class': f"{icon_cls} text-5xl text-{theme}-500/30 group-hover:text-{theme}-500/50 transition duration-300"})
                    div_icon_container.append(icon)
                    div_img.append(div_icon_container)
                    
                    div_badge = soup.new_tag('div', attrs={'class': f"absolute bottom-4 left-4 bg-{theme}-600 text-white text-xs font-bold px-2 py-1 rounded"})
                    div_badge.string = p['badge_text']
                    div_img.append(div_badge)
                    
                    a_tag.append(div_img)
                    
                    div_content = soup.new_tag('div', attrs={'class': 'p-6'})
                    h3 = soup.new_tag('h3', attrs={'class': f"text-xl font-bold text-white mb-3 group-hover:text-{theme}-400 transition"})
                    h3.string = p['title']
                    div_content.append(h3)
                    
                    p_desc = soup.new_tag('p', attrs={'class': 'text-sm text-gray-400 line-clamp-2'})
                    p_desc.string = p['description']
                    div_content.append(p_desc)
                    
                    div_meta = soup.new_tag('div', attrs={'class': 'mt-4 flex items-center text-xs text-gray-500'})
                    span_date = soup.new_tag('span')
                    span_date.append(soup.new_tag('i', attrs={'class': 'fa-regular fa-clock mr-1'}))
                    span_date.append(f" {p['date']}")
                    div_meta.append(span_date)
                    
                    # Hot/Star icon for engagement if needed
                    span_extra = soup.new_tag('span', attrs={'class': 'ml-2'})
                    # We could add more logic here, but keeping it simple for now
                    
                    div_content.append(div_meta)
                    a_tag.append(div_content)
                    
                    grid.append(a_tag)

        self.write_formatted_html(INDEX_PATH, soup)

    def update_blog_index(self):
        blog_index_path = os.path.join(BLOG_DIR, 'index.html')
        if os.path.exists(blog_index_path):
            print("Updating blog/index.html...")
            with open(blog_index_path, 'r', encoding='utf-8') as f:
                soup = BeautifulSoup(f, 'html.parser')
                
            if self.nav_html and soup.body:
                old_nav = soup.body.find('nav')
                if old_nav: old_nav.replace_with(copy.copy(self.nav_html))
            if self.footer_html and soup.body:
                old_footer = soup.body.find('footer')
                if old_footer: old_footer.replace_with(copy.copy(self.footer_html))
            
            # Update Article Grid
            grid = soup.find('div', role='list')
            # Fallback if role=list is missing, look for grid class
            if not grid:
                grids = soup.find_all('div', class_='grid')
                if grids:
                    grid = grids[0] # Assume first grid is the post list
            
            if grid:
                grid.clear()
                # Update grid class to be responsive
                grid['class'] = "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8"
                
                for p in self.posts_metadata:
                    theme = p['theme_color']
                    
                    a_tag = soup.new_tag('a', href=p['url'], attrs={'class': f"group block rounded-3xl bg-[#151515] border border-white/5 overflow-hidden hover:border-{theme}-500/30 transition duration-300 flex flex-col h-full", 'role': 'listitem'})
                    
                    div_img = soup.new_tag('div', attrs={'class': f"h-48 bg-gradient-to-br from-{theme}-900/20 to-black relative shrink-0"})
                    div_icon_container = soup.new_tag('div', attrs={'class': 'absolute inset-0 flex items-center justify-center'})
                    
                    # Icon
                    icon_cls = p['icon_class']
                    if not icon_cls.startswith('fa-'): icon_cls = f"fa-solid {icon_cls}" 
                    else: icon_cls = f"fa-solid {icon_cls}"
                    
                    icon = soup.new_tag('i', attrs={'class': f"{icon_cls} text-5xl text-{theme}-500/30 group-hover:text-{theme}-500/50 transition duration-300"})
                    div_icon_container.append(icon)
                    div_img.append(div_icon_container)
                    
                    div_badge = soup.new_tag('div', attrs={'class': f"absolute bottom-4 left-4 bg-{theme}-600 text-white text-xs font-bold px-2 py-1 rounded"})
                    div_badge.string = p['badge_text']
                    div_img.append(div_badge)
                    
                    a_tag.append(div_img)
                    
                    div_content = soup.new_tag('div', attrs={'class': 'p-6 flex flex-col flex-1'})
                    h2 = soup.new_tag('h2', attrs={'class': f"text-xl font-bold text-white mb-3 group-hover:text-{theme}-400 transition"})
                    h2.string = p['title']
                    div_content.append(h2)
                    
                    p_desc = soup.new_tag('p', attrs={'class': 'text-sm text-gray-400 line-clamp-2 mb-4 flex-1'})
                    p_desc.string = p['description']
                    div_content.append(p_desc)
                    
                    div_meta = soup.new_tag('div', attrs={'class': 'mt-auto flex items-center text-xs text-gray-500'})
                    span_date = soup.new_tag('span')
                    span_date.append(soup.new_tag('i', attrs={'class': 'fa-regular fa-clock mr-1'}))
                    span_date.append(f" {p['date']}")
                    div_meta.append(span_date)
                    
                    span_dot = soup.new_tag('span', attrs={'class': 'mx-2'})
                    span_dot.string = "·"
                    div_meta.append(span_dot)
                    
                    span_extra = soup.new_tag('span')
                    icon_extra = soup.new_tag('i', attrs={'class': f"fa-solid fa-star text-{theme}-500/70 mr-1"})
                    if p['badge_text'] == "省钱必读":
                         icon_extra['class'] = f"fa-solid fa-fire text-{theme}-500/70 mr-1"
                    elif p['badge_text'] == "深度评测":
                         icon_extra['class'] = f"fa-solid fa-eye text-{theme}-500/70 mr-1"
                    elif p['badge_text'] == "对比评测":
                         icon_extra['class'] = f"fa-solid fa-scale-balanced text-{theme}-500/70 mr-1"
                         
                    recommend_text = " 强烈推荐"
                    if p['badge_text'] == "省钱必读":
                         recommend_text = " 热度飙升"
                    elif p['badge_text'] == "深度评测":
                         recommend_text = " 编辑推荐"
                    elif p['badge_text'] == "对比评测":
                         recommend_text = " 深度对比"
                         
                    span_extra.append(icon_extra)
                    span_extra.append(recommend_text)
                    div_meta.append(span_extra)
                    
                    div_content.append(div_meta)
                    a_tag.append(div_content)
                    
                    grid.append(a_tag) 

            # Inject JSON-LD
            item_list = {
                "@context": "https://schema.org",
                "@type": "ItemList",
                "itemListElement": []
            }

            for index, p in enumerate(self.posts_metadata):
                item = {
                    "@type": "ListItem",
                    "position": index + 1,
                    "url": self.site_url + p['url'],
                    "name": p['title']
                }
                item_list["itemListElement"].append(item)
            
            # Find existing script or create new one
            script_tag = soup.find('script', type='application/ld+json')
            if script_tag:
                script_tag.string = json.dumps(item_list, ensure_ascii=False, indent=2)
            else:
                script_tag = soup.new_tag('script', type='application/ld+json')
                script_tag.string = json.dumps(item_list, ensure_ascii=False, indent=2)
                if soup.head:
                    soup.head.append(script_tag)

            self.write_formatted_html(blog_index_path, soup)

if __name__ == "__main__":
    builder = BlogBuilder()
    builder.run()
