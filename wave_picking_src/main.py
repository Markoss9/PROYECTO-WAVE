"""
Módulo Principal - Punto de entrada del Sistema de Wave Picking.
Carga automáticamente el escenario JSON inicial o genera uno válido automáticamente
e inicia el simulador visual.
"""
import os
from persistencia import PersistenciaJSON
from generador import GeneradorWarehouse
from simulacion import AppVisual


def generar_escenario_valido(
    cant_estantes=4,
    cant_pasillos=6,
    cant_productos=12,
    modo_localizacion="Equitativa por Estante y Zona (Balanceada)",
    cant_pedidos=6,
    max_productos_por_pedido=4,
    wave_max_pedidos=3,
    wave_max_productos=15,
    **kwargs
):
    """
    Genera automáticamente un Warehouse válido respetando todos los parámetros configurados
    y las restricciones estructurales y de circulación del sistema.
    """
    return GeneradorWarehouse.generar(
        cant_estantes=cant_estantes,
        cant_pasillos=cant_pasillos,
        cant_productos=cant_productos,
        modo_localizacion=modo_localizacion,
        cant_pedidos=cant_pedidos,
        max_productos_por_pedido=max_productos_por_pedido,
        wave_max_pedidos=wave_max_pedidos,
        wave_max_productos=wave_max_productos,
        **kwargs
    )


def cargar_escenario_inicial():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    rutas_posibles = [
        os.path.join(base_dir, "..", "data", "escenario_basico.json"),
        os.path.join(base_dir, "data", "escenario_basico.json"),
        "escenario_basico.json",
        os.path.join("data", "escenario_basico.json"),
        os.path.join("..", "data", "escenario_basico.json")
    ]

    for ruta in rutas_posibles:
        if os.path.exists(ruta):
            print(f"Cargando escenario desde: {ruta}")
            return PersistenciaJSON.cargar_escenario(ruta)

    return generar_escenario_valido()


if __name__ == "__main__":
    wh_inicial = cargar_escenario_inicial()
    app = AppVisual(wh_inicial)
    app.mainloop()