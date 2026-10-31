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
        
        # Check cursor glow and 3D tubes canvas styles
        self.assertIn('.btn-cursor-glow', css)
        self.assertIn('.hero__tubes', css)
        
        # Check reviews badge hidden on mobile
        self.assertIn('.reviews-trust-badge,', css)
        
        # Check that input font-size is 16px to prevent iOS Safari auto-zoom
        self.assertIn('font-size: 16px !important;', css)

    def test_calculator_structure(self):
        html_path = os.path.join(os.path.dirname(__file__), 'index.html')
        with open(html_path) as f:
            content = f.read()
        
        # Minimalist Configurator / Editorial Calculator section must exist
        self.assertTrue('<section id="calculator"' in content or 'id="calculator"' in content)
        self.assertIn('arh-calc-section', content)
        self.assertIn('arh-calc-container', content)
        self.assertIn('arhShootType', content)
        self.assertIn('arhFrames', content)
        self.assertIn('arhCostTop', content)
        self.assertIn('arhCostBottom', content)
        self.assertIn('arhTgBtn', content)
        
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

        # Process standards & Configurator blocks
        self.assertIn('process-standards-section', html)
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
        self.assertIn('ИП Закопудова Екатерина Александровна', html)

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

if __name__ == '__main__':
    unittest.main()
