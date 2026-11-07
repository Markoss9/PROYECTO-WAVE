"""
Módulo Generador Automático de Escenarios de Warehouse
Construye y configura automáticamente escenarios válidos de almacén (racks, pasillos,
puertas, zonas de despacho, pickers, inventario de productos y pedidos) garantizando
todas las restricciones geométricas, estructurales y de sentido de circulación.
"""
import math
import random
from warehouse import Warehouse
from modelos import (
    Puerta, ZonaDespacho, Rack, Pasillo,
    Picker, Producto, Pedido
)


class GeneradorWarehouse:
    """
    Generador automático y configurable de escenarios de Warehouse que garantiza por construcción
    y verificación formal todas las restricciones geométricas, de inventario y de circulación.
    """

    CATALOGO_NOMBRES = [
        "Monitor 27", "Teclado Mecánico", "Mouse Inalámbrico", "Notebook 14",
        "Auriculares Pro", "Impresora Láser", "Cable HDMI", "Webcam HD",
        "Disco SSD 1TB", "Memoria RAM 16G", "Router WiFi 6", "Switch Gigabit",
        "Fuente 750W", "Placa de Video", "Microprocesador", "Gabinete ATX",
        "Tablet 10 Pulg", "Cargador USB-C", "Soporte VESA", "Cooler CPU",
        "UPS Interactiva", "Scanner Código", "Zebra Handheld", "Proyector LED",
        "Silla Ergonómica", "Docking Station", "Servidor NAS", "Patchcord Cat6",
        "Cámara IP Domo", "Hub USB 3.0"
    ]

    MODOS_LOCALIZACION = [
        "Equitativa por Estante y Zona (Balanceada)",
        "Aleatoria Uniforme en todos los Estantes",
        "Concentrada en Estantes Cercanos al Despacho",
        "Concentrada en Estantes del Fondo",
        "Concentrada en Mitad Izquierda (Zona 1)",
        "Concentrada en Mitad Derecha (Zona 2)",
        "Personalizada (Asignación Manual por Producto)"
    ]

    @classmethod
    def calcular_geometria_layout(
        cls,
        cant_estantes=4,
        largo_estante=6,
        orientacion="VERTICAL",
        cant_pasillos=6,
        sentido_pasillos="ALTERNADO",
        cant_puertas=2,
        peso_max_zona_kg=500.0
    ):
        """
        Construye las listas de Puertas, Zonas de Despacho, Racks y Pasillos garantizando:
        - Cero solapamiento entre todos los elementos.
        - Todos los elementos dentro de (ancho_x, largo_y).
        - Todos los racks con un lado de valor 2.
        - Puertas sobre el borde inferior (y=0) con su Zona de Despacho justo enfrente (y=1..2).
        - Calles de estiba con flechas de circulación (↑/↓ en estantes verticales, →/← en estantes horizontales)
          flanqueando absolutamente todos los racks sin excepción.
        - Conectividad fuerte respetando el sentido de circulación de los pasillos.
        """
        cant_estantes = max(1, int(cant_estantes))
        largo_estante = max(2, int(largo_estante))
        cant_puertas = max(1, int(cant_puertas))
        es_vertical = not str(orientacion).upper().startswith("H")
        usar_mano_unica = not str(sentido_pasillos).upper().startswith("DOBLE")

        racks = []
        calles_con_flechas = []
        avenidas_conexion = []

        if es_vertical:
            # Estantes verticales: ancho = 2, alto = largo_estante
            # Hasta 10 estantes se disponen en una sola hilera continua como en el diseño clásico de 4 racks
            n_pisos = 1 if cant_estantes <= 10 else 2
            cols_max = math.ceil(cant_estantes / n_pisos)
            ancho_pas_v = 2 if cols_max >= 3 else 3

            ancho_base = cols_max * 2 + (cols_max + 1) * ancho_pas_v
            ancho_min_puertas = cant_puertas * 6 + 2
            while ancho_base < max(14, ancho_min_puertas):
                ancho_pas_v += 1
                ancho_base = cols_max * 2 + (cols_max + 1) * ancho_pas_v

            ancho_x = ancho_base
            alto_h_inf = 2
            alto_h_med = 2
            alto_h_sup = 3
            largo_y = 3 + alto_h_inf + n_pisos * largo_estante + (n_pisos - 1) * alto_h_med + alto_h_sup

            # Avenida horizontal inferior (frente a las zonas de despacho): y = 3..4
            avenidas_conexion.append((0, 3, ancho_x, alto_h_inf, "AMBOS", "H"))

            rack_idx = 1
            for piso in range(n_pisos):
                y_piso = 3 + alto_h_inf + piso * (largo_estante + alto_h_med)
                restantes = cant_estantes - len(racks)
                cols_este_piso = min(cols_max, restantes) if piso < n_pisos - 1 else restantes

                # Si este piso tiene menos racks que cols_max, distribuir el ancho de calle uniformemente
                ancho_total_calles = ancho_x - (cols_este_piso * 2)
                num_calles_piso = cols_este_piso + 1
                ancho_calle_base = ancho_total_calles // num_calles_piso
                sobrante_calle = ancho_total_calles % num_calles_piso

                x_cursor = 0
                for c in range(cols_este_piso):
                    w_calle = ancho_calle_base + (1 if c < sobrante_calle else 0)
                    sent_v = ("N" if c % 2 == 0 else "S") if usar_mano_unica else "AMBOS"
                    calles_con_flechas.append((x_cursor, y_piso, w_calle, largo_estante, sent_v, "V"))
                    x_cursor += w_calle

                    racks.append(Rack(f"R{rack_idx}", x_cursor, y_piso, 2, largo_estante))
                    rack_idx += 1
                    x_cursor += 2

                # Última calle vertical a la derecha del último rack de este piso
                sent_ult = ("N" if cols_este_piso % 2 == 0 else "S") if usar_mano_unica else "AMBOS"
                if cols_este_piso == 1 and usar_mano_unica:
                    sent_ult = "S"  # Garantizar siempre al menos una calle N y una S
                ancho_restante = ancho_x - x_cursor
                calles_con_flechas.append((x_cursor, y_piso, ancho_restante, largo_estante, sent_ult, "V"))

                if piso < n_pisos - 1:
                    y_med = y_piso + largo_estante
                    avenidas_conexion.append((0, y_med, ancho_x, alto_h_med, "AMBOS", "H"))

            y_sup = largo_y - alto_h_sup
            avenidas_conexion.append((0, y_sup, ancho_x, alto_h_sup, "AMBOS", "H"))
            