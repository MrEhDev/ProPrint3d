"""
Módulo de cálculo de tarifas oficiales de Correos España (Península y Baleares) - Tarifas Oficiales 2026.
Permite calcular el coste de envío exacto por tramos de peso y dimensiones volumétricas.
"""

import math
from decimal import Decimal

# Tarifas 2026 Península y Baleares (Precios finales PVP en Euros)

# Carta Certificada Nacional (Exenta de IVA, seguimiento incluido, máx 2.000 g)
CARTA_CERTIFICADA_RATES = [
    (20, Decimal('5.74')),
    (50, Decimal('5.93')),
    (100, Decimal('6.53')),
    (500, Decimal('8.48')),
    (1000, Decimal('11.68')),
    (2000, Decimal('12.23')),
]

# Paq Ligero Nacional (Entrega en domicilio, PVP con IVA, máx 2.000 g)
PAQ_LIGERO_RATES = [
    (250, Decimal('6.06')),
    (500, Decimal('7.56')),
    (1000, Decimal('10.61')),
    (2000, Decimal('12.64')),
]

# Paq Estándar Nacional (Entrega en domicilio/oficina, PVP con IVA, hasta 30 kg)
PAQ_ESTANDAR_RATES = [
    (1000, Decimal('13.65')),
    (5000, Decimal('17.10')),
    (10000, Decimal('22.95')),
    (15000, Decimal('27.81')),
    (20000, Decimal('33.65')),
    (25000, Decimal('39.01')),
    (30000, Decimal('44.25')),
]
PAQ_ESTANDAR_EXTRA_KG = Decimal('1.36')

PACKAGING_TARE_DEFAULT_GRAMS = 100

CORREOS_SERVICES = [
    ('carta_certificada', 'Carta Certificada (Correos)'),
    ('paq_ligero', 'Paq Ligero (Correos)'),
    ('paq_estandar', 'Paq Estándar (Correos)'),
    ('paq_premium', 'Paq Premium (Correos)'),
]

# Paq Premium Nacional (Entrega urgente 24h domicilio/oficina, PVP con IVA, hasta 30 kg)
PAQ_PREMIUM_RATES = [
    (1000, Decimal('15.35')),
    (5000, Decimal('18.90')),
    (10000, Decimal('24.74')),
    (15000, Decimal('29.45')),
    (20000, Decimal('35.90')),
    (25000, Decimal('42.50')),
    (30000, Decimal('48.90')),
]
PAQ_PREMIUM_EXTRA_KG = Decimal('1.40')


def calculate_volumetric_weight_grams(length_cm, width_cm, height_cm):
    """
    Fórmula oficial de Correos: (Largo x Ancho x Alto en cm) / 6.000
    Devuelve el peso volumétrico expresado en gramos.
    """
    try:
        vol_kg = (float(length_cm) * float(width_cm) * float(height_cm)) / 6000.0
        return int(math.ceil(vol_kg * 1000))
    except (TypeError, ValueError, ZeroDivisionError):
        return 0


def get_rate_for_table(table, weight_grams, extra_per_kg=None, max_base=30000):
    """Devuelve el precio correspondiente para un peso en gramos según la tabla."""
    for max_g, price in table:
        if weight_grams <= max_g:
            return price
            
    if extra_per_kg and weight_grams > max_base:
        last_max, last_price = table[-1]
        extra_kg = math.ceil((weight_grams - last_max) / 1000.0)
        return last_price + (Decimal(str(extra_kg)) * extra_per_kg)
        
    return None


def calculate_correos_rate(service_code, weight_grams, length_cm=None, width_cm=None, height_cm=None, destination='peninsula'):
    """
    Calcula la tarifa específica para un servicio dado y un peso/volumen.
    """
    options_data = calculate_all_correos_options(
        weight_grams=weight_grams,
        length_cm=length_cm,
        width_cm=width_cm,
        height_cm=height_cm,
        destination=destination
    )
    code_normalized = service_code.lower().replace(' ', '_').replace('á', 'a')
    for opt in options_data['options']:
        opt_code = opt['code'].lower().replace(' ', '_').replace('á', 'a')
        if opt_code == code_normalized:
            return opt['price']
    return None


def calculate_all_correos_options(weight_grams, dimensions_cm=None, packaging_margin_grams=100, length_cm=None, width_cm=None, height_cm=None, destination='peninsula'):
    """
    Calcula todas las opciones disponibles de Correos 2026.
    
    Retorna un diccionario con:
    - real_weight_grams: Peso de las piezas + margen de caja
    - volumetric_weight_grams: Peso volumétrico calculado (si se pasan dimensiones)
    - billable_weight_grams: Mayor entre peso real y volumétrico (para paquetería)
    - options: Lista con detalles de cada servicio (nombre, precio, disponible, notas)
    - recommended: La opción recomendada (predetermina Carta Certificada si <= 2kg)
    """
    real_weight = int(weight_grams or 0) + int(packaging_margin_grams or 0)
    vol_weight = 0
    
    if length_cm and width_cm and height_cm:
        vol_weight = calculate_volumetric_weight_grams(length_cm, width_cm, height_cm)
    elif dimensions_cm:
        if isinstance(dimensions_cm, (list, tuple)) and len(dimensions_cm) == 3:
            vol_weight = calculate_volumetric_weight_grams(dimensions_cm[0], dimensions_cm[1], dimensions_cm[2])
        elif isinstance(dimensions_cm, str) and 'x' in dimensions_cm.lower():
            parts = dimensions_cm.lower().replace('cm', '').split('x')
            if len(parts) == 3:
                vol_weight = calculate_volumetric_weight_grams(parts[0].strip(), parts[1].strip(), parts[2].strip())

    billable_for_parcels = max(real_weight, vol_weight)

    options = []

    # 1. Carta Certificada (No aplica peso volumétrico, solo peso real en báscula, máx 2.000 g)
    if real_weight <= 2000:
        price_cc = get_rate_for_table(CARTA_CERTIFICADA_RATES, real_weight)
        options.append({
            'code': 'Carta Certificada',
            'service_key': 'carta_certificada',
            'name': 'Carta Certificada (Correos)',
            'price': price_cc,
            'price_float': float(price_cc) if price_cc else 0.0,
            'is_available': True,
            'description': 'Con número de seguimiento. No aplica volumen (máx. 2 kg)',
            'is_default': True,
            'estimated_days': '2-3 días'
        })
    else:
        options.append({
            'code': 'Carta Certificada',
            'service_key': 'carta_certificada',
            'name': 'Carta Certificada (Correos)',
            'price': None,
            'price_float': None,
            'is_available': False,
            'description': 'Supera el límite de 2 kg para formato carta',
            'is_default': False,
            'estimated_days': '2-3 días'
        })

    # 2. Paq Ligero (Hasta 2.000 g)
    if billable_for_parcels <= 2000:
        price_pl = get_rate_for_table(PAQ_LIGERO_RATES, billable_for_parcels)
        options.append({
            'code': 'Paq Ligero',
            'service_key': 'paq_ligero',
            'name': 'Paq Ligero (Correos)',
            'price': price_pl,
            'price_float': float(price_pl) if price_pl else 0.0,
            'is_available': True,
            'description': 'Económico para paquetes pequeños a domicilio (máx. 2 kg)',
            'is_default': False,
            'estimated_days': '24-48h'
        })
    else:
        options.append({
            'code': 'Paq Ligero',
            'service_key': 'paq_ligero',
            'name': 'Paq Ligero (Correos)',
            'price': None,
            'price_float': None,
            'is_available': False,
            'description': 'Supera los 2 kg máximos de Paq Ligero',
            'is_default': False,
            'estimated_days': '24-48h'
        })

    # 3. Paq Estándar (Hasta 30 kg)
    price_pe = get_rate_for_table(PAQ_ESTANDAR_RATES, billable_for_parcels, PAQ_ESTANDAR_EXTRA_KG)
    options.append({
        'code': 'Paq Estándar',
        'service_key': 'paq_estandar',
        'name': 'Paq Estándar (Correos)',
        'price': price_pe,
        'price_float': float(price_pe) if price_pe else 0.0,
        'is_available': price_pe is not None,
        'description': 'Paquetería estándar nacional con seguimiento',
        'is_default': False,
        'estimated_days': '48-72h'
    })

    # 4. Paq Premium (Hasta 30 kg)
    price_pp = get_rate_for_table(PAQ_PREMIUM_RATES, billable_for_parcels, PAQ_PREMIUM_EXTRA_KG)
    options.append({
        'code': 'Paq Premium',
        'service_key': 'paq_premium',
        'name': 'Paq Premium (Correos)',
        'price': price_pp,
        'price_float': float(price_pp) if price_pp else 0.0,
        'is_available': price_pp is not None,
        'description': 'Entrega urgente prioritaria nacional',
        'is_default': False,
        'estimated_days': '24h'
    })

    # Determinar recomendación
    # Regla: Carta Certificada por defecto si <= 2000g, sino Paq Estándar
    recommended = None
    for opt in options:
        if opt['code'] == 'Carta Certificada' and opt['is_available']:
            recommended = opt
            break
            
    if not recommended:
        for opt in options:
            if opt['code'] == 'Paq Estándar' and opt['is_available']:
                recommended = opt
                break

    return {
        'real_weight_grams': real_weight,
        'volumetric_weight_grams': vol_weight,
        'billable_weight_grams': billable_for_parcels,
        'options': options,
        'recommended': recommended,
    }
