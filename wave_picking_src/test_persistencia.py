import os
from persistencia import PersistenciaJSON

def buscar_y_probar(nombre_json):
    # Busca el archivo en la carpeta actual, en ../ o en ../data/
    rutas_posibles = [
        nombre_json,
        os.path.join("data", nombre_json),
        os.path.join("..", nombre_json),
        os.path.join("..", "data", nombre_json)
    ]
    for ruta in rutas_posibles:
        if os.path.exists(ruta):
            print(f"\n--- Probando lectura de: {ruta} ---")
            wh = PersistenciaJSON.cargar_escenario(ruta)
            print(f"Dimensiones: {wh.ancho_x} x {wh.largo_y}")
            print(f"Racks: {len(wh.racks)} | Pasillos: {len(wh.pasillos)} | Pickers: {len(wh.pickers)}")
            print(f"Productos: {len(wh.productos)} | Pedidos: {len(wh.pedidos)}")
            print(f"Nodos transitables en el grafo: {len(wh.grafo.nodos)}")
            print("Resultado: LECTURA EXITOSA")
            return
    print(f"\nNo se encontró el archivo {nombre_json} en ninguna ruta cercana.")

if __name__ == "__main__":
    buscar_y_probar("escenario_basico.json")
    buscar_y_probar("escenario_grande.json")
    