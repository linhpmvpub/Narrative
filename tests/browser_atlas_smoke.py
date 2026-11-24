"""Optional installed-Edge smoke: python tests/browser_atlas_smoke.py LOCAL_ATLAS_DIR."""
import sys
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

root = Path(sys.argv[1]).resolve()
with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge", headless=True)
    page = browser.new_page(viewport={"width": 1365, "height": 900})
    failures = []
    network = []
    page.on("pageerror", lambda error: failures.append(str(error)))
    page.on("request", lambda request: network.append(request.url) if request.url.startswith("http") else None)
    page.goto((root / "index.html").as_uri())
    expect(page.locator('#profile option')).to_have_count(6)
    expect(page.locator('#components details')).to_have_count(42)
    expect(page.locator('#mechanisms details')).to_have_count(7)
    for ticker in ['AMD', 'DELL', 'MU', 'NVDA', 'SNDK']:
        options = page.locator('#profile option').all()
        value = next(o.get_attribute('value') for o in options if o.text_content().startswith(ticker+' '))
        page.select_option('#profile', value)
        assert page.locator('#graph .node').count() > 0
        page.locator('#relations button').first.click()
        expect(page.locator('#detail blockquote').first).to_be_visible()
        page.locator('#narratives button').first.click()
        expect(page.locator('#detail pre')).to_contain_text('thesis')
    # Every optional exposure card must preserve period/basis/provenance and source access.
    for option in page.locator('#profile option').all():
        page.select_option('#profile', option.get_attribute('value'))
        for card in page.locator('#facts .exposure-fact').all():
            card.locator('summary').click()
            expect(card).to_contain_text('Kỳ:')
            expect(card).to_contain_text('Mẫu số / cơ sở đo:')
            expect(card).to_contain_text('Người rà soát:')
            card.locator('button').click()
            expect(page.locator('#detail blockquote').first).to_be_visible()
    if page.locator('#financials').count():
        for option in page.locator('#profile option').all():
            page.select_option('#profile', option.get_attribute('value'))
            for card in page.locator('#financials .financial-context').all():
                card.locator('summary').click()
                expect(card.locator('table')).to_be_visible()
                card.locator('button').first.click()
                expect(page.locator('#detail pre')).to_contain_text('source_sha256')
                expect(page.locator('#detail pre')).to_contain_text('impact_weight')
    if page.locator('#field-inventory').count():
        expect(page.locator('#field-inventory details')).to_have_count(7)
        group = page.evaluate('(data.identity_groups||[])[0]')
        if group:
            refs = page.evaluate('data.entity_references')
            member = next(r for r in refs if r['id'] == group['references'][0])
            page.select_option('#profile', member['profile_id'])
            page.locator('#identities summary').first.click()
            page.locator('#identities button').last.click()
            expect(page.locator('#detail pre')).to_contain_text('REVIEWED_NAVIGATION_ONLY')
            expect(page.locator('#detail blockquote').first).to_be_visible()
    if page.locator('#view option[value="FINANCIAL"]').count():
        page.select_option('#view','FINANCIAL')
        for ticker in ['AMD','DELL','MU','NVDA','SNDK']:
            options=page.locator('#profile option').all()
            value=next(o.get_attribute('value') for o in options if o.text_content().startswith(ticker+' ') and 'historical' not in o.get_attribute('value'))
            page.select_option('#profile',value)
            assert page.locator('#graph .node').count()>0
            page.locator('#relations button').first.click()
            expect(page.locator('#detail pre')).to_contain_text('causal_routing')
        page.select_option('#profile','dell-supply-2026')
        page.locator('#relations button').filter(has_text='SUBSET_OF_BUCKET').click()
        expect(page.locator('#detail blockquote').first).to_be_visible()
        expect(page.locator('#detail pre')).to_contain_text('affected_revenue_share')
    page.select_option('#view', 'MECHANISM')
    page.select_option('#view', 'all')
    page.evaluate('window.scrollTo(0,0)')
    page.screenshot(path=str(root/'desktop.png'))
    page.set_viewport_size({'width':390,'height':844})
    assert page.evaluate('document.body.scrollWidth <= window.innerWidth')
    page.evaluate('window.scrollTo(0,0)')
    page.screenshot(path=str(root/'mobile.png'))
    assert not failures, failures
    assert not network, network
    browser.close()
print('PASS: five companies, evidence, narrative paths, filters, 42 components, seven mechanisms, mobile fit, no network requests')
