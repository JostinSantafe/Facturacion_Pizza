import os
import base64
from typing import Optional, List, Dict
import xml.etree.ElementTree as ET
from datetime import datetime
from database.connection import get_connection

FOLIO_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "folio.txt")


def obtener_proximo_folio() -> int:
    """Devuelve un folio único basado en el mayor entre BD y `folio.txt` + 1.

    No modifica el esquema de la BD. Actualiza `folio.txt` para mantener consistencia.
    """
    file_val = 0
    try:
        if os.path.exists(FOLIO_FILE):
            with open(FOLIO_FILE, "r", encoding="utf-8") as f:
                contenido = (f.read() or "0").strip()
                file_val = int(contenido or 0)
    except Exception:
        file_val = 0

    db_val = 0
    try:
        conn = get_connection()
        if conn:
            cur = conn.cursor()
            cur.execute("SELECT COALESCE(MAX(folio), 0) FROM Factura;")
            row = cur.fetchone()
            db_val = int(row[0] or 0)
            cur.close()
            conn.close()
    except Exception:
        db_val = 0

    next_val = max(file_val, db_val) + 1
    try:
        with open(FOLIO_FILE, "w", encoding="utf-8") as f:
            f.write(str(next_val))
            f.flush()
    except Exception:
        pass
    return next_val

def _numero_a_letras_simplificado(numero: int) -> str:
    try:
        n = int(numero)
    except Exception:
        n = 0
    return f"CANTIDAD {n} PESOS CON 00 CENTAVOS"


def _get_or_create_receptor(cur, nit: str, nombre: str, email: str) -> int:
    cur.execute("SELECT id FROM Receptor WHERE nit=%s LIMIT 1", (nit,))
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute(
        "INSERT INTO Receptor (nit, tipoDoc, nombre, email) VALUES (%s, %s, %s, %s) RETURNING id",
        (nit or "", "13", nombre or "", email or ""),
    )
    return cur.fetchone()[0]


def _get_or_create_producto(cur, descripcion: str, precio: float, impuesto_defecto: float = 19.0) -> int:
    codigo = (descripcion or "PROD").upper().replace(" ", "_")[:20]
    cur.execute("SELECT id FROM Producto WHERE codigo=%s LIMIT 1", (codigo,))
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute(
        "INSERT INTO Producto (codigo, descripcion, precio, impuestoDefecto) VALUES (%s, %s, %s, %s) RETURNING id",
        (codigo, descripcion or codigo, float(precio), float(impuesto_defecto)),
    )
    return cur.fetchone()[0]


def _get_or_create_impuesto(cur, tipo: str = "IVA", tasa: float = 19.0) -> int:
    cur.execute("SELECT id FROM Impuesto WHERE tipo=%s AND tasa=%s LIMIT 1", (tipo, float(tasa)))
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute(
        "INSERT INTO Impuesto (tipo, tasa) VALUES (%s, %s) RETURNING id",
        (tipo, float(tasa)),
    )
    return cur.fetchone()[0]


def _map_tipo_impuesto(xml_code: str) -> str:
    if (xml_code or "").strip() == "01":
        return "IVA"
    if (xml_code or "").strip() == "02":
        return "RET"
    if (xml_code or "").strip() == "03":
        return "INC"
    return "IMP"


def _parse_impuestos_from_xml(xml_text: Optional[str]) -> List[Dict]:
    """Extrae impuestos desde el XML en forma de lista {tipo, tasa, base, valor}."""
    result: List[Dict] = []
    if not xml_text:
        return result
    try:
        root = ET.fromstring(xml_text)
        for imp in root.findall(".//Impuestos/Imp"):
            tasa = float(imp.findtext("tasa", default="0") or 0)
            base = float(imp.findtext("baseimpuestos", default="0") or 0)
            valor = float(imp.findtext("importe", default="0") or 0)
            tipo = _map_tipo_impuesto(imp.findtext("tipoImpuesto", default=""))
            result.append({"tipo": tipo, "tasa": tasa, "base": base, "valor": valor})
        if not result:
            # Fallback: usar encabezado si no hay nodos Imp
            enc = root.find("Encabezado")
            if enc is not None:
                base = float(enc.findtext("baseimpuesto", default="0") or 0)
                valor = float(enc.findtext("totalimpuestos", default="0") or 0)
                if base or valor:
                    result.append({"tipo": "IVA", "tasa": 19.0, "base": base, "valor": valor})
    except Exception:
        pass
    return result


def guardar_factura(*, folio: int, cliente_nombre: str, cliente_nit: str, cliente_email: str, subtotal: int, impuesto: int, total: int, carrito: Optional[List[Dict]] = None, xml_text: Optional[str] = None):
    """Inserta en el esquema existente y retorna el id de Factura.

    No altera tablas; usa tablas: Factura, Receptor, FacturaReceptor, DetalleFactura, Impuesto, FacturaImpuesto.
    """
    conn = get_connection()
    if conn is None:
        print("[guardar_factura] Sin conexión BD")
        return None
    cur = conn.cursor()
    print(f"[guardar_factura] Iniciando folio={folio} subtotal={subtotal} impuesto={impuesto} total={total}")
    try:

        # Receptor
        id_receptor = _get_or_create_receptor(cur, cliente_nit, cliente_nombre, cliente_email)
        print(f"[guardar_factura] id_receptor={id_receptor}")

    # Cabecera factura
        cur.execute(
            """
            INSERT INTO Factura (
                folio, prefijo, tipoComprobante, fecha, hora, fechaVencimiento,
                subtotal, impuesto, total, montoLetra, estado, idEmisor, idResolucion
            ) VALUES (
                %s, 'FAC', '01', CURRENT_DATE, CURRENT_TIME, CURRENT_DATE,
                %s, %s, %s, %s, 'EMITIDA', NULL, NULL
            ) RETURNING id
            """,
            (int(folio), float(subtotal), float(impuesto), float(total), _numero_a_letras_simplificado(total)),
        )
        factura_id = cur.fetchone()[0]
        print(f"[guardar_factura] factura_id={factura_id}")

    # Relación Factura-Receptor
        cur.execute(
            "INSERT INTO FacturaReceptor (idFactura, idReceptor) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (factura_id, id_receptor),
        )

    # Detalle e impuestos (si hay carrito)
        if carrito:
            for item in carrito:
                id_prod = _get_or_create_producto(cur, item.get("nombre"), item.get("precio", 0))
                cantidad = int(item.get("cantidad", 1))
                precio_u = float(item.get("precio", 0))
                subtotal_linea = cantidad * precio_u
                impuesto_linea = round(subtotal_linea * 0.19, 2)
                cur.execute(
                    """
                    INSERT INTO DetalleFactura (idFactura, idProducto, cantidad, precioUnitario, subtotalLinea, impuestoLinea)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (factura_id, id_prod, cantidad, precio_u, subtotal_linea, impuesto_linea),
                )
            print(f"[guardar_factura] Detalles insertados={len(carrito)}")

    # Impuestos desde XML si se proporcionó; si no, usar totales básicos
        impuestos_xml = _parse_impuestos_from_xml(xml_text)
        if impuestos_xml:
            for imp in impuestos_xml:
                imp_id = _get_or_create_impuesto(cur, imp.get("tipo", "IVA"), float(imp.get("tasa", 0)))
                cur.execute(
                    """
                    INSERT INTO FacturaImpuesto (idFactura, idImpuesto, baseGravable, valor)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (idFactura, idImpuesto) DO NOTHING
                    """,
                    (factura_id, imp_id, float(imp.get("base", 0)), float(imp.get("valor", 0))),
                )
            print(f"[guardar_factura] Impuestos XML insertados={len(impuestos_xml)}")
        else:
            imp_id = _get_or_create_impuesto(cur, "IVA", 19.0)
            cur.execute(
                """
                INSERT INTO FacturaImpuesto (idFactura, idImpuesto, baseGravable, valor)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (idFactura, idImpuesto) DO NOTHING
                """,
                (factura_id, imp_id, float(subtotal), float(impuesto)),
            )
            print("[guardar_factura] Impuesto básico insertado")
        conn.commit()
        print("[guardar_factura] Commit OK")
        return factura_id
    except Exception as e:
        print(f"[guardar_factura] ERROR {e}")
        try:
            conn.rollback()
            print("[guardar_factura] Rollback ejecutado")
        except Exception:
            pass
        return None
    finally:
        cur.close()
        conn.close()


def guardar_documento_factura(*, factura_id: Optional[int], xml_path: Optional[str], pdf_path: Optional[str], uuid: str):
    """Guarda/actualiza en FacturaDocumento respetando el tipo real de la columna `pdf`.

    Si existe registro por uuid → update con solo las columnas provistas.
    Si no existe → insert (requiere `factura_id`).
    No se asume tipo; se consulta el tipo de `pdf` (BYTEA o TEXT) y se envía el valor adecuado.
    """
    conn = get_connection()
    if conn is None:
        return None

    xml_text = None
    pdf_bytes = None
    b64_text = None

    print(f"[guardar_documento_factura] Iniciando para uuid={uuid} factura_id={factura_id}")
    print(f"[guardar_documento_factura] Rutas: xml_path={xml_path} pdf_path={pdf_path}")

    try:
        if xml_path and os.path.exists(xml_path):
            with open(xml_path, "r", encoding="utf-8") as f:
                xml_text = f.read()
            print(f"[guardar_documento_factura] XML leído, tamaño={len(xml_text)} bytes")
        else:
            print("[guardar_documento_factura] XML no encontrado o ruta vacía")
    except Exception as e:
        print(f"[guardar_documento_factura] Error leyendo XML: {e}")
        xml_text = None

    try:
        if pdf_path and os.path.exists(pdf_path):
            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()
            b64_text = base64.b64encode(pdf_bytes).decode("ascii")
            print(f"[guardar_documento_factura] PDF leído, tamaño={len(pdf_bytes)} bytes / base64 len={len(b64_text)}")
        else:
            print("[guardar_documento_factura] PDF no encontrado o ruta vacía")
    except Exception as e:
        print(f"[guardar_documento_factura] Error leyendo PDF: {e}")
        pdf_bytes = None
        b64_text = None

    cur = conn.cursor()

    # Detectar tipo real de columna pdf
    cur.execute(
        """
        SELECT data_type
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name='facturadocumento' AND column_name='pdf'
        """
    )
    row_type = cur.fetchone()
    pdf_is_bytea = bool(row_type and row_type[0].lower() == 'bytea')

    # Guardar bytes solo si la columna es BYTEA; si no, dejamos NULL y usamos base64doc
    pdf_value = pdf_bytes if pdf_is_bytea else None

    # Upsert por uuid con SQL dinámico sin COALESCE de tipos distintos
    # Upsert simplificado: si existe actualiza, si no existe inserta SIEMPRE al menos uuid
    try:
        cur.execute("SELECT id FROM FacturaDocumento WHERE uuid=%s LIMIT 1", (uuid,))
        row = cur.fetchone()
        if row:
            sets = []
            params = []
            if xml_text is not None:
                sets.append("xml=%s")
                params.append(xml_text)
            if b64_text is not None:
                sets.append("base64doc=%s")
                params.append(b64_text)
            if pdf_value is not None:
                sets.append("pdf=%s")
                params.append(pdf_value)
            if sets:
                sql = "UPDATE FacturaDocumento SET " + ", ".join(sets) + " WHERE uuid=%s"
                params.append(uuid)
                cur.execute(sql, tuple(params))
                print(f"[guardar_documento_factura] UPDATE ejecutado columnas={sets}")
            else:
                print("[guardar_documento_factura] Nada que actualizar (sin datos nuevos)")
        else:
            # Insert mínimo aunque falten datos
            cols = ["uuid"]
            vals = [uuid]
            placeholders = ["%s"]
            if factura_id is not None:
                cols.insert(0, "idFactura")
                vals.insert(0, factura_id)
                placeholders.insert(0, "%s")
            if xml_text is not None:
                cols.append("xml")
                vals.append(xml_text)
                placeholders.append("%s")
            if b64_text is not None:
                cols.append("base64doc")
                vals.append(b64_text)
                placeholders.append("%s")
            if pdf_value is not None:
                cols.append("pdf")
                vals.append(pdf_value)
                placeholders.append("%s")
            sql = f"INSERT INTO FacturaDocumento ({', '.join(cols)}) VALUES ({', '.join(placeholders)})"
            cur.execute(sql, tuple(vals))
            print(f"[guardar_documento_factura] INSERT ejecutado columnas={cols}")
    except Exception as e:
        print(f"[guardar_documento_factura] ERROR upsert {e}")

    # Verificación post-operación; segundo intento mínimo si no existe
    cur.execute("SELECT id, length(xml), length(base64doc), CASE WHEN pdf IS NULL THEN 0 ELSE 1 END FROM FacturaDocumento WHERE uuid=%s LIMIT 1", (uuid,))
    ver_row = cur.fetchone()
    if not ver_row:
        try:
            cur.execute("INSERT INTO FacturaDocumento (uuid) VALUES (%s) ON CONFLICT DO NOTHING", (uuid,))
            print("[guardar_documento_factura] Segundo intento inserción mínima ejecutado")
        except Exception as e:
            print(f"[guardar_documento_factura] ERROR segundo intento {e}")
    else:
        print(f"[guardar_documento_factura] Verificación OK id={ver_row[0]} xml_len={ver_row[1]} b64_len={ver_row[2]} tiene_pdf={bool(ver_row[3])}")

    conn.commit()
    cur.close()
    conn.close()
    print("[guardar_documento_factura] Commit realizado y conexión cerrada")
    return True

