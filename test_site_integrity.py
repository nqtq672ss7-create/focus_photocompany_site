import os
import unittest
import html.parser

class SiteIntegrityTest(unittest.TestCase):
    def test_cname_configuration(self):
        cname_path = os.path.join(os.path.dirname(__file__), 'CNAME')
        self.assertTrue(os.path.exists(cname_path), 'CNAME file must exist')
        with open(cname_path) as f:
            domain = f.read().strip()
        self.assertEqual(domain, 'focus-photocompany.ru', f'Unexpected domain: {domain}')

    def test_html_and_meta_theme(self):
        html_path = os.path.join(os.path.dirname(__file__), 'index.html')
        self.assertTrue(os.path.exists(html_path), 'index.html must exist')
        with open(html_path) as f:
            content = f.read()
        
        # Must have dark theme-color and dark color-scheme to prevent mobile white flash
        self.assertIn('<meta name="color-scheme" content="dark">', content)
        self.assertIn('<meta name="theme-color" content="#0c0d11">', content)
        
        # Must not contain banned liveDotPulse or reviews-trust-badge__live-dot in reviews badge
        self.assertNotIn('reviews-trust-badge__live-dot', content)
        self.assertNotIn('Смотреть профиль на Яндекс Картах', content)
        self.assertNotIn('reviews-yandex-badge', content)
        self.assertNotIn('15 минут', content)
        self.assertIn('в течение дня', content)
        
        # HTML must parse without errors
        parser = html.parser.HTMLParser()
        parser.feed(content)

    def test_css_mobile_responsiveness(self):
        css_path = os.path.join(os.path.dirname(__file__), 'style.css')
        self.assertTrue(os.path.exists(css_path), 'style.css must exist')
        with open(css_path) as f:
            css = f.read()
        
        # Check that about section is hidden on mobile per user requirements
        self.assertIn('#about,', css)
        self.assertIn('.about-clean {', css)
        self.assertIn('display: none !important;', css)
        
        # Check cursor glow and luxury scroll progress bar styles
        self.assertIn('.btn-cursor-glow', css)
        self.assertIn('.scroll-progress-bar', css)
        
        # Check reviews badge hidden on mobile
        self.assertIn('.reviews-trust-badge,', css)
        
        # Check that input font-size is 16px to prevent iOS Safari auto-zoom
        self.assertIn('font-size: 16px !important;', css)

    def test_calculator_structure(self):
        html_path = os.path.join(os.path.dirname(__file__), 'index.html')
        with open(html_path) as f:
            content = f.read()
        
        # Minimalist B2B Configurator / Editorial Calculator section must exist
        self.assertTrue('<section id="calculator"' in content or 'id="calculator"' in content)
        self.assertIn('arh-calc-section', content)
        self.assertIn('arh-calc-container', content)
        self.assertIn('arhShootType', content)
        self.assertIn('arhDurationCounter', content)
        self.assertIn('arh-duration-btn', content)
        self.assertIn('arh-addon-card', content)
        self.assertIn('arhCostTop', content)
        self.assertIn('arhCostBottom', content)
        self.assertIn('arhTgBtn', content)
        self.assertIn('arhCity', content)
        
        # B2B pricing checks (Shubskiy benchmark: 25 000 ₽ minimum order)
        self.assertIn('25 000 ₽', content)
        self.assertIn('ИП Авалян Р.А.', content)
        
        # Anti-slop checks for calculator
        self.assertNotIn('01 ·', content)
        self.assertNotIn('///', content)

    def test_seo_and_conversion_integrity(self):
        root = os.path.dirname(__file__)
        
        # 1. robots.txt
        robots_path = os.path.join(root, 'robots.txt')
        self.assertTrue(os.path.exists(robots_path), 'robots.txt must exist')
        with open(robots_path) as f:
            robots = f.read()
        self.assertIn('User-agent: *', robots)
        self.assertIn('Sitemap: https://focus-photocompany.ru/sitemap.xml', robots)

        # 2. sitemap.xml
        sitemap_path = os.path.join(root, 'sitemap.xml')
        self.assertTrue(os.path.exists(sitemap_path), 'sitemap.xml must exist')
        with open(sitemap_path) as f:
            sitemap = f.read()
        self.assertIn('<loc>https://focus-photocompany.ru/</loc>', sitemap)
        self.assertIn('urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"', sitemap)

        # 3. site.webmanifest
        manifest_path = os.path.join(root, 'site.webmanifest')
        self.assertTrue(os.path.exists(manifest_path), 'site.webmanifest must exist')
        import json
        with open(manifest_path) as f:
            manifest = json.load(f)
        self.assertEqual(manifest.get('name'), 'ФОКУС — Фотокомпания')

        # 4. index.html SEO, PillNav, About & Dispatcher
        html_path = os.path.join(root, 'index.html')
        with open(html_path) as f:
            html = f.read()
        # meta keywords removed per SEO best practices (not used by Yandex/Google)
        self.assertNotIn('<meta name="keywords"', html)
        self.assertIn('application/ld+json', html)
        self.assertIn('PhotographyBusiness', html)
        self.assertNotIn('AggregateRating', html) # No fabricated reviews schema
        
        # Contacts & Domain hygiene
        self.assertNotIn('https://max.ru', html) # Banned placeholder link
        self.assertNotIn('info@focus-photo.ru', html) # Must be info@focus-photocompany.ru
        self.assertNotIn('focus-photo.ru', html)

        # Process standards block removed per user request
        self.assertNotIn('process-standards-section', html)
        self.assertNotIn('КАК МЫ РАБОТАЕМ:', html)
        self.assertIn('arhCity', html)
        
        # FAQ section and FAQPage schema removed per user requirements
        self.assertNotIn('FAQPage', html)
        self.assertNotIn('id="faq"', html)
        
        # Streamlined PillNav: 3 links + green signature CTA pill
        self.assertIn('nav-panel__cta', html)
        self.assertIn('ОБСУДИТЬ СЪЁМКУ', html)
        
        # Professional wording in About section (not amateur 'Молодая')
        self.assertIn('экспертная', html.lower())
        self.assertNotIn('молодая', html.lower())
        
        self.assertIn('id="leadHandoffModal"', html)
        self.assertIn('FocusLeadDispatcher', html)
        self.assertIn('floating-contact-pill', html)
        self.assertIn('ИП Авалян Руслан Артурович', html)

        # Primary Geo-Targeting: Anapa & Krasnodar Krai
        self.assertIn('<meta name="geo.region" content="RU-KDA">', html)
        self.assertIn('<meta name="geo.placename" content="Анапа">', html)
        self.assertIn('"addressLocality": "Анапа"', html)
        self.assertIn('"addressRegion": "Краснодарский край"', html)

        # User Design Laws anti-slop checks
        self.assertNotIn('>01 Интерьеры<', html)
        self.assertNotIn('>02 Отели<', html)
        self.assertNotIn('contactsChipInteriors: \'01', html)
        self.assertNotIn('contactsChipHotels: \'02', html)

    def test_advanced_seo_and_crawler_integrity(self):
        root = os.path.dirname(__file__)

        # 1. robots.txt crawler directives
        with open(os.path.join(root, 'robots.txt'), 'r', encoding='utf-8') as f:
            robots = f.read()
        self.assertIn('User-agent: Googlebot', robots)
        self.assertIn('User-agent: Yandex', robots)
        self.assertIn('User-agent: Googlebot-Image', robots)
        self.assertIn('User-agent: YandexImages', robots)
        self.assertIn('Allow: /assets/', robots)
        self.assertIn('Clean-param: utm_source', robots)
        self.assertIn('Host: https://focus-photocompany.ru', robots)

        # 2. sitemap.xml freshness and schema
        with open(os.path.join(root, 'sitemap.xml'), 'r', encoding='utf-8') as f:
            sitemap = f.read()
        self.assertIn('<lastmod>2026-11-06</lastmod>', sitemap)
        self.assertIn('xmlns:image="http://www.google.com/schemas/sitemap-image/1.1"', sitemap)
        self.assertIn('og-image.jpg', sitemap)

        # 3. 404.html existence and noindex
        f404_path = os.path.join(root, '404.html')
        self.assertTrue(os.path.exists(f404_path), '404.html must exist to prevent soft 404')
        with open(f404_path, 'r', encoding='utf-8') as f:
            f404 = f.read()
        self.assertIn('<meta name="robots" content="noindex, follow">', f404)

        # 4. Social OpenGraph 1200x630 assets
        og_jpg = os.path.join(root, 'assets', 'og-image.jpg')
        self.assertTrue(os.path.exists(og_jpg), 'assets/og-image.jpg must exist')

        # 5. Exact H1 count in index.html (Strictly ONE H1)
        with open(os.path.join(root, 'index.html'), 'r', encoding='utf-8') as f:
            index_html = f.read()
        import re
        h1_matches = re.findall(r'<h1[^>]*>(.*?)</h1>', index_html, re.DOTALL | re.IGNORECASE)
        self.assertEqual(len(h1_matches), 1, f'Expected strictly 1 H1 tag, found {len(h1_matches)}')
        self.assertIn('ФОКУС', h1_matches[0])

        # 6. Crawler directives & HTTPS upgrades in index.html
        self.assertIn('<meta name="robots" content="index, follow', index_html)
        self.assertIn('<meta name="googlebot" content="index, follow', index_html)
        self.assertIn('<meta name="yandex" content="index, follow">', index_html)
        self.assertIn('<meta http-equiv="Content-Security-Policy" content="upgrade-insecure-requests">', index_html)
        self.assertIn('og:image:width" content="1200"', index_html)
        self.assertIn('og:image:height" content="630"', index_html)
        self.assertIn('og-image.jpg', index_html)
        self.assertIn('BreadcrumbList', index_html)
        self.assertIn('WebSite', index_html)

        # 7. Legal pages canonical and robots
        for doc in ['privacy.html', 'terms.html', 'cookies.html']:
            with open(os.path.join(root, doc), 'r', encoding='utf-8') as f:
                c = f.read()
            self.assertIn(f'<link rel="canonical" href="https://focus-photocompany.ru/{doc}">', c)
            self.assertIn('<meta name="robots" content="index, follow">', c)
            self.assertIn('<meta http-equiv="Content-Security-Policy" content="upgrade-insecure-requests">', c)

        # 8. Requisites anchor in privacy.html
        with open(os.path.join(root, 'privacy.html'), 'r', encoding='utf-8') as f:
            privacy_c = f.read()
        self.assertIn('id="requisites"', privacy_c)

        # 9. Server security and HSTS
        with open(os.path.join(root, 'serve.py'), 'r', encoding='utf-8') as f:
            serve_c = f.read()
        self.assertIn('Strict-Transport-Security', serve_c)
        self.assertIn('404.html', serve_c)

if __name__ == '__main__':
    unittest.main()
