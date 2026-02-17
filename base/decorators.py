from django.core.cache import cache
from django.http import JsonResponse, HttpResponse
from functools import wraps
import hashlib


def get_client_ip(request):
    """Get the client's IP address from the request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def rate_limit(max_requests=5, time_window=60, block_duration=300):
    """
    Rate limiting decorator.

    Args:
        max_requests: Maximum number of requests allowed
        time_window: Time window in seconds (default 60 seconds)
        block_duration: How long to block after limit exceeded (default 300 seconds = 5 minutes)
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            ip = get_client_ip(request)
            cache_key = f'rate_limit_{view_func.__name__}_{ip}'
            block_key = f'blocked_{view_func.__name__}_{ip}'

            # Check if IP is currently blocked
            if cache.get(block_key):
                if request.method == 'POST':
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Too many requests. Please try again later.'
                    }, status=429)
                else:
                    return HttpResponse('Too many requests. Please try again later.', status=429)

            # Get current request count
            request_count = cache.get(cache_key, 0)

            if request_count >= max_requests:
                # Block the IP
                cache.set(block_key, True, block_duration)
                cache.delete(cache_key)

                if request.method == 'POST':
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Too many requests. You have been temporarily blocked.'
                    }, status=429)
                else:
                    return HttpResponse('Too many requests. You have been temporarily blocked.', status=429)

            # Increment request count
            cache.set(cache_key, request_count + 1, time_window)

            return view_func(request, *args, **kwargs)
        return wrapped
    return decorator
