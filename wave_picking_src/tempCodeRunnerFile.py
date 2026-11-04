"""
Módulo Principal - Punto de entrada del Sistema de Wave Picking.
Carga automáticamente los escenarios JSON oficiales o permite generar escenarios válidos.
"""
import os
import random
from warehouse import Warehouse
from modelos import Puerta, ZonaDespacho, Rack, Pasillo, Picker, Producto, Pedido
from persistencia import PersistenciaJSON
from simulacion import AppVisual


def generar_escenario_valido(num_racks=3, largo_rack=6, cant_productos=20,
                             cant_pedidos=8, max_prod_por_pedido=4, cap_wave_pedidos=3):
    """Genera un Warehouse aleatorio cumpliendo todas las reglas geométricas del PDF."""
    num_racks = max(2, int(num_racks))
    largo_rack = max(4, int(largo_rack))

    ancho_x = num_racks * 5 + 3
    largo_y = largo_rack + 10

    wh = Warehouse(ancho_x=ancho_x, largo_y=largo_y)
    wh.wave_max_pedidos = max(1, int(cap_wave_pedidos))
    wh.wave_max_productos = wh.wave_max_pedidos * max_prod_por_pedido * 3

    wh.puertas.append(Puerta("PUERTA_OUT_1", "OUTBOUND", 4, 0))
    wh.zonas_despacho.append(ZonaDespacho("ZONA_A", "PUERTA_OUT_1", 2, 1, 5, 2, 600.0))

    y_racks_ini = 5
    y_racks_fin = y_racks_ini + largo_rack
    wh.pasillos.append(Pasillo("PAS_H_INF", 0, 3, ancho_x, 2, "AMBOS"))
    wh.pasillos.append(Pasillo("PAS_H_SUP", 0, y_racks_fin, ancho_x, largo_y - y_racks_fin, "AMBOS"))

    for i in range(num_racks + 1):
        px = i * 5
        sentido_v = "N" if i % 2 == 0 else "S"
        wh.pasillos.append(Pasillo(f"PAS_V{i}", px, y_racks_ini, 3, largo_rack, sentido_v))
        if i < num_racks:
            rx = px + 3
            wh.racks.append(Rack(f"R{i+1}", rx, y_racks_ini, 2, largo_rack))

    wh.pickers.append(Picker("PK_01", 1, 3, 150.0))
    wh.pickers.append(Picker("PK_02", ancho_x - 2, 3, 120.0))

    nombres_base = ["Monitor 27", "Teclado Mecánico", "Mouse Gamer", "Notebook 15", "Auriculares", "SSD 1TB"]
    posiciones_usadas = set()

    for i in range(1, cant_productos + 1):
        rack = random.choice(wh.racks)
        for _ in range(50):
            px = random.randint(rack.x, rack.x + rack.ancho - 1)
            py = random.randint(rack.y, rack.y + rack.alto - 1)
            pz = random.randint(1, 3)
            if (px, py, pz) not in posiciones_usadas:
                posiciones_usadas.add((px, py, pz))
                break

        prod = Producto(
            id_prod=f"P{i:03d}",
            nombre=random.choice(nombres_base),
            x=px, y=py, z=pz,
            stock=random.randint(5, 25),
            peso=round(random.uniform(0.5, 12.0), 2),
            rack_id=rack.id_rack
        )
        wh.registrar_producto(prod)

    lista_prods = wh.productos.valores()
    for i in range(1, cant_pedidos + 1):
        ped = Pedido(f"PED_{i:02d}", prioridad=random.randint(1, 5), estado="PENDIENTE")
        k = random.randint(1, min(max_prod_por_pedido, len(lista_prods)))
        for pr in random.sample(lista_prods, k):
            ped.agregar_producto(pr.id_prod, random.randint(1, 4))
        wh.registrar_pedido(ped)

    wh.construir_estructura()
    return wh


if __name__ == "__main__":
    rutas_posibles = [
        "escenario_basico.json",
        os.path.join("data", "escenario_basico.json"),
        os.path.join("..", "escenario_basico.json"),
        os.path.join("..", "data", "escenario_basico.json")
    ]

    wh_inicial = None
    for ruta in rutas_posibles:
        if os.path.exists(ruta):
            print(f"Cargando escenario desde: {ruta}")
            wh_inicial = PersistenciaJSON.cargar_escenario(ruta)
            break

    if wh_inicial is None:
        wh_inicial = generar_escenario_valido()

    app = AppVisual(wh_inicial, funcion_generador=generar_escenario_valido)
    app.mainloop()