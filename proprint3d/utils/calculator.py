# =====================================================================
# MÓDULO: calculator.py
# Propósito: Aislar la lógica de cálculo de costes de impresión 3D
# de las vistas. Esto facilita las pruebas unitarias y el mantenimiento.
# =====================================================================

def calculate_print_costs(weight_grams, hours, minutes, other_materials_cost=0.0):
    """
    Función que calcula los costes de producción y sugiere precios de venta.
    
    Parámetros:
    - weight_grams (float): Peso en gramos del filamento consumido.
    - hours (int): Horas enteras estimadas de impresión.
    - minutes (int): Minutos restantes (0-59).
    - other_materials_cost (float): Coste adicional (pintura, insertos, etc.).
    
    Razón de la estructura: Extraer la matemática de las vistas para
    mantener el principio de Responsabilidad Única (SRP).
    """
    
    # -------------------------------------------------------------
    # 1. Convertir tiempo a formato decimal
    # Matemáticas: 60 minutos = 1 hora. Por tanto, minutos / 60
    # nos da la fracción de hora.
    # -------------------------------------------------------------
    total_hours = float(hours) + (float(minutes) / 60.0)
    
    # -------------------------------------------------------------
    # 2. Fórmulas Matemáticas de Costes Base
    # Coste filamento = 0.02€/g (precio promedio de PLA/PETG básico)
    # Coste energía = 0.15kW (consumo) * 0.12€/kWh * horas (esto asume tarifa 0.12€)
    # Coste desgaste = 0.025€/h (mantenimiento y depreciación máquina)
    # -------------------------------------------------------------
    cost_filament = 0.02 * float(weight_grams)
    cost_energy = 0.15 * 0.12 * total_hours
    cost_wear = 0.025 * total_hours
    
    # Subtotal directo sin margen de error
    cost_subtotal = cost_filament + cost_energy + cost_wear + float(other_materials_cost)
    
    # -------------------------------------------------------------
    # 3. Margen de Error y Coste Final de Producción
    # Matemáticas: Añadimos un 15% para absorber fallos de impresión,
    # purgas de filamento, etc.
    # -------------------------------------------------------------
    error_margin = cost_subtotal * 0.15
    final_production_cost = cost_subtotal + error_margin
    
    # -------------------------------------------------------------
    # 4. Cálculo de Precios de Venta Sugeridos
    # Matemáticas: (filamento + energia) * multiplicador + desgaste + margen
    # Según requisitos, desgaste, otros y margen no se multiplican.
    # -------------------------------------------------------------
    base_var = cost_filament + cost_energy
    fixed_costs = cost_wear + float(other_materials_cost) + error_margin
    
    price_x25 = (base_var * 2.5) + fixed_costs
    price_x30 = (base_var * 3.0) + fixed_costs
    price_x40 = (base_var * 4.0) + fixed_costs
    
    # Devolvemos un diccionario estructurado para renderizarlo fácil en templates o JSON
    return {
        "breakdown": {
            "filament": round(cost_filament, 2),
            "energy": round(cost_energy, 2),
            "wear": round(cost_wear, 2),
            "other": round(float(other_materials_cost), 2),
            "error_margin": round(error_margin, 2),
        },
        "production_cost": round(final_production_cost, 2),
        "suggested_prices": {
            "x2_5": round(price_x25, 2),
            "x3_0": round(price_x30, 2),
            "x4_0": round(price_x40, 2),
        }
    }
