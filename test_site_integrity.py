import os
import html.parser

def test_cname_configuration():
    cname_path = os.path.join(os.path.dirname(__file__), 'CNAME')
    assert os.path.exists(cname_path), 'CNAME file must exist'
    with open(cname_path) as f:
        domain = f.read().strip()
    assert domain == 'focus-photocompany.ru', f'Unexpected domain: {domain}'

def test_html_and_meta_theme():
    html_path = os.path.join(os.path.dirname(__file__), 'index.html')
    assert os.path.exists(html_path), 'index.html must exist'
    with open(html_path) as f:
        content = f.read()
    
    # Must have dark theme-color and dark color-scheme to prevent mobile white flash
    assert '<meta name="color-scheme" content="dark">' in content
    assert '<meta name="theme-color" content="#0c0d11">' in content
    
    # Must not contain banned liveDotPulse or reviews-trust-badge__live-dot in reviews badge
    assert 'reviews-trust-badge__live-dot' not in content
    
    # HTML must parse without errors
    parser = html.parser.HTMLParser()
    parser.feed(content)

def test_css_mobile_responsiveness():
    css_path = os.path.join(os.path.dirname(__file__), 'style.css')
    assert os.path.exists(css_path), 'style.css must exist'
    with open(css_path) as f:
        css = f.read()
    
    # Check that about section is hidden on mobile per user requirements
    assert '#about,' in css
    assert '.about-clean {' in css
    assert 'display: none !important;' in css
    
    # Check that input font-size is 16px to prevent iOS Safari auto-zoom
    assert 'font-size: 16px !important;' in css
