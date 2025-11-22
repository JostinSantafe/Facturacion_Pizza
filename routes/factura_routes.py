from flask import Blueprint, request, jsonify, send_file
from datetime import datetime
import os
from services.xml_generator import generar_xml_base
from services.file_manager import save_xml
from services.pdf_generator import generar_pdf_desde_xml
from models.factura import guardar_factura, obtener_proximo_folio, guardar_documento_factura
from config.settings import PENDIENTES_BASE, STATIC_PDFS
from services.logger import db_logger
import time


def log_event(uuid: str | None, phase: str, message: str, data: dict | None = None, level: str = "INFO"):
    """Log estructurado facturación -> colección Mongo `logs_facturacion`."""
    safe_data = None
    if data:
        safe_data = {}
        for k, v in data.items():
            if isinstance(v, list) and len(v) > 30:
                safe_data[k] = f"LIST({len(v)})"
            else:
                safe_data[k] = v
    payload = {
        "uuid": uuid,
        "phase": phase,
        "msg": message,
        "data": safe_data,
        "ts_epoch": time.time(),
    }
    db_logger.log_facturacion_structured(level, payload)

factura_bp = Blueprint("factura", __name__)

# Importar logger
db_logger = None
try:
    from services.logger import DatabaseLogger
    db_logger = DatabaseLogger(use_postgres=True)
except Exception as e:
    print(f"[-] Error al importar logger: {e}")


@factura_bp.route("/generar-xml", methods=["POST"])
def generar_xml():
    """
    Genera el XML y la factura en BD cuando el cliente llena sus datos.
    No genera PDF aún.
    """
    try:
        data = request.json or {}
        cliente = data.get("cliente", {})
        carrito = data.get("carrito", [])
        log_event(None, "INICIO_SOLICITUD", "Recepción datos para generar factura", {"carrito_items": len(carrito)})

        if not carrito:
            log_event(None, "VALIDACION", "Carrito vacío, no se genera factura", {}, level="WARNING")
            return jsonify({"status": "error", "message": "Carrito vacío"}), 400

        if not cliente.get("nombre") or not cliente.get("nit"):
            log_event(None, "VALIDACION", "Datos cliente incompletos", {"cliente": cliente}, level="WARNING")
            return jsonify({"status": "error", "message": "Datos de cliente incompletos"}), 400
        
        # Obtener próximo folio secuencial
        folio = obtener_proximo_folio()
        factura_id = f"FAC-{folio}"
        log_event(factura_id, "FOLIO_ASIGNADO", "Folio calculado", {"folio": folio})

        # Generar y guardar XML en pendientes/base
        try:
            xml_base = generar_xml_base(factura_id, cliente, carrito)
            xml_file = save_xml(xml_base, f"{factura_id}.xml", folder="base")
            log_event(factura_id, "XML_GENERADO", "XML generado y almacenado", {"xml_file": xml_file, "xml_len": len(xml_base)})
        except Exception as e_xml:
            log_event(factura_id, "ERROR", f"Fallo generando XML: {e_xml}", level="ERROR")
            return jsonify({"status": "error", "message": "Error generando XML"}), 500

        # Generar y guardar PDF inmediatamente en static/pdfs
        pdf_path = os.path.join(STATIC_PDFS, f"{factura_id}.pdf")
        try:
            generar_pdf_desde_xml(xml_base, pdf_path)
            log_event(factura_id, "PDF_GENERADO", "PDF generado exitosamente", {"pdf_path": pdf_path})
        except PermissionError:
            alt_path = os.path.join(STATIC_PDFS, f"{factura_id}_copy.pdf")
            generar_pdf_desde_xml(xml_base, alt_path)
            pdf_path = alt_path
            log_event(factura_id, "PDF_GENERADO", "PDF bloqueado, generado copia", {"pdf_path": pdf_path}, level="WARNING")
        except Exception as e_pdf:
            log_event(factura_id, "ERROR", f"Fallo generando PDF: {e_pdf}", level="ERROR")

        # Calcular totales
        subtotal = sum(item["precio"] * item["cantidad"] for item in carrito)
        impuesto = int(subtotal * 0.19)
        total = subtotal + impuesto
        
        # Guardar factura en BD (cabecera, receptor, detalle, impuestos)
        factura_db_id = guardar_factura(
            folio=folio,
            cliente_nombre=cliente.get("nombre", ""),
            cliente_nit=cliente.get("nit", ""),
            cliente_email=cliente.get("email", ""),
            subtotal=subtotal,
            impuesto=impuesto,
            total=total,
            carrito=carrito,
            xml_text=xml_base
        )
        if factura_db_id:
            log_event(factura_id, "FACTURA_DB", "Factura insertada en BD", {"factura_db_id": factura_db_id})
        else:
            log_event(factura_id, "ERROR", "No se insertó factura en BD", level="ERROR")
        
        # Guardar documento (XML y PDF) en BD
        if factura_db_id:
            try:
                guardar_documento_factura(
                    factura_id=factura_db_id,
                    xml_path=xml_file,
                    pdf_path=pdf_path,
                    uuid=factura_id
                )
                log_event(factura_id, "DOCUMENTO_DB", "Documento almacenado (XML/PDF)")
            except Exception as e_doc:
                log_event(factura_id, "ERROR", f"Fallo guardando documento: {e_doc}", level="ERROR")

        if db_logger:
            db_logger.info(f"XML generado para factura {factura_id} (folio {folio}).", module="factura_routes")
        
        log_event(factura_id, "FINALIZADO", "Proceso completado", {"total": total})
        return jsonify({
            "status": "success",
            "factura_id": factura_id,
            "folio": folio,
            "subtotal": subtotal,
            "impuesto": impuesto,
            "total": total
        })
    except Exception as e:
        log_event(None, "ERROR", f"Excepción en generar_xml: {e}", level="ERROR")
        return jsonify({"status": "error", "message": "Error interno"}), 500

@factura_bp.route("/pagar", methods=["POST"])
def pagar():
    """
    Endpoint heredado - ahora solo llama a generar_xml
    """
    return generar_xml()


@factura_bp.route("/api/carrito/cancelar", methods=["POST"])
def cancelar_carrito():
    """Loguea la cancelación de un proceso de facturación antes de generar la factura."""
    data = request.json or {}
    factura_uuid = data.get("factura_uuid")  # opcional si ya se asignó
    motivo = data.get("motivo", "usuario_cancela")
    log_event(factura_uuid, "CANCELACION", "Carrito cancelado por usuario", {"motivo": motivo}, level="INFO")
    return jsonify({"status": "success", "message": "Cancelación registrada"})


@factura_bp.route("/descargar-pdf/<factura_id>", methods=["GET"])
def descargar_pdf(factura_id):
    """Descarga el PDF de una factura desde archivos o BD"""
    try:
        import base64
        import io
        from database.connection import get_connection
        from config.settings import PENDIENTES_BASE
        from models.factura import guardar_documento_factura
        
        # Primero buscar en archivos
        pdf_path = os.path.join(STATIC_PDFS, f"{factura_id}.pdf")
        txt_path = os.path.join(PENDIENTES_BASE, f"{factura_id}.txt")
        
        if os.path.exists(pdf_path):
            return send_file(
                pdf_path,
                mimetype='application/pdf',
                as_attachment=True,
                download_name=f"{factura_id}.pdf"
            )
        
        # Si no está en archivos, buscar/generar en BD
        try:
            conn = get_connection()
            cur = conn.cursor()
            
            cur.execute("""
                SELECT xml, pdf, base64doc FROM FacturaDocumento 
                WHERE uuid = %s
                LIMIT 1
            """, (factura_id,))
            
            resultado = cur.fetchone()
            cur.close()
            conn.close()
            
            if resultado:
                xml_text, pdf_bytes, pdf_b64text = resultado
                if pdf_bytes:
                    return send_file(
                        io.BytesIO(pdf_bytes),
                        mimetype='application/pdf',
                        as_attachment=True,
                        download_name=f"{factura_id}.pdf"
                    )
                if pdf_b64text:
                    try:
                        pdf_bytes_dec = base64.b64decode(pdf_b64text)
                        return send_file(
                            io.BytesIO(pdf_bytes_dec),
                            mimetype='application/pdf',
                            as_attachment=True,
                            download_name=f"{factura_id}.pdf"
                        )
                    except Exception:
                        pass
                # Generar PDF desde XML si existe
                if xml_text:
                    generado_path, generado_b64 = generar_pdf_desde_xml(xml_text, pdf_path)
                    # Guardar en BD
                    guardar_documento_factura(
                        factura_id=None,
                        xml_path=None,
                        pdf_path=generado_path,
                        uuid=factura_id
                    )
                    return send_file(
                        generado_path,
                        mimetype='application/pdf',
                        as_attachment=True,
                        download_name=f"{factura_id}.pdf"
                    )
        except Exception as e:
            print(f"[-] Error al obtener PDF de BD: {e}")
        
        # Intentar generar desde XML en disco
        xml_disk = os.path.join(PENDIENTES_BASE, f"{factura_id}.xml")
        if os.path.exists(xml_disk):
            try:
                with open(xml_disk, "r", encoding="utf-8") as f:
                    xml_text = f.read()
                generado_path, _ = generar_pdf_desde_xml(xml_text, pdf_path)
                return send_file(
                    generado_path,
                    mimetype='application/pdf',
                    as_attachment=True,
                    download_name=f"{factura_id}.pdf"
                )
            except Exception as e:
                print(f"[-] Error al generar PDF desde XML en disco: {e}")

        # Fallback a TXT como último recurso
        if os.path.exists(txt_path):
            return send_file(
                txt_path,
                mimetype='text/plain',
                as_attachment=True,
                download_name=f"{factura_id}.txt"
            )
        
        return jsonify({"status": "error", "message": "Archivo no encontrado"}), 404
            
    except Exception as e:
        if db_logger:
            db_logger.error(f"Error al descargar PDF {factura_id}: {e}", module="factura_routes", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500


@factura_bp.route("/api/facturas", methods=["GET"])
def listar_facturas():
    """Lista todas las facturas generadas"""
    try:
        facturas = []
        for archivo in os.listdir(PENDIENTES_BASE):
            if archivo.startswith("FAC-"):
                facturas.append({
                    "nombre": archivo,
                    "ruta": os.path.join(PENDIENTES_BASE, archivo)
                })
        
        return jsonify({"status": "success", "facturas": facturas})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@factura_bp.route("/api/debug/documentos", methods=["GET"])
def debug_documentos():
    """Devuelve conteos y últimos documentos para diagnóstico."""
    try:
        from database.connection import get_connection
        conn = get_connection()
        if not conn:
            return jsonify({"status": "error", "message": "Sin conexión BD"}), 500
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM Factura")
        c_fact = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM facturadocumento")
        c_docs = cur.fetchone()[0]
        cur.execute("SELECT id, uuid, idFactura, length(base64doc) AS len_b64, CASE WHEN pdf IS NULL THEN 0 ELSE 1 END AS tiene_pdf FROM facturadocumento ORDER BY id DESC LIMIT 10")
        rows = cur.fetchall()
        cur.close(); conn.close()
        return jsonify({
            "status": "success",
            "facturas": c_fact,
            "documentos": c_docs,
            "ultimos": [
                {"id": r[0], "uuid": r[1], "idFactura": r[2], "lenBase64": r[3], "pdfGuardado": bool(r[4])} for r in rows
            ]
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@factura_bp.route("/api/logs/mongo", methods=["GET"])
def listar_logs_mongo():
    """Lista últimos logs almacenados en MongoDB."""
    try:
        limit = int(request.args.get("limit", 50))
        level = request.args.get("level")
        module = request.args.get("module")
        logs = db_logger.get_mongo_logs(limit=limit, level=level, module=module, category="facturacion")
        return jsonify({"status": "success", "count": len(logs), "logs": logs})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@factura_bp.route("/api/logs/sistema", methods=["GET"])
def listar_logs_sistema():
    """Lista logs de la colección de sistema."""
    try:
        limit = int(request.args.get("limit", 50))
        level = request.args.get("level")
        module = request.args.get("module")
        logs = db_logger.get_mongo_logs(limit=limit, level=level, module=module, category="sistema")
        return jsonify({"status": "success", "count": len(logs), "logs": logs})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

