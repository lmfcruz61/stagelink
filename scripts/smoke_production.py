from html.parser import HTMLParser
import ssl
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import certifi


BASE_URL = 'https://stagehub.pt'
SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = set()

    def handle_starttag(self, tag, attrs):
        if tag != 'a':
            return
        attributes = dict(attrs)
        href = attributes.get('href', '')
        if href.startswith('/'):
            self.links.add(href)


def fetch(path):
    url = f'{BASE_URL}{path}'
    request = Request(url, headers={'User-Agent': 'StageHub smoke test'})
    try:
        with urlopen(request, timeout=30, context=SSL_CONTEXT) as response:
            body = response.read().decode('utf-8', errors='replace')
            return response.status, dict(response.headers), body
    except HTTPError as error:
        body = error.read().decode('utf-8', errors='replace')
        return error.code, dict(error.headers), body
    except URLError as error:
        raise AssertionError(f'{url} failed: {error}') from error


def assert_ok(path, expected_text=None):
    status, headers, body = fetch(path)
    assert status == 200, f'{path} returned HTTP {status}'
    assert 'Server Error' not in body, f'{path} contains Server Error'
    if expected_text:
        assert expected_text in body, f'{path} does not contain {expected_text!r}'
    return headers, body


def assert_security_headers(headers):
    normalized_headers = {key.lower(): value for key, value in headers.items()}
    expected = {
        'Strict-Transport-Security': 'max-age=',
        'X-Frame-Options': 'DENY',
        'X-Content-Type-Options': 'nosniff',
        'Referrer-Policy': 'strict-origin-when-cross-origin',
    }
    for header, expected_fragment in expected.items():
        value = normalized_headers.get(header.lower(), '')
        assert expected_fragment in value, f'missing/invalid {header}: {value!r}'


def main():
    homepage_headers, homepage = assert_ok('/', 'StageHub')
    assert_security_headers(homepage_headers)

    assert_ok('/conta/login/', 'Esqueceste a password?')
    assert_ok('/conta/password/esqueci/', 'Recuperar password')
    assert_ok('/conta/registo/', 'Criar conta')

    admin_status, _, _ = fetch('/admin/')
    assert admin_status in {200, 302}, f'/admin/ returned HTTP {admin_status}'

    parser = LinkParser()
    parser.feed(homepage)
    public_links = sorted(
        link for link in parser.links
        if not link.startswith('/media/')
        and not link.startswith('/static/')
        and not link.startswith('/admin/')
        and not link.startswith('/contas/')
    )[:20]

    for link in public_links:
        status, _, body = fetch(link)
        assert status < 500, f'{link} returned HTTP {status}'
        assert 'Server Error' not in body, f'{link} contains Server Error'

    print('Production smoke tests passed')
    print(f'Checked base pages and {len(public_links)} homepage links')


if __name__ == '__main__':
    main()
