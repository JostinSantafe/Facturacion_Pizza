from flask import Flask, render_template, jsonify, request, send_from_directory
import os

# Obtener la ruta base del proyecto
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, 'static')

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path='/static')

@app.route("/")
def index():
    """Página principal con lista de productos"""
    productos = [
        {"nombre": "Pizza Hawaiana", "precio": 35000, "img": "PizzaHawaiana.png"},
        {"nombre": "Pizza Mexicana", "precio": 40000, "img": "PizzaMexicana.png"},
        {"nombre": "Pizza Napolitana", "precio": 32000, "img": "PizzaNapolitana.png"},
        {"nombre": "Pizza Pepperoni", "precio": 36000, "img": "PizzaPepperoni.png"},
        {"nombre": "Pizza Cuatro Quesos", "precio": 42000, "img": "PizzaCuatroQuesos.png"},
        {"nombre": "Gaseosa 1.5L", "precio": 8000, "img": "Gaseosa.png"},
    ]
    return render_template("index.html", productos=productos)

@app.route("/api/health", methods=["GET"])
def health():
    """Endpoint de salud"""
    return jsonify({"status": "ok", "message": "App funcionando"})

# Importar rutas después de definir app
try:
    from routes.factura_routes import factura_bp
    app.register_blueprint(factura_bp)
except Exception as e:
    print(f"[-] Error al importar rutas: {e}")

if __name__ == "__main__":
    print("\n" + "="*60)
    print("[+] Iniciando Facturacion_Pizza")
    print("[+] URL: http://127.0.0.1:5000")
    print("[+] Presiona CTRL+C para detener")
    print("="*60 + "\n")
    
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False, threaded=True)




