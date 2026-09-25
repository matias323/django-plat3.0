import io
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, KeepTogether
from datetime import datetime
from django.utils import timezone
from django.contrib.staticfiles import finders
import os
from django.conf import settings


class AsientoContableServicePDF:
    
    @staticmethod
    def generate_asiento_pdf(asiento, user=None):
        buffer = io.BytesIO()

        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36
        )

        elements = []

        styles = getSampleStyleSheet()

        # Estilos
        title_style = ParagraphStyle(
            "TitleStyle",
            parent=styles["Heading1"],
            fontSize=16,
            leading=10,
            textColor=colors.HexColor("#20682A"),
            alignment=1
        )

        label_style = ParagraphStyle(
            "LabelStyle",
            parent=styles["Normal"],
            fontSize=9,
            leading=11,
            fontName="Helvetica-Bold"
        )

        value_style = ParagraphStyle(
            "ValueStyle",
            parent=styles["Normal"],
            fontSize=9,
            leading=11,
            fontName="Helvetica"
        )

        cell_style = ParagraphStyle(
            "CellStyle",
            parent=styles["Normal"],
            fontSize=8,
            leading=10,
            fontName="Helvetica"
        )

        cell_header_style = ParagraphStyle(
            "CellHeaderStyle",
            parent=styles["Normal"],
            fontSize=10,
            leading=10,
            fontName="Helvetica-Bold",
            textColor=colors.white
        )

        # ---------------------------------------
        # 1. TÍTULO
        # ---------------------------------------
        elements.append(
            Paragraph(
                f"COMPROBANTE DE ASIENTO CONTABLE",
                title_style
            )
        )
        elements.append(Spacer(1, 2))
        
        elements.append(
            Paragraph(
                f"{asiento['numero_comprobante']}",
                title_style
            )
        )

        elements.append(Spacer(1, 45))

        # ---------------------------------------
        # 2. METADATA
        # ---------------------------------------

        periodo = asiento["periodo"]
        creador = asiento["user_create"].upper()
        
        fecha_asiento = asiento["fecha_asiento"]
        fecha_asiento = fecha_asiento.strftime("%d/%m/%Y")

        periodo_desc = f"{periodo['month_name']} - {periodo['year']}"

        metadata_data = [
            [
                Paragraph("<b>Fecha:</b>", label_style),
                Paragraph(str(fecha_asiento), value_style),

                Paragraph("<b>Tipo:</b>", label_style),
                Paragraph(str(asiento["asiento_tipo"]), value_style),
            ],
            [
                Paragraph("<b>Periodo:</b>", label_style),
                Paragraph(periodo_desc, value_style),

                Paragraph("<b>Estado:</b>", label_style),
                Paragraph(str(asiento["asiento_estado"]), value_style),
            ],
            [
                Paragraph("<b>Creado por:</b>", label_style),
                Paragraph(str(creador), value_style),

                Paragraph("<b>N° Asiento:</b>", label_style),
                Paragraph(
                    str(asiento["numero_asiento"] or "-"),
                    value_style
                ),
            ],
            [
                Paragraph("<b>Glosa:</b>", label_style),
                Paragraph(
                    str(asiento["glosa"] or "-"),
                    value_style
                ),
                "",
                ""
            ]
        ]

        metadata_table = Table(
            metadata_data,
            colWidths=[90, 180, 90, 180]
        )

        metadata_table.setStyle(
            TableStyle([
                ("SPAN", (1, 3), (3, 3)),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
            ])
        )

        elements.append(metadata_table)

        elements.append(Spacer(1, 45))

        # ---------------------------------------
        # 3. MOVIMIENTOS
        # ---------------------------------------

        table_data = [
            [
                Paragraph("Cuenta / Código", cell_header_style),
                Paragraph("Descripción / Glosa", cell_header_style),
                Paragraph("Debe", cell_header_style),
                Paragraph("Haber", cell_header_style)
            ]
        ]

        total_debe = 0
        total_haber = 0

        movimientos = asiento["movimientos"]

        for mov in movimientos:

            total_debe += mov["debe"]
            total_haber += mov["haber"]

            cuenta = mov["cuenta"]

            cuenta_label = (
                f"{cuenta['num_cuenta']} - {cuenta['nombre']}"
            )

            table_data.append([
                Paragraph(cuenta_label, cell_style),
                Paragraph(
                    mov["glosa"] or "-",
                    cell_style
                ),
                Paragraph(
                    f"${mov['debe']:,}".replace(",", "."),
                    cell_style
                ),
                Paragraph(
                    f"${mov['haber']:,}".replace(",", "."),
                    cell_style
                ),
            ])
            

        # ---------------------------------------
        # 4. TOTALES
        # ---------------------------------------

        table_data.append([
            Paragraph("<b>TOTALES</b>", cell_style),
            "",
            Paragraph(
                f"<b>${total_debe:,}</b>".replace(",", "."),
                cell_style
            ),
            Paragraph(
                f"<b>${total_haber:,}</b>".replace(",", "."),
                cell_style
            )
        ])

        mov_table = Table(
            table_data,
            colWidths=[180, 200, 80, 80]
        )

        mov_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#20682A")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),

                ("ALIGN", (2, 0), (3, -1), "RIGHT"),

                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),

                ("GRID", (0, 0), (-1, -2), 0.5,
                 colors.HexColor("#CFE1CB")),

                ("SPAN", (0, -1), (1, -1)),

                ("BACKGROUND", (0, -1), (-1, -1),
                 colors.HexColor("#F1F5F9")),

                ("LINEABOVE", (0, -1), (-1, -1), 1,
                 colors.HexColor("#0F2A10")),

                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ])
        )

        elements.append(mov_table)
        
        if user:
            impreso_por = user.person.get_full_name().upper()
        else:
            impreso_por = "Sistema"
            
        fecha_impresion = timezone.localtime(timezone.now()).strftime("%d/%m/%Y %H:%M")
            
        def header_and_footer(canvas, doc):
            # ----------------------------------------------------
            # 1. DIBUJAR LOGO CON COORDENADAS EXACTAS
            # ----------------------------------------------------
            # ---------------------------------------
            # 1. Obtener la ruta absoluta del logo
            # ---------------------------------------
            logo_path = finders.find('img/logo_dibicar.png') # Busca en las carpetas static
            
            # Si no lo encuentra mediante finders, puedes usar la ruta fallback de BASE_DIR:
            if not logo_path:
                logo_path = os.path.join(settings.BASE_DIR, 'static', 'img', 'logo_dibicar.png')
    
            # ---------------------------------------
            # 2. Crear el encabezado con Logo + Título
            # ---------------------------------------
            header_elements = []
    
            if os.path.exists(logo_path):
                # Cargar la imagen y ajustar tamaño (ancho x alto en puntos, 1 pulgada = 72 pt)
                logo_img = Image(logo_path, width=50, height=50)
                logo_img.hAlign = 'LEFT'
            else:
                logo_img = Paragraph("", value_style)
            # logo_path = config.logo.path if (config.logo and os.path.exists(config.logo.path)) else None

            if logo_path:
                # Parámetros del logo
                logo_width = 40   # Ancho de la imagen
                logo_height = 40   # Alto de la imagen
                
                # Coordenadas X e Y:
                # X = 612 (ancho total) - 36 (margen derecho) - 100 (ancho logo) = 476
                # Y = 792 (alto total) - 36 (margen superior) - 40 (alto logo) = 716
                pos_x = 100 - 36 - logo_width
                pos_y = 792 - 20 - logo_height  # Sube más el valor para pegarlo más arriba

                canvas.drawImage(
                    logo_path,
                    x=pos_x,
                    y=pos_y,
                    width=logo_width,
                    height=logo_height,
                    preserveAspectRatio=True,
                    mask='auto'  # Conserva transparencia en imágenes PNG
                )
            
            
            # ----------------------------------------------------
            # 2. PIE DE PÁGINA
            # ----------------------------------------------------
            canvas.saveState()
            
            # Dibujar línea separadora superior del footer
            canvas.setStrokeColor(colors.HexColor("#CBD5E1"))
            canvas.setLineWidth(0.5)
            canvas.line(36, 35, 612 - 36, 35)  # 612 es el ancho estándar de hoja Carta ('letter')

            # Configurar fuente
            canvas.setFont("Helvetica", 8)
            canvas.setFillColor(colors.HexColor("#64748B"))

            # Texto a la izquierda: Impreso por... | Fecha: ...
            text_left = f"Generado por: {impreso_por}  |  Fecha impresión: {fecha_impresion}"
            canvas.drawString(36, 22, text_left)

            # Texto a la derecha: Número de página
            text_right = f"Página {doc.page}"
            canvas.drawRightString(612 - 36, 22, text_right)

            canvas.restoreState()

        # ---------------------------------------
        # 5. GENERAR PDF
        # ---------------------------------------

        doc.build(elements, onFirstPage=header_and_footer,
            onLaterPages=header_and_footer)

        buffer.seek(0)

        return buffer.getvalue()
    

#generar PDF LIBRO DIARIO
class LibroDiarioPDF:
    @staticmethod
    def generate_libro_diario_pdf(data, user=None):
        buffer = io.BytesIO()
        
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=70,
            bottomMargin=36
        )
        
        styles = getSampleStyleSheet()

        # Estilos base
        title_style = ParagraphStyle(
            "TitleStyle",
            parent=styles["Heading1"],
            fontSize=16,
            leading=10,
            textColor=colors.HexColor("#000000"),
            alignment=1
        )
        subtitle_style = ParagraphStyle(
            'SubtitleStyle', parent=styles['Normal'], fontSize=8, leading=10,
            textColor=colors.HexColor('#475569'), fontName='Helvetica'
        )
        asiento_header_style = ParagraphStyle(
            'AsientoHeader', parent=styles['Normal'], fontSize=8, leading=10,
            textColor=colors.HexColor('#0F172A'), fontName='Helvetica-Bold'
        )
        cell_style = ParagraphStyle(
            'CellStyle', parent=styles['Normal'], fontSize=7.5, leading=9, fontName='Helvetica'
        )
        cell_bold = ParagraphStyle(
            'CellBold', parent=styles['Normal'], fontSize=7.5, leading=9, fontName='Helvetica-Bold'
        )
        cell_header_style = ParagraphStyle(
            'CellHeaderStyle', parent=styles['Normal'], fontSize=8, leading=10,
            textColor=colors.white, fontName='Helvetica-Bold'
        )
        value_style = ParagraphStyle(
            "ValueStyle",
            parent=styles["Normal"],
            fontSize=9,
            leading=11,
            fontName="Helvetica"
        )

        elements = []
        styles = getSampleStyleSheet()
        
        # ---------------------------------------
        # 1. TÍTULO
        # ---------------------------------------
        elements.append(
            Paragraph(
                f"LIBRO DIARIO",
                title_style
            )
        )

        elements.append(Spacer(1, 45))
        
        # ----------------------------------------------------
        # 2. ITERAR ASIENTOS CONTABLES
        # ----------------------------------------------------
        gran_total_debe = 0
        gran_total_haber = 0

        for asiento in data:
            asiento_elements = []

            # Si es nulo
            if asiento.get('is_null'):
                header_info = f"<b>Asiento N° {asiento['numero_asiento']}</b> | Fecha: {asiento['fecha_asiento']} | <font color='red'><b>ASIENTO NULO</b></font>"
                asiento_table = Table([[Paragraph(header_info, asiento_header_style)]], colWidths=[540])
                asiento_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#FEE2E2')),
                    ('PADDING', (0, 0), (-1, -1), 4),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#FCA5A5'))
                ]))
                asiento_elements.append(asiento_table)
                asiento_elements.append(Spacer(1, 8))
                elements.append(KeepTogether(asiento_elements))
                continue

            # Encabezado del Asiento
            n_comprobante = f" | Comp: {asiento['numero_comprobante']}" if asiento.get('numero_comprobante') else ""
            header_txt = f"<b>Asiento N° {asiento['numero_asiento']}</b>{n_comprobante} | Fecha: {asiento['fecha_asiento']} | Tipo: {asiento['asiento_tipo']}"
            
            # Tabla del detalle del asiento
            table_data = [
                # Fila 0: Encabezado del asiento
                [Paragraph(header_txt, asiento_header_style), "", "", ""],
                # Fila 1: Encabezados de columnas
                [
                    Paragraph("Cuenta / Código", cell_header_style),
                    Paragraph("Descripción / Glosa Detalle", cell_header_style),
                    Paragraph("Debe (CLP)", cell_header_style),
                    Paragraph("Haber (CLP)", cell_header_style)
                ]
            ]

            total_debe_asiento = 0
            total_haber_asiento = 0

            # Filas de Movimientos
            for mov in asiento.get('movimientos', []):
                debe = int(mov.get('debe', 0) or 0)
                haber = int(mov.get('haber', 0) or 0)
                total_debe_asiento += debe
                total_haber_asiento += haber

                cuenta_obj = mov.get('cuenta')
                cuenta_str = f"{cuenta_obj['num_cuenta']} - {cuenta_obj['nombre']}"

                table_data.append([
                    Paragraph(cuenta_str, cell_style),
                    Paragraph(mov.get('glosa') or '-', cell_style),
                    Paragraph(
                        f"${debe:,.0f}".replace(",", "."),
                        cell_style
                    ),
                    Paragraph(
                        f"${haber:,.0f}".replace(",", "."),
                        cell_style
                    )
                ])

            # Glosa General + Totales del Asiento
            glosa_gen = f"<b>Glosa:</b> {asiento.get('glosa') or '-'}"
            table_data.append([
                Paragraph(glosa_gen, cell_style),
                "",
                Paragraph(
                    f"${total_debe_asiento:,.0f}".replace(",", "."),
                    cell_style
                ),
                Paragraph(
                    f"${total_haber_asiento:,.0f}".replace(",", "."),
                    cell_style
                )
            ])

            gran_total_debe += total_debe_asiento
            gran_total_haber += total_haber_asiento

            t_asiento = Table(table_data, colWidths=[180, 220, 70, 70])
            t_asiento.setStyle(TableStyle([
                # Fila 0: Header Gris claro
                ('SPAN', (0, 0), (3, 0)),
                ('BACKGROUND', (0, 0), (3, 0), colors.HexColor("#E2F0E3")),
                
                # Fila 1: Header Oscuro de la Tabla
                ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#20682A')),
                ('ALIGN', (2, 1), (3, -1), 'RIGHT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                
                # Grid de datos
                ('GRID', (0, 1), (-1, -2), 0.5, colors.HexColor('#CBD5E1')),
                
                # Fila Final: Totales del Asiento
                ('SPAN', (0, -1), (1, -1)),
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#F8FAFC')),
                ('LINEABOVE', (0, -1), (-1, -1), 0.8, colors.HexColor('#0F172A')),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ]))

            asiento_elements.append(t_asiento)
            asiento_elements.append(Spacer(1, 10))

            # KeepTogether evita que un asiento individual se corte feo entre dos páginas
            elements.append(KeepTogether(asiento_elements))

        # ----------------------------------------------------
        # 3. GRAN TOTAL DEL LIBRO DIARIO
        # ----------------------------------------------------
        totales_resumen = [
            [
                Paragraph("<b>TOTAL LIBRO DIARIO</b>", cell_header_style),
                Paragraph(
                    f"<b>${gran_total_debe:,.0f}</b>".replace(",", "."),
                    cell_header_style
                ),
                Paragraph(
                    f"<b>${gran_total_haber:,.0f}</b>".replace(",", "."),
                    cell_header_style
                )
            ]
        ]
        t_resumen = Table(totales_resumen, colWidths=[400, 70, 70])
        t_resumen.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#1E5321")),
            ('ALIGN', (1, 0), (2, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('PADDING', (0, 0), (-1, -1), 5),
        ]))
        
        elements.append(Spacer(1, 5))
        elements.append(t_resumen)

        # ----------------------------------------------------
        # 4. PIE DE PÁGINA
        # ----------------------------------------------------
        
        if user:
            impreso_por = user.person.get_full_name().upper()
        else:
            impreso_por = "Sistema"
            
        fecha_impresion = timezone.localtime(timezone.now()).strftime("%d/%m/%Y %H:%M")
        
        def header_and_footer(canvas, doc):
            # ----------------------------------------------------
            # 1. DIBUJAR LOGO CON COORDENADAS EXACTAS
            # ----------------------------------------------------
            # ---------------------------------------
            # 1. Obtener la ruta absoluta del logo
            # ---------------------------------------
            logo_path = finders.find('img/logo_dibicar.png') # Busca en las carpetas static
            
            # Si no lo encuentra mediante finders, puedes usar la ruta fallback de BASE_DIR:
            if not logo_path:
                logo_path = os.path.join(settings.BASE_DIR, 'static', 'img', 'logo_dibicar.png')
    
            # ---------------------------------------
            # 2. Crear el encabezado con Logo + Título
            # ---------------------------------------
            header_elements = []
    
            if os.path.exists(logo_path):
                # Cargar la imagen y ajustar tamaño (ancho x alto en puntos, 1 pulgada = 72 pt)
                logo_img = Image(logo_path, width=50, height=50)
                logo_img.hAlign = 'LEFT'
            else:
                logo_img = Paragraph("", value_style)
            # logo_path = config.logo.path if (config.logo and os.path.exists(config.logo.path)) else None

            if logo_path:
                # Parámetros del logo
                logo_width = 40   # Ancho de la imagen
                logo_height = 40   # Alto de la imagen
                
                # Coordenadas X e Y:
                # X = 612 (ancho total) - 36 (margen derecho) - 100 (ancho logo) = 476
                # Y = 792 (alto total) - 36 (margen superior) - 40 (alto logo) = 716
                pos_x = 100 - 36 - logo_width
                pos_y = 792 - 20 - logo_height  # Sube más el valor para pegarlo más arriba

                canvas.drawImage(
                    logo_path,
                    x=pos_x,
                    y=pos_y,
                    width=logo_width,
                    height=logo_height,
                    preserveAspectRatio=True,
                    mask='auto'  # Conserva transparencia en imágenes PNG
                )
            
            
            # ----------------------------------------------------
            # 2. PIE DE PÁGINA
            # ----------------------------------------------------
            canvas.saveState()
            
            # Dibujar línea separadora superior del footer
            canvas.setStrokeColor(colors.HexColor("#CBD5E1"))
            canvas.setLineWidth(0.5)
            canvas.line(36, 35, 612 - 36, 35)  # 612 es el ancho estándar de hoja Carta ('letter')

            # Configurar fuente
            canvas.setFont("Helvetica", 8)
            canvas.setFillColor(colors.HexColor("#64748B"))

            # Texto a la izquierda: Impreso por... | Fecha: ...
            text_left = f"Generado por: {impreso_por}  |  Fecha impresión: {fecha_impresion}"
            canvas.drawString(36, 22, text_left)

            # Texto a la derecha: Número de página
            text_right = f"Página {doc.page}"
            canvas.drawRightString(612 - 36, 22, text_right)

            canvas.restoreState()

        # ---------------------------------------
        # 5. GENERAR PDF
        # ---------------------------------------

        doc.build(elements, onFirstPage=header_and_footer,
            onLaterPages=header_and_footer)

        buffer.seek(0)

        return buffer.getvalue()



