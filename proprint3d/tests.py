from django.test import TestCase, Client
from django.contrib.auth.models import User
from decimal import Decimal
import datetime

from proprint3d.models import Customer, Order, OrderItem, Branch, UserProfile, Filament
from proprint3d.utils.correos_rates import (
    calculate_all_correos_options,
    calculate_volumetric_weight_grams,
    CARTA_CERTIFICADA_RATES,
    PAQ_LIGERO_RATES,
    PAQ_ESTANDAR_RATES
)


class CorreosRatesTestCase(TestCase):
    def test_carta_certificada_tramos(self):
        """Verifica los tramos oficiales de Carta Certificada 2026."""
        # 0 a 20g (sumando tara o peso neto)
        res_20g = calculate_all_correos_options(weight_grams=20, packaging_margin_grams=0)
        cc_20g = next(opt for opt in res_20g['options'] if opt['code'] == 'Carta Certificada')
        self.assertEqual(cc_20g['price'], Decimal('5.74'))

        # 50g
        res_50g = calculate_all_correos_options(weight_grams=50, packaging_margin_grams=0)
        cc_50g = next(opt for opt in res_50g['options'] if opt['code'] == 'Carta Certificada')
        self.assertEqual(cc_50g['price'], Decimal('5.93'))

        # 100g
        res_100g = calculate_all_correos_options(weight_grams=100, packaging_margin_grams=0)
        cc_100g = next(opt for opt in res_100g['options'] if opt['code'] == 'Carta Certificada')
        self.assertEqual(cc_100g['price'], Decimal('6.53'))

        # 500g
        res_500g = calculate_all_correos_options(weight_grams=500, packaging_margin_grams=0)
        cc_500g = next(opt for opt in res_500g['options'] if opt['code'] == 'Carta Certificada')
        self.assertEqual(cc_500g['price'], Decimal('8.48'))

        # 1000g
        res_1000g = calculate_all_correos_options(weight_grams=1000, packaging_margin_grams=0)
        cc_1000g = next(opt for opt in res_1000g['options'] if opt['code'] == 'Carta Certificada')
        self.assertEqual(cc_1000g['price'], Decimal('11.68'))

        # 2000g (Límite máximo)
        res_2000g = calculate_all_correos_options(weight_grams=2000, packaging_margin_grams=0)
        cc_2000g = next(opt for opt in res_2000g['options'] if opt['code'] == 'Carta Certificada')
        self.assertEqual(cc_2000g['price'], Decimal('12.23'))
        self.assertTrue(cc_2000g['is_available'])

        # Supera 2000g -> no disponible para Carta Certificada
        res_2500g = calculate_all_correos_options(weight_grams=2500, packaging_margin_grams=0)
        cc_2500g = next(opt for opt in res_2500g['options'] if opt['code'] == 'Carta Certificada')
        self.assertFalse(cc_2500g['is_available'])

    def test_default_recommendation_and_packaging_tare(self):
        """Comprueba que por defecto se recomienda Carta Certificada sumando 100g de tara."""
        # Pieza de 220g + 100g tara = 320g -> Título <= 500g -> 8.48€
        analysis = calculate_all_correos_options(weight_grams=220, packaging_margin_grams=100)
        self.assertEqual(analysis['real_weight_grams'], 320)
        self.assertIsNotNone(analysis['recommended'])
        self.assertEqual(analysis['recommended']['code'], 'Carta Certificada')
        self.assertEqual(analysis['recommended']['price'], Decimal('8.48'))

    def test_volumetric_weight_calculation(self):
        """Verifica la fórmula oficial (L x A x H) / 6000."""
        # 30 x 20 x 10 cm = 6000 cm3 / 6000 = 1 kg = 1000 gramos
        vol_g = calculate_volumetric_weight_grams(30, 20, 10)
        self.assertEqual(vol_g, 1000)

        # Si el volumen es mayor que el peso real en paquetería estándar, se factura por volumen
        analysis = calculate_all_correos_options(
            weight_grams=200, # 200g real + 100g tara = 300g
            packaging_margin_grams=100,
            dimensions_cm=(30, 30, 20) # 18.000 / 6000 = 3 kg volumétrico (3000g)
        )
        self.assertEqual(analysis['volumetric_weight_grams'], 3000)
        self.assertEqual(analysis['billable_weight_grams'], 3000)


class CustomerAndOrderShippingTestCase(TestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(username='admin', password='password123', is_staff=True)
        self.client = Client()
        self.client.login(username='admin', password='password123')

    def test_customer_creation_and_order_linking(self):
        """Crea un cliente habitual y verifica su vinculación al pedido."""
        cust = Customer.objects.create(
            name="Marta García",
            phone="612345678",
            email="marta@example.com",
            address="C/ Marina 45, 2º 1ª",
            postal_code="08005",
            city="Barcelona",
            province="Barcelona"
        )
        self.assertEqual(cust.full_address, "C/ Marina 45, 2º 1ª\n08005 Barcelona")

        order = Order.objects.create(
            customer=cust,
            client_name=cust.name,
            client_contact=cust.phone,
            order_date=datetime.date.today(),
            shipping_address=cust.address,
            shipping_postal_code=cust.postal_code,
            shipping_city=cust.city,
            shipping_province=cust.province,
            correos_service="carta_certificada",
            tracking_number="PK123456789ES",
            price=Decimal('50.00'),
            total_cost=Decimal('15.00'),
            shipping_cost=Decimal('8.48'),
            shipping_cost_paid_by='seller' # El taller asume el envío
        )

        OrderItem.objects.create(
            order=order,
            description="Lámpara Voronoi",
            quantity=1,
            weight_grams=220.0,
            unit_cost=Decimal('15.00'),
            total_cost=Decimal('15.00'),
            unit_price=Decimal('50.00'),
            price=Decimal('50.00')
        )

        # Ganancia: 50.00 - 15.00 - 8.48 (envío) = 26.52€
        self.assertEqual(order.profit, Decimal('26.52'))

        # Tracking URL
        self.assertIn("PK123456789ES", order.correos_tracking_url)

        # Peso total estimado: 220g + 100g tara = 320g
        self.assertEqual(order.calculated_total_weight_grams, 320)

    def test_thermal_label_view(self):
        """Verifica que la plantilla de etiqueta térmica de 58mm se renderiza correctamente."""
        order = Order.objects.create(
            client_name="Carlos Ruiz",
            client_contact="677889900",
            order_date=datetime.date.today(),
            shipping_address="Av. Diagonal 200",
            shipping_postal_code="08018",
            shipping_city="Barcelona",
            shipping_province="Barcelona",
            correos_service="carta_certificada",
            tracking_number="CD987654321ES",
            price=Decimal('25.00')
        )
        OrderItem.objects.create(
            order=order,
            description="Pieza Soporte",
            quantity=1,
            weight_grams=150.0,
            price=Decimal('25.00')
        )

        response = self.client.get(f'/crm/order/{order.id}/thermal-label/')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        # Verificar datos del remitente fijo
        self.assertIn("Eleazar Hernández", content)
        self.assertIn("C/ Empordá 136", content)
        self.assertIn("08186", content)

        # Verificar QR
        self.assertIn("proprint3d.shop", content)

        # Verificar destinatario
        self.assertIn("Carlos Ruiz", content)
        self.assertIn("Av. Diagonal 200", content)
        self.assertIn("08018", content)

        # Verificar que el teléfono NO aparece en la etiqueta (privacidad acordada)
        self.assertNotIn("677889900", content)

        # Verificar línea de corte y datos internos al final
        self.assertIn("CORTAR ANTES DE PEGAR", content)
        self.assertIn(f"Pedido:</strong> #{order.id}", content)
        self.assertIn("Peso est.:</strong> 250g", content) # 150g pieza + 100g caja

    def test_api_shipping_calculate_exact_tare(self):
        """Verifica que la API sume exactamente 100g de tara una sola vez (220g + 100g = 320g)."""
        response = self.client.get('/crm/api/shipping/calculate/?weight_grams=220&add_tare=1')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        analysis = data['shipping_analysis']
        # El peso total debe ser 320g (no 420g)
        self.assertEqual(analysis['real_weight_grams'], 320)
        # La opción recomendada es Carta Certificada a 8.48€
        self.assertEqual(analysis['recommended']['code'], 'Carta Certificada')
        self.assertEqual(analysis['recommended']['price'], '8.48')

    def test_client_phone_and_email_fields(self):
        """Verifica que el teléfono y el email se almacenen por separado y sincronicen el contacto."""
        order = Order.objects.create(
            client_name="Laura Pons",
            client_phone="655443322",
            client_email="laura@example.com",
            order_date=datetime.date.today(),
            price=Decimal('20.00'),
            total_cost=Decimal('5.00')
        )
        self.assertEqual(order.client_phone, "655443322")
        self.assertEqual(order.client_email, "laura@example.com")
        self.assertIn("655443322", order.client_contact)
        self.assertIn("laura@example.com", order.client_contact)

    def test_include_shipping_in_total_and_profit(self):
        """Verifica que si include_shipping_in_total=True, el envío se sume al presupuesto y la ganancia se mantenga neta."""
        order = Order.objects.create(
            client_name="Pere Valls",
            order_date=datetime.date.today(),
            shipping_cost=Decimal('6.53'),
            shipping_cost_paid_by='client',
            include_shipping_in_total=True
        )
        OrderItem.objects.create(
            order=order,
            description="Llavero 3D",
            quantity=2,
            unit_cost=Decimal('2.00'),
            total_cost=Decimal('4.00'),
            unit_price=Decimal('10.00'),
            price=Decimal('20.00')
        )
        order.update_totals_from_items()
        # Total cobrado al cliente = 20.00 (piezas) + 6.53 (envío) = 26.53€
        self.assertEqual(order.price, Decimal('26.53'))
        # Beneficio neto del taller = 20.00 (piezas) - 4.00 (coste) = 16.00€
        self.assertEqual(order.profit, Decimal('16.00'))

    def test_api_postal_code_lookup(self):
        """Comprueba el endpoint de autocompletado de provincia por código postal."""
        response = self.client.get('/crm/api/postal-code/08186/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['postal_code'], '08186')
        self.assertEqual(data['province'], 'Barcelona')

    def test_about_view_renders_reviews(self):
        """Verifica que la vista 'quienes-somos' cargue las reviews activas."""
        from proprint3d.models import Review
        Review.objects.create(client_name="Test User", text="Excelente calidad", rating=5, is_active=True)
        response = self.client.get('/quienes-somos/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test User")
        self.assertContains(response, "Excelente calidad")

    def test_reviews_auto_seed_when_empty(self):
        """Verifica que si no hay reviews en la base de datos, get_verified_reviews siembra automáticamente."""
        from proprint3d.models import Review
        from proprint3d.utils.reviews_seed import get_verified_reviews
        Review.objects.all().delete()
        self.assertEqual(Review.objects.count(), 0)
        reviews = get_verified_reviews(limit=10)
        self.assertGreaterEqual(len(reviews), 5)
        self.assertEqual(Review.objects.count(), 9)

    def test_catalog_pdf_generation_view(self):
        """Verifica la generación del PDF del catálogo para staff."""
        from proprint3d.models import Category, Product
        cat = Category.objects.create(name="Navidad", slug="navidad")
        Product.objects.create(title="Árbol 3D", price=Decimal('15.00'), is_active=True)
        
        # Como admin logueado con opciones personalizadas
        response = self.client.get('/crm/catalogo-pdf/?categories=navidad&include_prices=0&include_descriptions=1&custom_title=Edicion+Especial')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('Catalogo_ProPrint3D_Edicion_Especial_', response['Content-Disposition'])

        # Como usuario no autenticado -> redirige al login
        anon_client = Client()
        anon_res = anon_client.get('/crm/catalogo-pdf/navidad/')
        self.assertEqual(anon_res.status_code, 302)
        self.assertIn('/login/', anon_res['Location'])

    def test_order_quote_pdf_with_shipping(self):
        """Verifica que el PDF del presupuesto de pedido incluya el envío tras el subtotal."""
        order = Order.objects.create(
            client_name="Enrique Puig",
            client_contact="660112233",
            order_date=datetime.date.today(),
            shipping="Correos",
            correos_service="carta_certificada",
            tracking_number="CD0C8E0000199330028907K",
            shipping_cost=Decimal('5.50'),
            include_shipping_in_total=True,
            unit_price=Decimal('20.00'),
            price=Decimal('25.50')
        )
        self.assertIn("tracking-number=CD0C8E0000199330028907K", order.correos_tracking_url)

        response = self.client.get(f'/crm/order/{order.id}/quote-pdf/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('Presupuesto_Enrique_Puig_', response['Content-Disposition'])

        # Comprobar que en el HTML renderizado aparezca el número de tracking, link y web
        from django.template.loader import render_to_string
        from proprint3d.views import get_quote_logo_base64

        logo_b64 = get_quote_logo_base64()
        self.assertTrue(logo_b64.startswith("data:image/png;base64,"))

        html = render_to_string('quote_pdf.html', {
            'logo_b64': logo_b64,
            'quote': {
                'id': order.id,
                'client_name': order.client_name,
                'client_contact': order.client_contact,
                'subtotal': '20.00',
                'shipping_cost': '5.50',
                'shipping_title': 'Envío certificado',
                'tracking_number': order.tracking_number,
                'tracking_url': order.correos_tracking_url,
                'total_price': '25.50',
                'items': [],
            }
        })
        self.assertIn("CD0C8E0000199330028907K", html)
        self.assertIn("Envío certificado", html)
        self.assertIn(order.correos_tracking_url, html)
        self.assertIn("www.proprint3d.shop", html)

        # Verificar que el número de seguimiento NO está en Datos del Cliente
        client_section = html.split('<div class="client-section">')[1].split('</div>')[0]
        self.assertNotIn(order.tracking_number, client_section)

    def test_order_quote_pdf_without_shipping_in_total(self):
        """Verifica que si include_shipping_in_total=False, el envío NO aparezca en el presupuesto ni se sume al total."""
        from unittest.mock import patch
        from django.template.loader import render_to_string

        order = Order.objects.create(
            client_name="Maria Gomez",
            client_contact="660998877",
            order_date=datetime.date.today(),
            shipping="Correos",
            correos_service="carta_certificada",
            tracking_number="CD0C8E0000199330028999X",
            shipping_cost=Decimal('5.50'),
            include_shipping_in_total=False,
            unit_price=Decimal('20.00'),
            price=Decimal('20.00')
        )
        with patch('proprint3d.views.render_to_string', wraps=render_to_string) as mock_render:
            response = self.client.get(f'/crm/order/{order.id}/quote-pdf/')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response['Content-Type'], 'application/pdf')
            self.assertIn('Presupuesto_Maria_Gomez_', response['Content-Disposition'])

            # Verificar el contexto pasado a la plantilla
            context = mock_render.call_args[0][1]
            quote = context['quote']
            self.assertIsNone(quote['shipping_cost'])
            self.assertIsNone(quote['shipping_title'])
            self.assertEqual(quote['total_price'], '20.00')
            self.assertFalse(quote['include_shipping_in_total'])

            # Verificar el HTML generado
            rendered_html = render_to_string('quote_pdf.html', context)
            self.assertNotIn('5.50', rendered_html)
            self.assertNotIn('Envío certificado', rendered_html)
            self.assertNotIn('Incluido', rendered_html)


class BranchMultiSiteTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.branch_espana, _ = Branch.objects.get_or_create(
            slug='espana',
            defaults={
                'name': 'España',
                'whatsapp': '34660904515',
                'phone': '+34 660 90 45 15',
                'greeting_name': 'ProPrint3D',
                'is_main': True,
                'is_active': True,
            }
        )
        self.branch_canarias, _ = Branch.objects.get_or_create(
            slug='canarias',
            defaults={
                'name': 'Canarias',
                'whatsapp': '34697868621',
                'phone': '+34 697 86 86 21',
                'greeting_name': 'ProPrint3D Canarias',
                'city': 'Santa Cruz de Tenerife',
                'is_main': False,
                'is_active': True,
            }
        )
        self.branch_canarias.city = 'Santa Cruz de Tenerife'
        self.branch_canarias.save()
        self.superadmin = User.objects.create_superuser('superadmin', 'admin@example.com', 'password123')
        self.canarias_user = User.objects.create_user('canarias_admin', 'canarias@example.com', 'password123', is_staff=True)
        self.canarias_user.profile.branch = self.branch_canarias
        self.canarias_user.profile.save()

        # Crear pedidos de prueba
        self.order_esp = Order.objects.create(
            branch=self.branch_espana,
            client_name="Cliente Península",
            order_date=datetime.date.today(),
            price=Decimal('25.00')
        )
        self.order_can = Order.objects.create(
            branch=self.branch_canarias,
            client_name="Cliente Tenerife",
            order_date=datetime.date.today(),
            price=Decimal('40.00')
        )

    def test_switch_branch_view(self):
        """Verifica que cambiar de sede guarde la elección en la sesión."""
        response = self.client.get('/cambiar-sede/canarias/', follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.session.get('branch_slug'), 'canarias')

    def test_branch_context_processor(self):
        """Verifica que el context processor inyecte el WhatsApp correcto."""
        # Sin seleccionar: defecto España
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['current_whatsapp'], '34660904515')

        # Con cambio a Canarias
        self.client.get('/cambiar-sede/canarias/')
        response = self.client.get('/')
        self.assertEqual(response.context['current_whatsapp'], '34697868621')
        self.assertTrue(response.context['is_canarias'])

    def test_crm_branch_isolation(self):
        """El administrador de Canarias solo ve los pedidos de Canarias en el CRM."""
        self.client.force_login(self.canarias_user)
        response = self.client.get('/crm/')
        self.assertEqual(response.status_code, 200)
        # Debe ver Cliente Tenerife pero NO Cliente Península
        self.assertContains(response, "Cliente Tenerife")
        self.assertNotContains(response, "Cliente Península")

    def test_crm_superadmin_defaults_to_espana(self):
        """El superadmin entra por defecto a la vista de España (Península)."""
        self.client.force_login(self.superadmin)
        response = self.client.get('/crm/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['selected_branch_slug'], 'espana')
        self.assertContains(response, "Cliente Península")
        self.assertNotContains(response, "Cliente Tenerife")

        # Al elegir 'all', ve ambos con distintivo
        response_all = self.client.get('/crm/?branch=all')
        self.assertTrue(response_all.context['is_all_branches_view'])
        self.assertContains(response_all, "Cliente Península")
        self.assertContains(response_all, "Cliente Tenerife")

    def test_catalog_pdf_canarias_data(self):
        """Verifica que el catálogo generado para Canarias use el teléfono y dirección de Santa Cruz de Tenerife."""
        from proprint3d.utils.catalog_pdf import build_catalog_context
        ctx_canarias = build_catalog_context(branch=self.branch_canarias)
        self.assertEqual(ctx_canarias['whatsapp_display'], '697 868 621')
        self.assertEqual(ctx_canarias['location'], 'Santa Cruz de Tenerife')

        ctx_espana = build_catalog_context(branch=self.branch_espana)
        self.assertEqual(ctx_espana['whatsapp_display'], '660 904 515')
        self.assertIn('Barcelona', ctx_espana['location'])

    def test_crm_superadmin_creates_order_in_canarias(self):
        """Verifica que el superadmin en el CRM de Canarias cree el pedido en Canarias y se refleje allí."""
        self.client.force_login(self.superadmin)
        
        # 1. Visitar CRM Canarias
        crm_can = self.client.get('/crm/?branch=canarias')
        self.assertEqual(crm_can.status_code, 200)
        self.assertEqual(crm_can.context['selected_branch_slug'], 'canarias')

        # 2. Abrir formulario de nuevo pedido
        new_order_page = self.client.get('/crm/order/new/?branch=canarias')
        self.assertEqual(new_order_page.status_code, 200)
        self.assertEqual(new_order_page.context['target_branch'].slug, 'canarias')

        # 3. Crear pedido con sede Canarias
        import json
        post_data = {
            'client_name': 'Cliente Canarias Especial',
            'client_phone': '699112233',
            'client_email': 'canarias@especial.es',
            'order_date': str(datetime.date.today()),
            'status': 'Presupuestado',
            'branch_slug': 'canarias',
            'pieces_json': json.dumps([{
                'description': 'Llavero Canarias',
                'quantity': 3,
                'weight_grams': 25,
                'print_time_hours': 1,
                'print_time_minutes': 0,
                'unit_price': 10.0,
                'price': 30.0,
            }]),
            'save_as_customer': 'true',
        }
        resp = self.client.post('/crm/order/new/', post_data)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('branch=canarias', resp.url)

        # 4. Verificar que el pedido existe y pertenece a Canarias
        order = Order.objects.filter(client_name='Cliente Canarias Especial').first()
        self.assertIsNotNone(order)
        self.assertEqual(order.branch, self.branch_canarias)

        # 5. Comprobar que aparece en CRM Canarias y NO en España
        crm_canarias = self.client.get('/crm/?branch=canarias')
        self.assertContains(crm_canarias, "Cliente Canarias Especial")

        crm_espana = self.client.get('/crm/?branch=espana')
        self.assertNotContains(crm_espana, "Cliente Canarias Especial")

    def test_api_customers_search_live_filtering(self):
        """Verifica que el buscador de clientes en agenda filtre en vivo por nombre y teléfono sin errores."""
        self.client.force_login(self.superadmin)
        customer = Customer.objects.create(
            name="Laura Sanchez",
            phone="+34 654 32 10 98",
            email="laura@test.es",
            city="Las Palmas",
            postal_code="35001",
            branch=self.branch_canarias
        )

        # Búsqueda por nombre
        res_name = self.client.get('/crm/api/customers/search/?q=Laura')
        self.assertEqual(res_name.status_code, 200)
        data_name = res_name.json()
        self.assertTrue(data_name['success'])
        self.assertTrue(any(c['name'] == 'Laura Sanchez' for c in data_name['customers']))

        # Búsqueda por dígitos de teléfono
        res_phone = self.client.get('/crm/api/customers/search/?q=654321')
        self.assertEqual(res_phone.status_code, 200)
        data_phone = res_phone.json()
        self.assertTrue(data_phone['success'])
        self.assertTrue(any(c['name'] == 'Laura Sanchez' for c in data_phone['customers']))

    def test_order_quote_pdf_canarias_branch_data(self):
        """Verifica que el presupuesto en PDF para un pedido de Canarias muestre la sede, teléfono y ubicación de Canarias."""
        self.client.force_login(self.superadmin)
        order = Order.objects.create(
            branch=self.branch_canarias,
            client_name="Cliente Tenerife Presupuesto",
            client_phone="697868621",
            client_contact="697868621",
            order_date=datetime.date.today(),
            price=Decimal('75.00'),
            status='Presupuestado'
        )
        OrderItem.objects.create(
            order=order,
            description="Pieza 3D Canarias",
            quantity=1,
            unit_price=Decimal('75.00'),
            price=Decimal('75.00')
        )

        resp = self.client.get(f'/crm/order/{order.id}/quote-pdf/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertTrue(len(resp.content) > 1000)

        # Verificar renderizado de plantilla
        from django.template.loader import render_to_string
        from proprint3d.views import get_quote_logo_base64
        quote_data = {
            'id': order.id,
            'client_name': order.client_name,
            'client_contact': order.client_contact,
            'created_at': order.order_date,
            'items': [{'custom_title': 'Pieza 3D Canarias', 'quantity': 1, 'unit_price': '75.00', 'calculated_cost': '75.00'}],
            'subtotal': '75.00',
            'total_price': '75.00',
            'branch': self.branch_canarias,
        }
        html = render_to_string('quote_pdf.html', {
            'quote': quote_data,
            'order': order,
            'quote_branch': self.branch_canarias,
            'logo_b64': get_quote_logo_base64(),
        })
        self.assertIn("ProPrint3D Canarias", html)
        self.assertIn("Santa Cruz de Tenerife", html)
        self.assertIn("697 868 621", html)
        self.assertIn("SEDE CANARIAS", html)


class FilamentManagementTestCase(TestCase):
    def setUp(self):
        self.branch_espana, _ = Branch.objects.get_or_create(
            slug="espana",
            defaults={"name": "Sede Península", "is_main": True}
        )
        self.branch_canarias, _ = Branch.objects.get_or_create(
            slug="canarias",
            defaults={"name": "Sede Canarias", "is_main": False}
        )
        self.user = User.objects.create_superuser(username="admin_filamentos", password="password123")
        self.client = Client()
        self.client.force_login(self.user)

    def test_filament_creation_and_branch_scoping(self):
        """Verifica la creación con código y unicidad por sede."""
        from django.db import IntegrityError

        fil_es = Filament.objects.create(
            branch=self.branch_espana,
            code=4,
            brand="eSun",
            material="PLA+",
            color_name="Gris Espacial",
            color_hex="#808080",
            spools_closed=2,
            spools_opened=1,
            min_closed_alert=1
        )
        self.assertEqual(fil_es.display_name, "#4 eSun PLA+ Gris Espacial")
        self.assertFalse(fil_es.is_low_stock)

        # Mismo código en Canarias es válido porque está en otra sede
        fil_can = Filament.objects.create(
            branch=self.branch_canarias,
            code=4,
            brand="Elegoo",
            material="PETG",
            color_name="Negro",
            color_hex="#000000"
        )
        self.assertEqual(fil_can.branch.slug, "canarias")

        # Mismo código en la misma sede España debe fallar por unique_together
        with self.assertRaises(IntegrityError):
            Filament.objects.create(
                branch=self.branch_espana,
                code=4,
                brand="Sunlu",
                material="PLA",
                color_name="Blanco"
            )

    def test_filament_stock_adjust_api(self):
        """Prueba la API de ajuste rápido de bobinas y apertura de bobinas."""
        import json

        fil = Filament.objects.create(
            branch=self.branch_espana,
            code=7,
            brand="Bambu Lab",
            material="PLA Basic",
            color_name="Verde Menta",
            color_hex="#00FF99",
            spools_closed=3,
            spools_opened=1,
            min_closed_alert=2
        )

        # 1. Abrir bobina: resta 1 a cerradas y suma 1 a abiertas
        res_open = self.client.post(
            "/crm/filamentos/api/adjust-stock/",
            data=json.dumps({"filament_id": fil.id, "action": "open_spool"}),
            content_type="application/json"
        )
        self.assertEqual(res_open.status_code, 200)
        data = res_open.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["spools_closed"], 2)
        self.assertEqual(data["spools_opened"], 2)

        # 2. Restar 1 a cerradas: ahora queda 1 cerrada (<= min_closed_alert=2 => is_low_stock True)
        res_dec = self.client.post(
            "/crm/filamentos/api/adjust-stock/",
            data=json.dumps({"filament_id": fil.id, "action": "dec_closed"}),
            content_type="application/json"
        )
        self.assertEqual(res_dec.status_code, 200)
        data_dec = res_dec.json()
        self.assertEqual(data_dec["spools_closed"], 1)
        self.assertTrue(data_dec["is_low_stock"])

    def test_order_item_filament_association_and_all_filaments(self):
        """Verifica la asignación de filamentos a piezas y la propiedad agregada order.all_filaments."""
        fil1 = Filament.objects.create(branch=self.branch_espana, code=1, brand="eSun", material="PLA", color_name="Negro")
        fil2 = Filament.objects.create(branch=self.branch_espana, code=2, brand="eSun", material="PLA", color_name="Blanco")

        order = Order.objects.create(
            branch=self.branch_espana,
            client_name="Cliente Filamentos",
            status="Presupuestado",
            order_date=datetime.date.today()
        )

        item1 = OrderItem.objects.create(order=order, description="Pieza Bicolor", quantity=1)
        item1.filaments.add(fil1, fil2)

        item2 = OrderItem.objects.create(order=order, description="Pieza Monocolor", quantity=2)
        item2.filaments.add(fil1)

        # Consolida sin duplicar: debe tener fil1 y fil2
        all_fils = order.all_filaments
        self.assertEqual(len(all_fils), 2)
        fil_codes = {f.code for f in all_fils}
        self.assertEqual(fil_codes, {1, 2})

    def test_order_edit_api_saves_filaments(self):
        """Verifica que el endpoint de edición de pedidos guarde los filament_ids de cada pieza."""
        import json

        fil4 = Filament.objects.create(branch=self.branch_espana, code=4, brand="eSun", material="PLA", color_name="Gris")
        order = Order.objects.create(
            branch=self.branch_espana,
            client_name="Cliente API Edit",
            status="Presupuestado",
            order_date=datetime.date.today()
        )
        item = OrderItem.objects.create(order=order, description="Soporte Auriculares", quantity=1)

        payload = {
            "client_name": "Cliente API Edit",
            "order_date": str(datetime.date.today()),
            "status": "En proceso",
            "pieces": [
                {
                    "id": item.id,
                    "description": "Soporte Auriculares Modificado",
                    "quantity": 1,
                    "filament_ids": [fil4.id]
                }
            ]
        }

        res = self.client.post(
            f"/crm/api/order/{order.id}/edit/",
            data=json.dumps(payload),
            content_type="application/json"
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json().get("success"))

        item.refresh_from_db()
        self.assertEqual(item.filaments.count(), 1)
        self.assertEqual(item.filaments.first().code, 4)



