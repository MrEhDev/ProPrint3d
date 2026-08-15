from .models import Cart

def cart_context(request):
    cart_item_count = 0
    cart_total_price = 0
    
    if not request.session.session_key:
        request.session.create()
        
    session_key = request.session.session_key
    
    if session_key:
        cart = Cart.objects.filter(session_key=session_key).first()
        if cart:
            cart_item_count = sum(item.quantity for item in cart.items.all())
            cart_total_price = cart.total_price
            
    return {
        'cart_item_count': cart_item_count,
        'cart_total_price': cart_total_price,
    }
