import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings


class CloudflareStreamError(Exception):
    pass


def create_live_input_for_artist(artist):
    account_id = settings.CLOUDFLARE_ACCOUNT_ID.strip()
    api_token = (getattr(settings, 'CLOUDFLARE_STREAM_TOKEN', '') or settings.CLOUDFLARE_API_TOKEN).strip()
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
    api_token = (getattr(settings, 'CLOUDFLARE_STREAM_TOKEN', '') or settings.CLOUDFLARE_API_TOKEN).strip()
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
        'expires': result.get('expires') or result.get('uploadExpiry', ''),
    }


def cloudflare_stream_request(path, method='GET'):
    account_id = settings.CLOUDFLARE_ACCOUNT_ID.strip()
    api_token = (getattr(settings, 'CLOUDFLARE_STREAM_TOKEN', '') or settings.CLOUDFLARE_API_TOKEN).strip()
    if not account_id or not api_token:
        raise CloudflareStreamError('Cloudflare nao esta configurado no servidor.')

    request = Request(
        f'https://api.cloudflare.com/client/v4/accounts/{account_id}{path}',
        headers={
            'Authorization': f'Bearer {api_token}',
            'Content-Type': 'application/json',
        },
        method=method,
    )
    try:
        with urlopen(request, timeout=25) as response:
            raw_body = response.read().decode('utf-8')
            return json.loads(raw_body) if raw_body else {'success': True}
    except HTTPError as exc:
        body = exc.read().decode('utf-8', errors='replace')
        raise CloudflareStreamError(f'Cloudflare devolveu erro {exc.code}: {body}') from exc
    except URLError as exc:
        raise CloudflareStreamError(f'Nao foi possivel ligar a Cloudflare: {exc.reason}') from exc


def get_stream_video(video_uid):
    data = cloudflare_stream_request(f'/stream/{video_uid}', method='GET')
    if not data.get('success'):
        raise CloudflareStreamError(f'Cloudflare nao devolveu o video: {data.get("errors")}')
    return data.get('result') or {}


def delete_stream_video(video_uid):
    data = cloudflare_stream_request(f'/stream/{video_uid}', method='DELETE')
    if not data.get('success', True):
        raise CloudflareStreamError(f'Cloudflare nao apagou o video: {data.get("errors")}')
    return data


def list_stream_videos():
    data = cloudflare_stream_request('/stream?per_page=1000', method='GET')
    if not data.get('success'):
        raise CloudflareStreamError(f'Cloudflare nao devolveu a lista de videos: {data.get("errors")}')
    return data.get('result') or []


def list_stream_live_inputs():
    data = cloudflare_stream_request('/stream/live_inputs?per_page=1000', method='GET')
    if not data.get('success'):
        raise CloudflareStreamError(f'Cloudflare nao devolveu a lista de canais ao vivo: {data.get("errors")}')
    return data.get('result') or []


def get_stream_live_input(live_input_uid):
    data = cloudflare_stream_request(f'/stream/live_inputs/{live_input_uid}', method='GET')
    if not data.get('success'):
        raise CloudflareStreamError(f'Cloudflare nao devolveu o canal ao vivo: {data.get("errors")}')
    return data.get('result') or {}


def list_stream_live_input_videos(live_input_uid):
    data = cloudflare_stream_request(
        f'/stream/live_inputs/{live_input_uid}/videos',
        method='GET',
    )
    if not data.get('success'):
        raise CloudflareStreamError(
            f'Cloudflare nao devolveu as gravacoes desta live: {data.get("errors")}',
        )
    return data.get('result') or []


def delete_stream_live_input(live_input_uid):
    data = cloudflare_stream_request(f'/stream/live_inputs/{live_input_uid}', method='DELETE')
    if not data.get('success', True):
        raise CloudflareStreamError(f'Cloudflare nao apagou o canal ao vivo: {data.get("errors")}')
    return data
