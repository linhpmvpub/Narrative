"""Explicit reviewed Inline XBRL selections for local atlas financial context."""
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from datetime import date
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from engine.filing_evidence import AXIS, IX, XBRL, XD, number, text

REVENUE = {'us-gaap:Revenues', 'us-gaap:SalesRevenueNet',
           'us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax'}


class Cell(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    fact_id: str = Field(min_length=1)
    context_id: str = Field(min_length=1)
    label: str = Field(min_length=1, max_length=300)
    dimensions: dict[str, str] = Field(max_length=5)
    role: Literal['PART', 'RECONCILIATION'] = 'PART'


class FinancialSelection(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    id: str = Field(pattern=r'^[A-Za-z0-9_.:-]{1,100}$')
    version: int = Field(ge=1)
    profile_id: str
    source_id: str
    cik: str = Field(pattern=r'^\d{1,10}$')
    kind: Literal['REPORTABLE_SEGMENTS', 'PRODUCTS', 'END_MARKETS', 'INVENTORY_BALANCE']
    total: Cell
    parts: list[Cell] = Field(default_factory=list, max_length=30)
    prior: Cell | None = None
    reviewed_at: AwareDatetime
    reviewer_id: str = Field(min_length=1, max_length=200)
    reviewer_kind: Literal['AI_OPERATOR', 'HUMAN']
    scope: str = Field(min_length=1, max_length=2000)


def extract_selection(blob, selection, published_at):
    """Pinned cells, strict aligned axes/periods/USD/issuer and exact reconciliation."""
    if len(blob) > 8_000_000 or re.search(br'<!\s*(DOCTYPE|ENTITY)', blob, re.I):
        raise ValueError('Unsafe/oversized financial XML')
    namespaces: dict[str, str] = {}
    for _, (prefix, uri) in ET.iterparse(BytesIO(blob), events=['start-ns']):
        if prefix in namespaces and namespaces[prefix] != uri:
            raise ValueError('Ambiguous namespace rebinding')
        namespaces[prefix] = uri
    if (not re.fullmatch(r'https?://fasb.org/us-gaap/\d{4}', namespaces.get('us-gaap',''))
            or namespaces.get('iso4217') != 'http://www.xbrl.org/2003/iso4217'):
        raise ValueError('Unsupported financial QName namespaces')
    root = ET.fromstring(blob)
    ids = [n.get('id') for n in root.iter() if n.get('id')]
    if len(ids) != len(set(ids)):
        raise ValueError('Ambiguous XML IDs')
    nodes = {n.get('id'): n for n in root.iter() if n.get('id')}
    hidden = {id(n) for h in root.iter(f'{{{IX}}}hidden') for n in h.iter()}

    def read(cell):
        n = nodes.get(cell.fact_id)
        if (n is None or n.tag != f'{{{IX}}}nonFraction' or id(n) in hidden
                or n.get('contextRef') != cell.context_id or n.get('continuedAt')):
            raise ValueError('Invalid pinned financial cell')
        c = nodes.get(cell.context_id)
        if c is None or c.tag != f'{{{XBRL}}}context' or list(c.iter(f'{{{XD}}}typedMember')):
            raise ValueError('Invalid financial context')
        identifiers = list(c.iter(f'{{{XBRL}}}identifier'))
        if (len(identifiers) != 1 or identifiers[0].get('scheme') != 'http://www.sec.gov/CIK'
                or int(identifiers[0].text or '-1') != int(selection.cik)):
            raise ValueError('Financial issuer mismatch')
        dims = [(x.get('dimension'), text(x)) for x in c.iter(f'{{{XD}}}explicitMember')]
        if any(axis and axis.startswith('srt:') for axis, _ in dims) and not re.fullmatch(r'https?://fasb.org/srt/\d{4}', namespaces.get('srt','')):
            raise ValueError('Unsupported axis namespace')
        if len(dict(dims)) != len(dims) or dict(dims) != cell.dimensions:
            raise ValueError('Financial axis mismatch')
        u = nodes.get(n.get('unitRef'))
        if (u is None or u.tag != f'{{{XBRL}}}unit' or len(list(u)) != 1
                or u[0].tag != f'{{{XBRL}}}measure' or u[0].text != 'iso4217:USD'):
            raise ValueError('Financial unit must be plain USD')
        start = c.findtext(f'.//{{{XBRL}}}startDate')
        end = c.findtext(f'.//{{{XBRL}}}endDate')
        instant = c.findtext(f'.//{{{XBRL}}}instant')
        if bool(instant) == bool(start or end) or (not instant and (not start or not end)):
            raise ValueError('Ambiguous financial period')
        finish = date.fromisoformat(instant or end or "")
        if finish > published_at.date() or (start and date.fromisoformat(start) > finish):
            raise ValueError('Invalid financial chronology')
        value = number(n)
        if not value.is_finite() or value < 0:
            raise ValueError('Invalid financial value')
        return {**cell.model_dump(), 'concept': n.get('name'), 'value_usd': str(value),
                'period_start': start, 'period_end': end, 'instant': instant,
                'scale': n.get('scale','0'), 'decimals': n.get('decimals'), 'reported_text': text(n)}

    total = read(selection.total)
    if total['dimensions']:
        raise ValueError('Consolidated denominator must have no dimensions')
    parts = [read(c) for c in selection.parts]
    prior = read(selection.prior) if selection.prior else None
    if selection.kind == 'INVENTORY_BALANCE':
        if (parts or total['concept'] != 'us-gaap:InventoryNet' or not total['instant']
                or prior is None or prior['dimensions'] or prior['concept'] != total['concept']
                or not prior['instant'] or prior['instant'] >= total['instant']):
            raise ValueError('Inventory requires two ordered consolidated balances; not buffer days')
    else:
        if not parts or prior or total['concept'] not in REVENUE or total['instant'] or Decimal(total['value_usd']) <= 0:
            raise ValueError('Revenue mix requires a positive duration denominator and parts')
        seen = set()
        for p in parts:
            if (p['concept'] != total['concept'] or p['period_start'] != total['period_start']
                    or p['period_end'] != total['period_end'] or p['instant']):
                raise ValueError('Revenue operands must share concept and exact period')
            dims = p['dimensions'].copy()
            if selection.kind == 'REPORTABLE_SEGMENTS':
                consolidation = dims.pop('srt:ConsolidationItemsAxis', None)
                if p['role'] == 'RECONCILIATION':
                    valid = not dims and consolidation == 'us-gaap:CorporateNonSegmentMember'
                else:
                    valid = set(dims) == {AXIS} and consolidation in {None,'us-gaap:OperatingSegmentsMember'}
            else:
                valid = set(dims) == {'srt:ProductOrServiceAxis'} and p['role'] == 'PART'
            identity = tuple(sorted(p['dimensions'].items()))
            if not valid or identity in seen:
                raise ValueError('Mixed, overlapping or unsupported revenue partition axes')
            seen.add(identity)
        if sum(Decimal(p['value_usd']) for p in parts) != Decimal(total['value_usd']):
            raise ValueError('Selected revenue partition does not reconcile exactly')
        for p in parts:
            p['share_of_total'] = str(Decimal(p['value_usd']) / Decimal(total['value_usd']))
    return {**selection.model_dump(mode='json'), 'total': total, 'parts': parts, 'prior': prior,
            'status': 'SOURCE_CELL_VERIFIED_OPERATOR_SCOPE_REVIEWED',
            'impact_weight': None, 'inventory_buffer_days': None,
            'partition_semantics': 'REVIEWER_DECLARATION_NOT_AUTOMATIC_CLASSIFICATION'}


def apply_financials(data, selections, profile_root, bundles, at):
    if len(selections) > 200:
        raise ValueError('Bounded financial selections required')
    dirs = {}
    for folder in Path(profile_root).iterdir():
        if folder.is_dir() and (folder/'current.json').exists():
            dirs[json.loads((folder/'current.json').read_text(encoding='utf-8'))['id']] = folder
    registry = {b.id: b for b in bundles}
    rows, used = [], set()
    for raw in selections:
        s = FinancialSelection.model_validate(raw)
        b = registry.get(s.profile_id)
        source = next((x for x in b.sources if s.source_id == b.id+'/'+x.id), None) if b else None
        if (b is None or source is None or s.id in used or s.reviewed_at > at or source.retrieved_at > s.reviewed_at or b.available_at > s.reviewed_at
                or int(b.identifiers.get('CIK','-1')) != int(s.cik)):
            raise ValueError('Financial source/profile/reviewer binding invalid')
        used.add(s.id)
        directory = dirs[b.id].resolve()
        path = (directory/source.file).resolve()
        if not path.is_relative_to(directory):
            raise ValueError('Financial source path invalid')
        blob = path.read_bytes()
        if hashlib.sha256(blob).hexdigest() != source.sha256:
            raise ValueError('Financial source changed')
        row = extract_selection(blob,s,source.published_at)
        row['source_sha256'] = source.sha256
        rows.append(row)
    data['financial_context'] = rows
