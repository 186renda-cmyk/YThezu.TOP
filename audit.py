import os
import sys
import re
import concurrent.futures
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin, unquote
from colorama import init, Fore, Style
from collections import defaultdict, Counter

# Initialize colorama
init(autoreset=True)

class SEOAudit:
    def __init__(self, root_dir='.'):
        self.root_dir = os.path.abspath(root_dir)
        self.base_url = None
        self.keywords = []
        self.files_to_scan = []
        self.internal_links_map = defaultdict(list) # target -> [sources]
        self.external_links = set() # (url, source_file)
        self.pages_data = {} # path -> {title, h1, schema, etc}
        self.score = 100
        self.issues = []
        
        # Configuration
        self.ignore_paths = ['.git', 'node_modules', '__pycache__', '.vscode', '.idea', 'MasterTool']
        self.ignore_url_prefixes = ['/go/', 'javascript:', 'mailto:', '#']
        self.ignore_filenames = ['google', '404.html'] # Partial match
        
        # Counters
        self.stats = {
            'pages_scanned': 0,
            'internal_links': 0,
            'external_links': 0,
            'dead_links': 0,
            'orphans': 0
        }

    def log(self, level, message, score_deduction=0):
        if level == 'SUCCESS':
            print(f"{Fore.GREEN}[SUCCESS]{Style.RESET_ALL} {message}")
        elif level == 'ERROR':
            print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} {message}")
            self.score -= score_deduction
        elif level == 'WARN':
            print(f"{Fore.YELLOW}[WARN]{Style.RESET_ALL} {message}")
            self.score -= score_deduction
        elif level == 'INFO':
            print(f"{Fore.BLUE}[INFO]{Style.RESET_ALL} {message}")
        
        if score_deduction > 0:
            self.issues.append(f"[{level}] {message} (-{score_deduction})")

    def auto_configure(self):
        index_path = os.path.join(self.root_dir, 'index.html')
        if not os.path.exists(index_path):
            self.log('WARN', "Root index.html not found. Cannot auto-configure Base URL.", 0)
            return

        try:
            with open(index_path, 'r', encoding='utf-8', errors='ignore') as f:
                soup = BeautifulSoup(f, 'html.parser')
                
                # Base URL
                canonical = soup.find('link', rel='canonical')
                if canonical and canonical.get('href'):
                    self.base_url = canonical['href'].rstrip('/')
                    self.log('SUCCESS', f"Base URL detected: {self.base_url}")
                else:
                    og_url = soup.find('meta', property='og:url')
                    if og_url and og_url.get('content'):
                        self.base_url = og_url['content'].rstrip('/')
                        self.log('SUCCESS', f"Base URL detected from og:url: {self.base_url}")
                    else:
                        self.log('WARN', "Could not detect Base URL (checked canonical and og:url).")

                # Keywords
                meta_keywords = soup.find('meta', attrs={'name': 'keywords'})
                if meta_keywords and meta_keywords.get('content'):
                    self.keywords = [k.strip() for k in meta_keywords['content'].split(',')]
                    self.log('INFO', f"Keywords detected: {', '.join(self.keywords)}")
                    
        except Exception as e:
            self.log('ERROR', f"Failed to parse index.html for configuration: {str(e)}")

    def is_ignored_path(self, path):
        for ignore in self.ignore_paths:
            if ignore in path.split(os.sep):
                return True
        return False

    def is_ignored_file(self, filename):
        for ignore in self.ignore_filenames:
            if ignore in filename:
                return True
        return False

    def scan_files(self):
        for root, dirs, files in os.walk(self.root_dir):
            # Modify dirs in-place to skip ignored directories
            dirs[:] = [d for d in dirs if d not in self.ignore_paths]
            
            for file in files:
                if not file.endswith('.html'):
                    continue
                if self.is_ignored_file(file):
                    continue
                
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, self.root_dir)
                self.files_to_scan.append((full_path, rel_path))

        self.log('INFO', f"Found {len(self.files_to_scan)} HTML files to scan.")

    def resolve_local_path(self, current_file_path, href):
        # Remove hash and query params
        href_clean = href.split('#')[0].split('?')[0]
        
        if not href_clean:
            return None # Just a hash or empty

        # Handle absolute URLs that point to this site (if base_url is known)
        if self.base_url and href_clean.startswith(self.base_url):
            href_clean = href_clean[len(self.base_url):]
            if not href_clean.startswith('/'):
                href_clean = '/' + href_clean
        
        target_path = None
        
        if href_clean.startswith('/'):
            # Absolute path relative to root
            potential_path = os.path.join(self.root_dir, href_clean.lstrip('/'))
        else:
            # Relative path
            potential_path = os.path.join(os.path.dirname(current_file_path), href_clean)

        # Check existence strategies
        # 1. Exact match (rare for clean URLs but possible)
        if os.path.isfile(potential_path):
            return potential_path
            
        # 2. Append .html
        if os.path.isfile(potential_path + '.html'):
            return potential_path + '.html'
            
        # 3. Directory index (folder/index.html)
        if os.path.isdir(potential_path) and os.path.isfile(os.path.join(potential_path, 'index.html')):
            return os.path.join(potential_path, 'index.html')
            
        return None # Not found

    def check_link_format(self, href, rel_file_path):
        issues = []
        if not href:
            return issues

        # Check 1: Relative paths warning
        if not href.startswith('/') and not href.startswith('http') and not any(href.startswith(p) for p in self.ignore_url_prefixes):
             issues.append((2, f"Use absolute paths (start with /) instead of relative: {href}"))

        # Check 2: Absolute URL with domain warning (if matches base_url)
        if self.base_url and href.startswith(self.base_url):
             issues.append((2, f"Use local path instead of full URL: {href}"))
             
        # Check 3: .html suffix warning
        if href.split('#')[0].split('?')[0].endswith('.html'):
             issues.append((2, f"Use Clean URL (remove .html): {href}"))
             
        return issues

    def analyze_page(self, full_path, rel_path):
        try:
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                soup = BeautifulSoup(content, 'html.parser')

            self.stats['pages_scanned'] += 1
            
            # --- Semantics Checks ---
            
            # H1 Check
            h1s = soup.find_all('h1')
            if len(h1s) == 0:
                self.log('ERROR', f"{rel_path}: Missing <h1> tag", 5)
            elif len(h1s) > 1:
                self.log('WARN', f"{rel_path}: Multiple <h1> tags found", 2)
            
            # Schema Check
            schemas = soup.find_all('script', type='application/ld+json')
            if not schemas:
                self.log('WARN', f"{rel_path}: Missing JSON-LD Schema", 2)
                
            # Breadcrumb Check
            breadcrumb = soup.find(attrs={"aria-label": "breadcrumb"}) or soup.find(class_=lambda c: c and 'breadcrumb' in c)
            if not breadcrumb and rel_path != 'index.html': # Skip for home
                 self.log('WARN', f"{rel_path}: Missing Breadcrumb", 0) # Just log, maybe not critical for all pages

            # --- Link Analysis ---
            links = soup.find_all('a', href=True)
            for link in links:
                href = link['href'].strip()
                
                # Skip ignored
                if any(href.startswith(p) for p in self.ignore_url_prefixes) or 'cdn-cgi' in href:
                    continue

                if href.startswith('http://') or href.startswith('https://'):
                    # External Link
                    if self.base_url and href.startswith(self.base_url):
                        # Technically internal but written as full URL
                        pass # Will be handled by check_link_format and resolve logic below if we treat it as local
                    else:
                        self.external_links.add((href, rel_path))
                        self.stats['external_links'] += 1
                        continue

                self.stats['internal_links'] += 1
                
                # Format Checks
                format_issues = self.check_link_format(href, rel_path)
                for score_ded, msg in format_issues:
                    self.log('WARN', f"{rel_path}: {msg}", score_ded)

                # Dead Link & Resolution
                target_file = self.resolve_local_path(full_path, href)
                
                if target_file:
                    # Map for equity
                    target_rel = os.path.relpath(target_file, self.root_dir)
                    self.internal_links_map[target_rel].append(rel_path)
                else:
                    self.log('ERROR', f"{rel_path}: Dead Internal Link -> {href}", 10)
                    self.stats['dead_links'] += 1

        except Exception as e:
            self.log('ERROR', f"Failed to analyze {rel_path}: {str(e)}")

    def check_external_links(self):
        print(f"\n{Fore.CYAN}Checking {len(self.external_links)} external links...{Style.RESET_ALL}")
        
        def check_url(url_info):
            url, source_file = url_info
            try:
                headers = {'User-Agent': 'SEOAuditBot/1.0'}
                response = requests.head(url, headers=headers, timeout=5, allow_redirects=True)
                if response.status_code >= 400:
                    return (url, source_file, response.status_code)
            except requests.RequestException:
                 return (url, source_file, 'Connection Error')
            return None

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(check_url, self.external_links))

        for res in results:
            if res:
                url, source, status = res
                self.log('ERROR', f"{source}: Broken External Link ({status}) -> {url}", 5)

    def analyze_equity(self):
        print(f"\n{Fore.CYAN}Analyzing Link Equity...{Style.RESET_ALL}")
        
        # Build set of all scanned pages
        all_pages = set(p[1] for p in self.files_to_scan)
        
        # Orphans (In-degree = 0)
        # Exclude index.html and white listed
        orphans = []
        for page in all_pages:
            if page == 'index.html' or self.is_ignored_file(page):
                continue
            
            # Check if anyone links TO this page
            # Note: self.internal_links_map keys are target files
            if page not in self.internal_links_map:
                orphans.append(page)

        if orphans:
            for orphan in orphans:
                self.log('WARN', f"Orphan Page (No incoming links): {orphan}", 5)
                self.stats['orphans'] += 1
        
        # Top Pages
        sorted_pages = sorted(self.internal_links_map.items(), key=lambda x: len(x[1]), reverse=True)
        print(f"\n{Fore.BLUE}Top 10 Pages by Inbound Links:{Style.RESET_ALL}")
        for page, sources in sorted_pages[:10]:
            print(f"  - {page}: {len(sources)} links")

    def run(self):
        print(f"{Fore.CYAN}=== Starting SEO Audit ==={Style.RESET_ALL}")
        self.auto_configure()
        self.scan_files()
        
        print(f"\n{Fore.CYAN}Analyzing Internal Structure...{Style.RESET_ALL}")
        for full_path, rel_path in self.files_to_scan:
            self.analyze_page(full_path, rel_path)
            
        self.analyze_equity()
        
        if self.external_links:
            self.check_external_links()
            
        # Final Report
        self.score = max(0, self.score)
        print(f"\n{Fore.CYAN}=== Audit Complete ==={Style.RESET_ALL}")
        print(f"Pages Scanned: {self.stats['pages_scanned']}")
        print(f"Internal Links: {self.stats['internal_links']}")
        print(f"External Links: {self.stats['external_links']}")
        print(f"Dead Links: {self.stats['dead_links']}")
        
        score_color = Fore.GREEN if self.score >= 90 else (Fore.YELLOW if self.score >= 70 else Fore.RED)
        print(f"\nFinal Score: {score_color}{self.score}/100{Style.RESET_ALL}")
        
        if self.score < 100:
            print(f"\n{Fore.MAGENTA}Actionable Advice:{Style.RESET_ALL}")
            print("Run 'python fix_links.py' (if available) or check the errors above.")

if __name__ == '__main__':
    audit = SEOAudit('.')
    audit.run()
