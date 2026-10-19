"""Download only official, public 2025 finalized-complaint ZIPs."""
from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from .config import CATALOG_URL, MANIFEST, RAW_DIR


def fetch(url: str) -> bytes:
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=90) as response:
                return response.read()
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))
    raise RuntimeError('Unreachable')


def download(item: dict) -> dict:
    name = item['nomeArquivo']
    url = f"https://consumidor.gov.br/pages/publicacao/externo/{item['codigo']}/download"
    path = RAW_DIR / name
    if not path.exists():
        contents = fetch(url)
        temporary = path.with_suffix('.part')
        temporary.write_bytes(contents)
        if not zipfile.is_zipfile(temporary):
            raise ValueError(f'Expected ZIP, received other content: {url}')
        temporary.replace(path)
    contents = path.read_bytes()
    digest = hashlib.sha256(contents).hexdigest()
    if item.get('expected_sha256') and digest != item['expected_sha256']:
        raise ValueError(f'SHA-256 differs from pinned snapshot: {path}. Do not silently replace the manifest.')
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError(f'Corrupt archive: {path}')
    print(f'{name}: {len(contents):,} bytes', flush=True)
    return {'file': name, 'url': url, 'publication_id': item['codigo'],
            'title': item['titulo'], 'description': item.get('texto'),
            'catalog_update': item.get('dataAlteracao'), 'bytes': len(contents),
            'sha256': digest}


def run(refresh_manifest: bool = False) -> None:
    """Verify the pinned snapshot, or rediscover the catalog when explicitly asked."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    if MANIFEST.exists() and not refresh_manifest:
        pinned = json.loads(MANIFEST.read_text(encoding='utf-8'))
        selected = [{'nomeArquivo': x['file'], 'codigo': x['publication_id'], 'titulo': x['title'],
                     'texto': x.get('description'), 'dataAlteracao': x.get('catalog_update'),
                     'expected_sha256': x['sha256']} for x in pinned['files']]
        with ThreadPoolExecutor(max_workers=3) as executor:
            list(executor.map(download, selected))
        print('Pinned snapshot verified; manifest preserved.', flush=True)
        return
    catalog = json.loads(fetch(CATALOG_URL))
    selected = sorted((x for x in catalog if re.fullmatch(r'finalizadas_2025-\d{2}\.zip', x.get('nomeArquivo', ''))), key=lambda x: x['nomeArquivo'])
    if len(selected) != 12 or len({x['nomeArquivo'] for x in selected}) != 12:
        raise ValueError('Expected exactly 12 distinct monthly files for 2025')
    with ThreadPoolExecutor(max_workers=3) as executor:
        files = list(executor.map(download, selected))
    manifest = {'catalog_url': CATALOG_URL, 'retrieved_at_utc': datetime.now(timezone.utc).isoformat(),
                'source': 'Senacon / Consumidor.gov.br', 'cohort': 'Finalizadas de janeiro a dezembro de 2025',
                'license_note': 'Fonte pública oficial; licença específica dos arquivos deve ser verificada junto à fonte. Dados brutos não redistribuídos.', 'files': files}
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
