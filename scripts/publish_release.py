"""Publish the verified Windows build from a repository-scoped Actions job."""
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def main():
    repository = os.environ['GITHUB_REPOSITORY']
    token = os.environ['GH_TOKEN']
    revision = os.environ['GITHUB_SHA']
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
        raise ValueError('Invalid repository')
    version = (ROOT / 'VERSION').read_text(encoding='utf-8').strip()
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError('Invalid version')
    base = f'https://api.github.com/repos/{repository}'

    def request(url, method='GET', payload=None, binary=None):
        if urllib.parse.urlparse(url).hostname not in ('api.github.com', 'uploads.github.com'):
            raise ValueError('Unexpected release API host')
        headers = {'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json',
                   'User-Agent': 'CodexPetAccessories-release', 'X-GitHub-Api-Version': '2022-11-28'}
        data = json.dumps(payload).encode('utf-8') if payload is not None else binary
        if payload is not None:headers['Content-Type'] = 'application/json'
        if binary is not None:headers['Content-Type'] = 'application/octet-stream'
        with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers, method=method), timeout=180) as response:
            return json.load(response)

    tag = f'v{version}'
    try:
        release = request(f'{base}/releases/tags/{tag}')
    except urllib.error.HTTPError as error:
        if error.code != 404:raise
        release = request(f'{base}/releases', 'POST', {
            'tag_name': tag, 'target_commitish': revision, 'name': f'Codex Pet Accessories {version}',
            'body': (ROOT / 'docs/RELEASE_NOTES.md').read_text(encoding='utf-8'),
            'draft': True, 'prerelease': False})
    if not release['draft']:
        print(f'Release already published: {release["html_url"]}')
        return
    if release['target_commitish'] != revision:
        raise RuntimeError('An existing draft targets a different commit; use a new version')
    paths = [ROOT / 'dist' / f'codex-pet-accessories-{version}-windows-x64.zip',
             ROOT / 'dist' / f'codex-pet-accessories-{version}-source.zip',
             ROOT / 'dist/SHA256SUMS.txt']
    existing = {asset['name']: asset for asset in release['assets']}
    if existing:
        raise RuntimeError('Draft already contains assets; inspect it before retrying publication')
    upload = release['upload_url'].split('{', 1)[0]
    for path in paths:
        request(upload + '?' + urllib.parse.urlencode({'name': path.name}), 'POST', binary=path.read_bytes())
    release = request(f'{base}/releases/{release["id"]}', 'PATCH', {'draft': False, 'make_latest': 'true'})
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a', encoding='utf-8') as output:
            output.write(f'Windows portable release: [{tag}]({release["html_url"]})\n')
    print(f'Published: {release["html_url"]}')


if __name__ == '__main__':
    main()
