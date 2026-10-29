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
        
        # Check reviews badge hidden on mobile
        self.assertIn('.reviews-trust-badge,', css)
        
        # Check that input font-size is 16px to prevent iOS Safari auto-zoom
        self.assertIn('font-size: 16px !important;', css)

    def test_calculator_structure(self):
        html_path = os.path.join(os.path.dirname(__file__), 'index.html')
        with open(html_path) as f:
            content = f.read()
        
        # Minimalist Configurator section must exist
        self.assertTrue('<section id="calculator"' in content or 'id="calculator"' in content)
        self.assertIn('calc-section', content)
        self.assertIn('calc-box', content)
        self.assertIn('calc-seg-btn', content)
        self.assertIn('calcSummaryInline', content)
        self.assertIn('calcBtnTg', content)
        self.assertIn('calcBtnWa', content)
        
        # Zero price constraint: No ruble prices in calculator markup
        self.assertNotIn('calcTotalPrice', content)
        
        # Anti-slop checks for calculator
        self.assertNotIn('01 ·', content)
        self.assertNotIn('///', content)

if __name__ == '__main__':
    unittest.main()
