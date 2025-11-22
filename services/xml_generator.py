import xml.etree.ElementTree as ET
from datetime import datetime

def generar_xml_base(factura_id, cliente, carrito):
    """
    Genera un XML de factura con la estructura correcta.
    Basado en el formato de facturación electrónica colombiano.
    """
    factura = ET.Element("Factura")
    
    # Encabezado
    encabezado = ET.SubElement(factura, "Encabezado")
    
    # Información básica
    ET.SubElement(encabezado, "llavecomprobante").text = factura_id
    ET.SubElement(encabezado, "nitemisor").text = "22222222"
    ET.SubElement(encabezado, "codSucursal").text = "Pizzeria 1"
    ET.SubElement(encabezado, "noresolucion").text = "123456789"
    ET.SubElement(encabezado, "prefijo").text = "PZZA"
    
    # Extraer folio del factura_id (ej: "FAC-41" -> "41")
    folio = factura_id.split("-")[-1] if "-" in factura_id else "0"
    ET.SubElement(encabezado, "folio").text = folio
    
    # Información del receptor
    ET.SubElement(encabezado, "obligacionesfiscalesreceptor").text = "R-99-PN"
    ET.SubElement(encabezado, "paisreceptor").text = "CO"
    ET.SubElement(encabezado, "moneda").text = "COP"
    ET.SubElement(encabezado, "metodopago").text = "1"
    ET.SubElement(encabezado, "mediopago").text = "10"
    ET.SubElement(encabezado, "terminospago").text = "0"
    ET.SubElement(encabezado, "tipoOpera").text = "10"
    ET.SubElement(encabezado, "xslt").text = "1"
    ET.SubElement(encabezado, "tipocomprobante").text = "01"
    ET.SubElement(encabezado, "totaldescuentos").text = "0.00"
    ET.SubElement(encabezado, "totalcargos").text = "0.00"
    ET.SubElement(encabezado, "totalimpuestosretenidos").text = "0.00"
    
    # Fecha y hora
    ahora = datetime.now()
    ET.SubElement(encabezado, "fecha").text = ahora.strftime("%Y-%m-%d")
    ET.SubElement(encabezado, "hora").text = ahora.strftime("%H:%M:%S")
    ET.SubElement(encabezado, "fechavencimiento").text = ahora.strftime("%Y-%m-%d")
    
    # Información del receptor
    ET.SubElement(encabezado, "tiporeceptor").text = "1"
    ET.SubElement(encabezado, "nitreceptor").text = "52169473"
    ET.SubElement(encabezado, "tipoDocRec").text = "13"
    ET.SubElement(encabezado, "digitoverificacion").text = ""
    ET.SubElement(encabezado, "nombrereceptor").text = cliente.get("nombre", "Cliente")
    ET.SubElement(encabezado, "mailreceptor").text = cliente.get("email", "")
    ET.SubElement(encabezado, "apellidosreceptor").text = ""
    
    # Calcular totales
    subtotal = 0
    total_impuestos = 0
    items_count = 0
    
    for item in carrito:
        importe = item["cantidad"] * item["precio"]
        impuesto = round(importe * 0.19, 2)
        subtotal += importe
        total_impuestos += impuesto
    
    total = subtotal + total_impuestos
    
    # Totales en encabezado
    ET.SubElement(encabezado, "subtotal").text = f"{subtotal:.2f}"
    ET.SubElement(encabezado, "baseimpuesto").text = f"{subtotal:.2f}"
    ET.SubElement(encabezado, "totalsindescuento").text = f"{subtotal:.2f}"
    ET.SubElement(encabezado, "totalimpuestos").text = f"{total_impuestos:.2f}"
    ET.SubElement(encabezado, "total").text = f"{total:.2f}"
    
    # Convertir total a letras (aproximado)
    ET.SubElement(encabezado, "montoletra").text = numero_a_letras(int(total))
    
    # Detalle de items
    detalle = ET.SubElement(factura, "Detalle")
    id_concepto = 1
    
    for item in carrito:
        det = ET.SubElement(detalle, "Det")
        ET.SubElement(det, "idConcepto").text = str(id_concepto)
        ET.SubElement(det, "llaveComprobante").text = factura_id
        ET.SubElement(det, "unidadmedida").text = "EA"
        ET.SubElement(det, "tasa").text = "19.00"
        ET.SubElement(det, "tipo").text = "01"
        
        # Código de producto (simplificado)
        codigo_producto = f"PZ{id_concepto:02d}"
        ET.SubElement(det, "identificacionproductos").text = codigo_producto
        
        importe = item["cantidad"] * item["precio"]
        impuesto = round(importe * 0.19, 2)
        
        ET.SubElement(det, "impuestolinea").text = f"{impuesto:.2f}"
        ET.SubElement(det, "baseimpuestos").text = f"{importe:.2f}"
        ET.SubElement(det, "descripcion").text = item["nombre"]
        ET.SubElement(det, "cantidad").text = str(item["cantidad"])
        ET.SubElement(det, "precioUnitario").text = f"{item['precio']:.2f}"
        ET.SubElement(det, "importe").text = f"{importe:.2f}"
        
        id_concepto += 1
    
    # Impuestos
    impuestos = ET.SubElement(factura, "Impuestos")
    imp = ET.SubElement(impuestos, "Imp")
    ET.SubElement(imp, "idImpuesto").text = "1"
    ET.SubElement(imp, "llaveComprobante").text = factura_id
    ET.SubElement(imp, "tasa").text = "19.00"
    ET.SubElement(imp, "tipoImpuesto").text = "01"
    ET.SubElement(imp, "baseimpuestos").text = f"{subtotal:.2f}"
    ET.SubElement(imp, "importe").text = f"{total_impuestos:.2f}"
    
    return ET.tostring(factura, encoding="utf-8", xml_declaration=True).decode()


def numero_a_letras(numero):
    """Convierte un número a palabras en español."""
    unidades = ["", "UNO", "DOS", "TRES", "CUATRO", "CINCO", "SEIS", "SIETE", "OCHO", "NUEVE"]
    decenas = ["", "", "VEINTE", "TREINTA", "CUARENTA", "CINCUENTA", "SESENTA", "SETENTA", "OCHENTA", "NOVENTA"]
    centenas = ["", "CIENTO", "DOSCIENTOS", "TRESCIENTOS", "CUATROCIENTOS", "QUINIENTOS", "SEISCIENTOS", "SETECIENTOS", "OCHOCIENTOS", "NOVECIENTOS"]
    
    if numero == 0:
        return "CERO PESOS CON 00 CENTAVOS"
    
    if numero < 10:
        return f"{unidades[numero]} PESOS CON 00 CENTAVOS"
    elif numero < 20:
        especiales = ["DIEZ", "ONCE", "DOCE", "TRECE", "CATORCE", "QUINCE", "DIECISEIS", "DIECISIETE", "DIECIOCHO", "DIECINUEVE"]
        return f"{especiales[numero - 10]} PESOS CON 00 CENTAVOS"
    elif numero < 100:
        d = numero // 10
        u = numero % 10
        resultado = decenas[d]
        if u > 0:
            resultado += f" Y {unidades[u]}"
        return f"{resultado} PESOS CON 00 CENTAVOS"
    elif numero < 1000:
        c = numero // 100
        resto = numero % 100
        resultado = centenas[c]
        if resto > 0:
            resultado += f" {numero_a_letras(resto).split(' PESOS')[0]}"
        return f"{resultado} PESOS CON 00 CENTAVOS"
    else:
        # Simplificado para números grandes
        return f"CANTIDAD {numero} PESOS CON 00 CENTAVOS"
