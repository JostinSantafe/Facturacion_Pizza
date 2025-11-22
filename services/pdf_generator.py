import os
import base64
from io import BytesIO
from xml.etree import ElementTree as ET

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib import colors


def _parse_xml(xml_text: str):
	root = ET.fromstring(xml_text)
	enc = root.find("Encabezado")
	detalle = root.find("Detalle")
	data = {
		"uuid": enc.findtext("llavecomprobante", default=""),
		"cliente": enc.findtext("nombrereceptor", default="Cliente"),
		"total": enc.findtext("total", default="0"),
		"fecha": enc.findtext("fecha", default=""),
		"items": [],
	}
	if detalle is not None:
		for det in detalle.findall("Det"):
			data["items"].append({
				"desc": det.findtext("descripcion", default="Producto"),
				"cant": det.findtext("cantidad", default="1"),
				"precio": det.findtext("precioUnitario", default="0"),
				"importe": det.findtext("importe", default="0"),
			})
	return data


def _fmt_cop(valor: float | str) -> str:
	try:
		num = float(valor)
	except Exception:
		try:
			num = float(str(valor).replace(',', ''))
		except Exception:
			num = 0.0
	return "$" + format(int(round(num)), ",").replace(',', '.')


def generar_pdf_desde_xml(xml_text: str, output_path: str | None = None):
	"""Genera un PDF simple desde el XML de factura.

	Retorna (pdf_path, pdf_base64)
	"""
	data = _parse_xml(xml_text)

	buf = BytesIO()
	doc = SimpleDocTemplate(buf, pagesize=letter, leftMargin=18*mm, rightMargin=18*mm, topMargin=18*mm, bottomMargin=18*mm)
	styles = getSampleStyleSheet()
	styles.add(ParagraphStyle(name="H1Center", parent=styles["Title"], alignment=1, fontSize=20))
	styles.add(ParagraphStyle(name="Label", parent=styles["Normal"], fontName="Helvetica-Bold"))

	story = []

	# Encabezado con QR (si existe)
	qr_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "imagenes", "qr.png")
	if os.path.exists(qr_path):
		try:
			qr_img = Image(qr_path, width=35*mm, height=35*mm)
			qr_img.hAlign = 'RIGHT'
			story.append(Paragraph("FACTURA DE COMPRA", styles["H1Center"]))
			story.append(qr_img)
			story.append(Spacer(1, 8))
		except Exception:
			story.append(Paragraph("FACTURA DE COMPRA", styles["H1Center"]))
			story.append(Spacer(1, 8))
	else:
		story.append(Paragraph("FACTURA DE COMPRA", styles["H1Center"]))
		story.append(Spacer(1, 8))
	# Encabezado
	story.append(Paragraph(f"Factura No.: {data['uuid']}", styles["Normal"]))
	story.append(Paragraph(f"Fecha: {data['fecha']}", styles["Normal"]))
	story.append(Spacer(1, 14))
	story.append(Paragraph("Datos del Cliente", styles["Label"]))
	story.append(Spacer(1, 6))
	story.append(Paragraph(f"Nombre: {data['cliente']}", styles["Normal"]))
	# email puede venir vacío; no rompe
	story.append(Paragraph(f"Email: {''}", styles["Normal"]))
	story.append(Spacer(1, 14))

	# Tabla de items
	rows = [["Producto", "Cant.", "Valor", "Subtotal"]]
	for it in data["items"]:
		rows.append([
			it["desc"],
			it["cant"],
			_fmt_cop(it["precio"]),
			_fmt_cop(it["importe"]),
		])

	tbl = Table(rows, colWidths=[80*mm, 20*mm, 30*mm, 30*mm])
	tbl.setStyle(TableStyle([
		("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
		("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
		("ALIGN", (1, 1), (-1, -1), "RIGHT"),
	]))
	story.append(tbl)
	story.append(Spacer(1, 10))

	# Resumen totales
	try:
		total = float(data.get("total") or 0)
		# si XML trae totales, úsalos; si no, calcula desde items
		if total <= 0 and data["items"]:
			base = sum(float(x.get("importe", 0)) for x in data["items"])
			iva = round(base * 0.19)
			total = base + iva
			subtotal = base
		else:
			subtotal = float(data.get("baseimpuesto") or data.get("subtotal") or 0)
			iva = float(data.get("totalimpuestos") or total - subtotal)
	except Exception:
		subtotal = 0
		iva = 0
		total = 0

	resumen = [
		["Subtotal:", _fmt_cop(subtotal)],
		["IVA (19%):", _fmt_cop(iva)],
		["TOTAL:", _fmt_cop(total)],
	]
	rt = Table(resumen, colWidths=[40*mm, 40*mm])
	rt.setStyle(TableStyle([
		("ALIGN", (1, 0), (-1, -1), "RIGHT"),
		("FONTSIZE", (0, 0), (-1, -2), 10),
		("FONTSIZE", (0, -1), (-1, -1), 12),
		("FONTNAME", (0, -1), (0, -1), "Helvetica-Bold"),
	]))
	story.append(rt)

	doc.build(story)

	pdf_bytes = buf.getvalue()
	buf.close()

	pdf_b64 = base64.b64encode(pdf_bytes).decode("ascii")
	pdf_path = None
	if output_path:
		os.makedirs(os.path.dirname(output_path), exist_ok=True)
		with open(output_path, "wb") as f:
			f.write(pdf_bytes)
		pdf_path = output_path

	return pdf_path, pdf_b64
