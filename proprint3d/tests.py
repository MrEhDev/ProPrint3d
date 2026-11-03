from django.test import TestCase, Client
from django.contrib.auth.models import User
from decimal import Decimal
import datetime

from proprint3d.models import Customer, Order, OrderItem
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
