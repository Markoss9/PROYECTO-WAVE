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
            
            
        else:
            # Estantes horizontales: ancho = largo_estante, alto = 2 (lado de valor 2)
            # Las calles con flechas (→ Este / ← Oeste) corren horizontalmente entre, debajo y encima de los racks
            cols_racks = 1 if cant_estantes <= 3 else 2
            filas_racks = math.ceil(cant_estantes / cols_racks)
            ancho_pas_lat = 2
            ancho_base = cols_racks * largo_estante + (cols_racks + 1) * ancho_pas_lat
            ancho_min_puertas = cant_puertas * 6 + 2
            while ancho_base < max(16, ancho_min_puertas):
                ancho_pas_lat += 1
                ancho_base = cols_racks * largo_estante + (cols_racks + 1) * ancho_pas_lat

            ancho_x = ancho_base
            alto_calle_h = 2
            y_inicio_estiba = 4  # y=3 es el corredor de acceso a Zonas de Despacho
            # Hay (filas_racks + 1) calles horizontales con flechas y (filas_racks) hileras de racks de alto 2
            alto_bloque_estiba = (filas_racks + 1) * alto_calle_h + filas_racks * 2
            largo_y = y_inicio_estiba + alto_bloque_estiba

            # Corredor inferior frente a las zonas de despacho (y = 3)
            avenidas_conexion.append((0, 3, ancho_x, 1, "AMBOS", "H"))

            # Avenidas verticales de conexión (izquierda, central y derecha) en sentido AMBOS
            for c in range(cols_racks + 1):
                if c < cols_racks:
                    x_av = c * (ancho_pas_lat + largo_estante)
                    w_av = ancho_pas_lat
                else:
                    x_av = cols_racks * (ancho_pas_lat + largo_estante)
                    w_av = ancho_x - x_av
                avenidas_conexion.append((x_av, y_inicio_estiba, w_av, alto_bloque_estiba, "AMBOS", "V"))

            # Crear las hileras de Racks Horizontales y las Calles Horizontales con flechas (→ / ←)
            rack_idx = 1
            for fila_calle in range(filas_racks + 1):
                y_calle = y_inicio_estiba + fila_calle * (alto_calle_h + 2)
                sent_h = ("E" if fila_calle % 2 == 0 else "O") if usar_mano_unica else "AMBOS"

                for c in range(cols_racks):
                    x_col = ancho_pas_lat + c * (largo_estante + ancho_pas_lat)
                    calles_con_flechas.append((x_col, y_calle, largo_estante, alto_calle_h, sent_h, "H"))

                    if fila_calle < filas_racks:
                        y_r = y_calle + alto_calle_h
                        if rack_idx <= cant_estantes:
                            racks.append(Rack(f"R{rack_idx}", x_col, y_r, largo_estante, 2))
                            rack_idx += 1
                        else:
                            # Si la cantidad de racks es impar y queda un hueco en la última fila/columna,
                            # ese espacio forma parte de la calle horizontal con el mismo sentido
                            calles_con_flechas.append((x_col, y_r, largo_estante, 2, sent_h, "H"))

        # Puertas sobre el borde inferior (y = 0) y Zonas de Despacho justo enfrente (y = 1..2)
        puertas = []
        zonas_despacho = []
        ancho_seg = ancho_x // cant_puertas
        letras = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        for i in range(cant_puertas):
            x_ini_seg = i * ancho_seg
            x_fin_seg = (i + 1) * ancho_seg if i < cant_puertas - 1 else ancho_x
            w_seg = x_fin_seg - x_ini_seg
            ancho_z = min(5, max(3, w_seg - 2))
            zx = x_ini_seg + max(1, (w_seg - ancho_z) // 2)
            if zx + ancho_z >= ancho_x:
                zx = max(1, ancho_x - ancho_z - 1)
            px = zx + ancho_z // 2

            tipo_p = "OUTBOUND" if i == 0 else ("INBOUND" if i == 1 and cant_puertas == 2 else "AMBOS")
            id_p = f"PUERTA_{i + 1}"
            id_z = f"ZONA_{letras[i % len(letras)]}"
            puertas.append(Puerta(id_p, tipo_p, px, 0))
            zonas_despacho.append(ZonaDespacho(id_z, id_p, zx, 1, ancho_z, 2, float(peso_max_zona_kg)))

        # NUNCA truncar las calles con flechas que flanquean los racks: todas deben dibujarse siempre
        cant_pasillos_obj = max(len(calles_con_flechas), int(cant_pasillos))
        bloques_totales = list(calles_con_flechas) + list(avenidas_conexion)

        if cant_pasillos_obj <= len(bloques_totales):
            seleccionados = bloques_totales[:cant_pasillos_obj]
        else:
            seleccionados = list(bloques_totales)
            # Si se solicitan más pasillos, subdividir únicamente las avenidas de conexión sin tocar las calles con flechas
            intentos = 0
            while len(seleccionados) < cant_pasillos_obj and intentos < 500:
                intentos += 1
                idx_mejor = -1
                max_dim = 1
                for idx_b, (bx, by, bw, bh, bs, bt) in enumerate(seleccionados):
                    # Preferir subdividir avenidas AMBOS antes que calles con flechas
                    prioridad_ambos = 100 if bs == "AMBOS" else 0
                    dim = max(bw, bh)
                    if dim >= 2 and (dim + prioridad_ambos) > max_dim:
                        max_dim = dim + prioridad_ambos
                        idx_mejor = idx_b
                if idx_mejor == -1:
                    break
                bx, by, bw, bh, bs, bt = seleccionados.pop(idx_mejor)
                if bw >= bh and bw >= 2:
                    mitad = bw // 2
                    seleccionados.insert(idx_mejor, (bx + mitad, by, bw - mitad, bh, bs, bt))
                    seleccionados.insert(idx_mejor, (bx, by, mitad, bh, bs, bt))
                elif bh >= 2:
                    mitad = bh // 2
                    seleccionados.insert(idx_mejor, (bx, by + mitad, bw, bh - mitad, bs, bt))
                    seleccionados.insert(idx_mejor, (bx, by, bw, mitad, bs, bt))

        pasillos = []
        for idx_p, (px, py, pw, ph, psent, ptipo) in enumerate(seleccionados, start=1):
            pasillos.append(Pasillo(f"PAS_{ptipo}{idx_p}", px, py, pw, ph, psent))

        return ancho_x, largo_y, puertas, zonas_despacho, racks, pasillos
