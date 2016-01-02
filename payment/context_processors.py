from payment import settings

def paypal(request):
    """
    Adds PAYPAL variables to response
    """
    return {
        'PAYPAL_URL': settings.PAYPAL_URL,
        'PAYPAL_BUTTON_ID': settings.PAYPAL_BUTTON_ID
    }
