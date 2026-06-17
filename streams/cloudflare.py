import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings


class CloudflareStreamError(Exception):
    pass


def create_live_input_for_artist(artist):
    account_id = settings.CLOUDFLARE_ACCOUNT_ID.strip()
    api_token = settings.CLOUDFLARE_API_TOKEN.strip()
    if not account_id or not api_token:
        raise CloudflareStreamError('Cloudflare nao esta configurado no servidor.')

    payload = {
        'enabled': True,
        'meta': {
            'name': f'StageHub - {artist.name}',
            'artist_id': str(artist.id),
        },
        'recording': {
            'mode': 'automatic',
            'hideLiveViewerCount': False,
            'timeoutSeconds': 0,
        },
        'deleteRecordingAfterDays': 30,
    }
    request = Request(
        f'https://api.cloudflare.com/client/v4/accounts/{account_id}/stream/live_inputs',
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Authorization': f'Bearer {api_token}',
            'Content-Type': 'application/json',
        },
        method='POST',
    )
    try:
        with urlopen(request, timeout=20) as response:
            data = json.loads(response.read().decode('utf-8'))
    except HTTPError as exc:
        body = exc.read().decode('utf-8', errors='replace')
        raise CloudflareStreamError(f'Cloudflare devolveu erro {exc.code}: {body}') from exc
    except URLError as exc:
        raise CloudflareStreamError(f'Nao foi possivel ligar a Cloudflare: {exc.reason}') from exc

    if not data.get('success'):
        raise CloudflareStreamError(f'Cloudflare nao criou o Live Input: {data.get("errors")}')

    result = data.get('result') or {}
    rtmps = result.get('rtmps') or {}
    return {
        'uid': result.get('uid', ''),
        'rtmps_url': rtmps.get('url', ''),
        'stream_key': rtmps.get('streamKey', ''),
    }


def create_direct_upload_for_stream(stream):
    account_id = settings.CLOUDFLARE_ACCOUNT_ID.strip()
    api_token = settings.CLOUDFLARE_API_TOKEN.strip()
    if not account_id or not api_token:
        raise CloudflareStreamError('Cloudflare nao esta configurado no servidor.')

    max_duration_seconds = 3600
    if stream.duration_minutes:
        max_duration_seconds = max(60, min(3600, int(stream.duration_minutes) * 60))

    payload = {
        'maxDurationSeconds': max_duration_seconds,
        'requireSignedURLs': False,
        'meta': {
            'name': stream.title,
            'artist': stream.artist.name,
            'artist_id': str(stream.artist_id),
            'stream_id': str(stream.id),
        },
    }
    request = Request(
        f'https://api.cloudflare.com/client/v4/accounts/{account_id}/stream/direct_upload',
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Authorization': f'Bearer {api_token}',
            'Content-Type': 'application/json',
        },
        method='POST',
    )
    try:
        with urlopen(request, timeout=20) as response:
            data = json.loads(response.read().decode('utf-8'))
    except HTTPError as exc:
        body = exc.read().decode('utf-8', errors='replace')
        raise CloudflareStreamError(f'Cloudflare devolveu erro {exc.code}: {body}') from exc
    except URLError as exc:
        raise CloudflareStreamError(f'Nao foi possivel ligar a Cloudflare: {exc.reason}') from exc

    if not data.get('success'):
        raise CloudflareStreamError(f'Cloudflare nao criou o upload direto: {data.get("errors")}')

    result = data.get('result') or {}
    return {
        'uid': result.get('uid', ''),
        'upload_url': result.get('uploadURL', ''),
        'expires': result.get('expires', ''),
    }
