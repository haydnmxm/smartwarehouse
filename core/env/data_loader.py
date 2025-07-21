from __future__ import annotations
import yaml
from .models import Zone, SKU, Client

def load_layout(path: str) -> dict[str, Zone]:
    with open(path, 'r', encoding='utf-8') as f:
        raw = yaml.safe_load(f)
    zones: dict[str, Zone] = {}
    for z in raw['zones']:
        zones[z['id']] = Zone(
            id=z['id'],
            type=z['type'],
            capacity=z.get('capacity', 0),
            x=z.get('x', 0),
            y=z.get('y', 0),
        )
    return zones

def load_skus(path: str) -> dict[str, SKU]:
    with open(path, 'r', encoding='utf-8') as f:
        raw = yaml.safe_load(f)
    skus: dict[str, SKU] = {}
    for s in raw['skus']:
        candidate = s.get('candidate_zones')
        if not candidate:
            candidate = [s['zone']]
        skus[s['id']] = SKU(
            id=s['id'],
            desc=s['desc'],
            zone_id=s['zone'],
            base_pick_sec=int(s['base_pick_sec']),
            initial_qty=int(s.get('initial_qty', 0)),
            candidate_zones=candidate
        )
    return skus

def load_clients(path: str) -> dict[str, Client]:
    with open(path, 'r', encoding='utf-8') as f:
        raw = yaml.safe_load(f)
    clients: dict[str, Client] = {}
    for c in raw['clients']:
        sku_mix = [(m['sku'], m['weight']) for m in c['sku_mix']]
        clients[c['id']] = Client(
            id=c['id'],
            name=c['name'],
            outbound_cfg=c['outbound'],
            sku_mix=sku_mix,
            next_outbound_time=0
        )
    return clients
