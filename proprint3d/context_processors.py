from .models import Cart, Category, Branch

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
        'all_categories': Category.objects.all().order_by('name'),
    }


def branch_context(request):
    """
    Context processor para inyectar la sede activa (España vs Canarias)
    en todas las plantillas de la web pública y panel.
    """
    # 1. Detectar si viene por parámetro GET (?sede=canarias o ?branch=canarias)
    param_branch = request.GET.get('sede') or request.GET.get('sucursal') or request.GET.get('branch')
    if param_branch:
        param_clean = param_branch.strip().lower()
        if Branch.objects.filter(slug=param_clean, is_active=True).exists():
            request.session['branch_slug'] = param_clean

    # 2. Obtener la sede desde la sesión
    branch_slug = request.session.get('branch_slug')
    current_branch = None
    if branch_slug:
        current_branch = Branch.objects.filter(slug=branch_slug, is_active=True).first()

    # 3. Si no hay sede en sesión o no es válida, recurrir a la principal (España)
    if not current_branch:
        current_branch = Branch.objects.filter(is_main=True, is_active=True).first()
    if not current_branch:
        current_branch = Branch.objects.filter(is_active=True).first()

    all_branches = list(Branch.objects.filter(is_active=True).order_by('-is_main', 'name'))

    whatsapp_number = current_branch.whatsapp if current_branch else "34660904515"
    greeting_name = current_branch.greeting_name if current_branch else "ProPrint3D"

    return {
        'current_branch': current_branch,
        'all_branches': all_branches,
        'current_whatsapp': whatsapp_number,
        'current_greeting': greeting_name,
        'is_canarias': bool(current_branch and current_branch.slug == 'canarias'),
    }

