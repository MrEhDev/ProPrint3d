import decimal
from collections import defaultdict
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count
from proprint3d.models import Order, OrderItem

class Command(BaseCommand):
    help = "Unifica pedidos de un mismo cliente en un único pedido multi-pieza, respetando piezas, costes y estados individuales."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Muestra una vista previa de la unificación sin aplicar cambios en la base de datos.',
        )
        parser.add_argument(
            '--by-date',
            action='store_true',
            help='Agrupa los pedidos del mismo cliente únicamente si coinciden en la fecha del pedido.',
        )
        parser.add_argument(
            '--client',
            type=str,
            default='',
            help='Filtra para unificar únicamente a un cliente en concreto (búsqueda parcial insensible a mayúsculas).',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        by_date = options['by_date']
        client_filter = options['client'].strip().lower()

        self.stdout.write(self.style.MIGRATE_HEADING("=== UNIFICADOR DE PEDIDOS POR CLIENTE ==="))
        if dry_run:
            self.stdout.write(self.style.WARNING("MODO SIMULACIÓN (DRY-RUN): No se aplicarán cambios a la base de datos.\n"))

        with transaction.atomic():
            # PASO 1: Asegurar que todos los pedidos existentes tengan al menos una pieza (OrderItem)
            # Esto soluciona de raíz el problema de pedidos antiguos que no tenían piezas asociadas.
            orders_missing_items = Order.objects.annotate(item_count=Count('items')).filter(item_count=0)
            created_items_count = 0

            for ord_obj in orders_missing_items:
                desc = ord_obj.description or (ord_obj.product.title if ord_obj.product else f"Pieza #{ord_obj.id}")
                if not dry_run:
                    OrderItem.objects.create(
                        order=ord_obj,
                        product=ord_obj.product,
                        description=desc,
                        quantity=ord_obj.quantity or 1,
                        weight_grams=ord_obj.weight_grams or 0.0,
                        print_time_hours=ord_obj.print_time_hours or 0.0,
                        print_time_minutes=ord_obj.print_time_minutes or 0,
                        extra_costs=ord_obj.extra_costs or decimal.Decimal('0.00'),
                        unit_cost=ord_obj.unit_cost or decimal.Decimal('0.00'),
                        total_cost=ord_obj.total_cost or decimal.Decimal('0.00'),
                        unit_price=ord_obj.unit_price or decimal.Decimal('0.00'),
                        price=ord_obj.price or decimal.Decimal('0.00'),
                        status=ord_obj.status or 'Presupuestado'
                    )
                created_items_count += 1

            if created_items_count > 0:
                self.stdout.write(self.style.SUCCESS(f"[PASO 1] Se crearon piezas (OrderItem) para {created_items_count} pedidos que estaban vacíos."))
            else:
                self.stdout.write("[PASO 1] Todos los pedidos ya contaban con piezas asociadas.")

            # PASO 2: Agrupar pedidos por nombre de cliente
            orders_qs = Order.objects.exclude(status='Cancelado').prefetch_related('items').order_by('id')
            groups = defaultdict(list)

            for o in orders_qs:
                cname = (o.client_name or '').strip()
                if not cname:
                    continue
                if client_filter and client_filter not in cname.lower():
                    continue

                if by_date:
                    key = (cname.lower(), o.order_date)
                else:
                    key = cname.lower()
                groups[key].append(o)

            unified_clients_count = 0
            merged_orders_total = 0
            total_pieces_unified = 0

            self.stdout.write("\n" + self.style.MIGRATE_HEADING("[PASO 2] Unificación de pedidos por cliente:"))

            for key, orders in groups.items():
                if len(orders) <= 1:
                    continue

                unified_clients_count += 1
                primary = orders[0]
                secondary_orders = orders[1:]
                merged_orders_total += len(secondary_orders)

                client_display = primary.client_name.strip()
                self.stdout.write(f"\n👉 Cliente: {self.style.SUCCESS(client_display)} ({len(orders)} pedidos -> consolidando en Pedido #{primary.id})")

                # Lista de todas las piezas que compondrán el pedido consolidado
                all_simulated_items = list(primary.items.all())

                # Fusionar piezas y atributos de los pedidos secundarios en el primario
                for sec in secondary_orders:
                    sec_items = list(sec.items.all())
                    for itm in sec_items:
                        total_pieces_unified += 1
                        all_simulated_items.append(itm)
                        self.stdout.write(f"   • Pieza transferida: '{itm.description}' (x{itm.quantity}, €{itm.price}) [Estado: {itm.status}] desde Pedido #{sec.id}")
                        if not dry_run:
                            itm.order = primary
                            itm.save()

                    # Acumular señales / pagos
                    sec_deposit = sec.deposit_amount or decimal.Decimal('0.00')
                    if sec_deposit > 0:
                        primary.deposit_amount = (primary.deposit_amount or decimal.Decimal('0.00')) + sec_deposit

                    # Copiar métodos si no los tenía el primario
                    if not primary.deposit_method and sec.deposit_method:
                        primary.deposit_method = sec.deposit_method
                    if not primary.final_payment_method and sec.final_payment_method:
                        primary.final_payment_method = sec.final_payment_method
                    if not primary.platform and sec.platform:
                        primary.platform = sec.platform
                    if not primary.shipping and sec.shipping:
                        primary.shipping = sec.shipping

                    # Fusionar notas
                    if sec.notes and sec.notes.strip():
                        if not primary.notes:
                            primary.notes = sec.notes.strip()
                        elif sec.notes.strip() not in primary.notes:
                            primary.notes = f"{primary.notes}\n{sec.notes.strip()}"

                    if sec.payment_notes and sec.payment_notes.strip():
                        if not primary.payment_notes:
                            primary.payment_notes = sec.payment_notes.strip()
                        elif sec.payment_notes.strip() not in primary.payment_notes:
                            primary.payment_notes = f"{primary.payment_notes} | {sec.payment_notes.strip()}"

                    # Fechas
                    if sec.order_date and sec.order_date < primary.order_date:
                        primary.order_date = sec.order_date
                    if sec.deadline:
                        if not primary.deadline or sec.deadline > primary.deadline:
                            primary.deadline = sec.deadline
                    if sec.shipped_date:
                        if not primary.shipped_date or sec.shipped_date > primary.shipped_date:
                            primary.shipped_date = sec.shipped_date
                    if sec.delivered_date:
                        if not primary.delivered_date or sec.delivered_date > primary.delivered_date:
                            primary.delivered_date = sec.delivered_date
                    if sec.paid_date:
                        if not primary.paid_date or sec.paid_date > primary.paid_date:
                            primary.paid_date = sec.paid_date

                    # Eliminar pedido secundario fusionado
                    if not dry_run:
                        sec.delete()

                # Calcular totales y estado consolidado (tanto para simulación como real)
                total_sim_price = sum((i.price or decimal.Decimal('0.00')) for i in all_simulated_items)
                total_sim_qty = sum((i.quantity or 1) for i in all_simulated_items)
                item_statuses = [i.status for i in all_simulated_items]

                if all(s == 'Cobrado' for s in item_statuses):
                    consolidated_status = 'Cobrado'
                elif all(s in ['Cobrado', 'Entregado'] for s in item_statuses):
                    consolidated_status = 'Entregado'
                elif all(s in ['Cobrado', 'Entregado', 'Enviado'] for s in item_statuses):
                    consolidated_status = 'Enviado'
                elif all(s in ['Cobrado', 'Entregado', 'Enviado', 'Realizado'] for s in item_statuses):
                    consolidated_status = 'Realizado'
                elif any(s in ['En proceso', 'Realizado', 'Enviado', 'Entregado', 'Cobrado'] for s in item_statuses):
                    consolidated_status = 'En proceso'
                else:
                    consolidated_status = 'Presupuestado'

                # Recalcular y guardar pedido primario en base de datos
                if not dry_run:
                    primary.update_totals_from_items()
                    primary.status = consolidated_status
                    primary.update_status_dates(primary.status)
                    primary.save()

                disp_price = primary.price if not dry_run else total_sim_price
                disp_status = primary.status if not dry_run else consolidated_status
                self.stdout.write(f"   ✅ Pedido #{primary.id} consolidado: {len(all_simulated_items)} piezas ({total_sim_qty} uds) | Total €{disp_price:.2f} | Estado global: {disp_status}\n")

            if dry_run:
                transaction.set_rollback(True)
                self.stdout.write(self.style.WARNING("\n[SIMULACIÓN FINALIZADA] Ningún cambio fue guardado."))
            else:
                self.stdout.write(self.style.SUCCESS(f"\n[ÉXITO] Se unificaron {unified_clients_count} clientes, agrupando {merged_orders_total} pedidos redundantes."))
                self.stdout.write(self.style.SUCCESS("Todos los pedidos unificados ahora aparecen correctamente con sus piezas individuales en el tablero Kanban y en la tabla de pedidos."))
