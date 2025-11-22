## Logs en MongoDB

Se añadió soporte para almacenar logs en una base de datos NoSQL (MongoDB) además del archivo y PostgreSQL.

### Configuración

Variables (puedes añadirlas a `.env`):

```
MONGO_LOG_MAX_SIZE=52428800   # 50MB tamaño colección capped
MONGO_LOG_TTL=2592000         # 30 días en segundos
```

`config/settings.py` define `MONGO_CONFIG` con:
- `uri`: conexión (por defecto `mongodb://localhost:27017/`)
- `database`: nombre DB (`facturacion_nosql`)
- `collection`: colección de logs (`logs_facturacion`)
- `max_size_bytes`: tamaño máximo colección capped
- `ttl_seconds`: TTL adicional (los documentos expiran según su campo `ts`)

### Retención

Se usa una colección capped para descartar automáticamente los documentos más antiguos al llegar al límite de tamaño, y un índice TTL para eliminar registros más antiguos que el plazo configurado.

### Endpoint de consulta

`GET /api/logs/mongo?limit=100&level=ERROR&module=factura_routes`

Respuesta:
```json
{
	"status": "success",
	"count": 2,
	"logs": [
		{"ts": "2025-11-18T10:00:00Z", "level": "ERROR", "module": "factura_routes", "message": "Error al generar XML", "error": "Traceback..."}
	]
}
```

### Dependencia

Instala pymongo:
```
pip install pymongo==4.6.1
```

### Verificación rápida

1. Inicia MongoDB (Windows servicio o `mongod`).
2. Genera operaciones en la app (crear facturas, forzar errores). 
3. Consulta: `curl http://localhost:5000/api/logs/mongo?limit=10`.

Si Mongo no está disponible, el logger continúa usando archivo y PostgreSQL sin fallar.

## Trazabilidad de Facturación

La ruta `POST /generar-xml` ahora emite eventos de logging estructurados (almacenados en archivo, PostgreSQL y Mongo) con fases para auditar el ciclo completo:

Formato JSON en Mongo (`logs_facturacion`):
```
{
	ts: ISODate,
	level: "INFO" | "ERROR" | ..., 
	module: "factura_flow",
	uuid: "FAC-123",
	phase: "XML_GENERADO",
	msg: "XML generado y almacenado",
	data: { xml_file: ".../FAC-123.xml", xml_len: 1245, folio: 123 },
	ts_epoch: 1731926400.123
}
```

Fases posibles:
- `INICIO_SOLICITUD`: recepción del JSON inicial (carrito y cliente).
- `VALIDACION`: problemas de datos (carrito vacío, cliente incompleto).
- `FOLIO_ASIGNADO`: folio secuencial elegido.
- `XML_GENERADO`: XML creado y guardado (incluye longitud y ruta).
- `PDF_GENERADO`: PDF creado; incluye advertencia si se generó copia por bloqueo.
- `FACTURA_DB`: cabecera/detalles/impuestos insertados en PostgreSQL.
- `DOCUMENTO_DB`: documento (XML/PDF/base64) almacenado.
- `FINALIZADO`: cierre exitoso del proceso con total.
- `CANCELACION`: usuario aborta antes de finalizar (endpoint `/api/carrito/cancelar`).
- `ERROR`: cualquier fallo en generación de XML/PDF o inserciones.

### Endpoint de cancelación

`POST /api/carrito/cancelar`
Body ejemplo:
```json
{ "factura_uuid": "FAC-123", "motivo": "cliente_se_retira" }
```
Registra fase `CANCELACION` para auditoría (se puede llamar antes de que exista la factura).

### Consulta filtrada de logs

Mongo facturación: `GET /api/logs/mongo?limit=100&module=factura_flow&level=ERROR`

Mongo sistema: `GET /api/logs/sistema?limit=50&level=ERROR&module=sistema`

PostgreSQL (manual):
```sql
SELECT fecha, nivel, mensaje FROM logs WHERE modulo='factura_flow' ORDER BY fecha DESC LIMIT 100;
```

### Buenas prácticas
- Mantener tamaño de carrito moderado para no sobrecargar logs.
- Consumir periódicamente `/api/logs/mongo` y, si se requiere exportar, antes de que la colección capped rote.
- Ajustar `MONGO_LOG_MAX_SIZE` y `MONGO_LOG_TTL` según volumen real.

## Colecciones Mongo

- `logs_facturacion`: eventos detallados del flujo de emisión de factura (trazabilidad).
- `logs_sistema`: eventos generales de sistema (errores globales, inicialización, estado).

Ambas son colecciones capped con TTL. Índices añadidos: `ts`, `level+module`, `uuid`.



# Facturacion_Pizza

Aplicación Flask para generar facturas simples con XML y tirilla PDF, guardando también en PostgreSQL.

## Requisitos
- Python 3.8+
- PostgreSQL en `localhost:5432` (configurable via `.env`)

## Puesta en marcha (Windows)
```bat
cd C:\Facturacion_Pizza
iniciar.bat
```
El script creará `.venv`, instalará dependencias, verificará el entorno y ejecutará el servidor.

## Variables de entorno
Crea un archivo `.env` en la raíz del proyecto (opcional). Ejemplo:
```env
DB_NAME=facturacion_electronica
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=localhost
DB_PORT=5432
```

## Flujo de uso
1. Selecciona productos.
2. Proceder al pago → completa datos del cliente.
3. Se genera XML y registro en BD.
4. Descarga PDF desde el botón (si no existe, se genera al vuelo desde el XML).

## Estructura
- `app.py` y `start.py`: arranque de Flask.
- `routes/`: rutas (e.g., `factura_routes.py`).
- `services/`: utilidades (XML, PDF, logger, archivos).
- `models/`: acceso a BD (creación de tablas, guardado de factura/documento, logs).
- `database/`: conexión a PostgreSQL.
- `config/settings.py`: configuración y carpetas.
- `static/`: estilos, imágenes y PDFs generados.
- `pendientes/`: XMLs generados (`base/`) y carpeta `xmldian/` (reserva).

## Comandos útiles
- Ejecutar verificación:
```bat
cd C:\Facturacion_Pizza
.venv\Scripts\python.exe verificar.py
```
- Ejecutar app sin navegador automático:
```bat
cd C:\Facturacion_Pizza
run.bat
```

## Notas
- El folio se gestiona con `folio.txt` en la raíz del proyecto.
- Las tablas `Factura` y `FacturaDocumento` se crean automáticamente si no existen.
- El PDF se guarda en `static/pdfs/` y en BD (Base64).