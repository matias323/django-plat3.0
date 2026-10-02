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
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, Border, Side, PatternFill
from openpyxl.utils import get_column_letter
from io import BytesIO
from django.http import HttpResponse


class ReporteService:
    
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
# class LibroDiario:
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
    
    #generar libro diario excel
    def libro_diario_excel(data):
        if isinstance(data, dict):
            asientos = data.get('data', {}).get('cuentas', data.get('cuentas', []))
        elif isinstance(data, list):
            asientos = data
        else:
            asientos = []
            
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Libro Diario"
        sheet.views.sheetView[0].showGridLines = True  # Asegura que las líneas de cuadrícula sean visibles
        
        # --- PALETA DE ESTILOS ---
        font_titulo = Font(name="Calibri", size=16, bold=True, color="1E293B")
        fill_titulo = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
        
        font_header = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        fill_header = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
        
        #letra color rojo
        font_nulo = Font(name="Calibri", size=10, bold=True, color="FF0000")
        
        font_data = Font(name="Calibri", size=10)
        
         # Bordes
        border_thin = Border(
            left=Side(style='thin', color='E2E8F0'),
            right=Side(style='thin', color='E2E8F0'),
            top=Side(style='thin', color='E2E8F0'),
            bottom=Side(style='thin', color='E2E8F0')
        )
        
        # Formato de moneda contable ($1.000 / -$1.000 / $0)
        FORMATO_MONEDA = '$#,##0;-$#,##0;"-"'
        
        # --- 1. TÍTULO GENERAL ---
        sheet["A1"] = "REPORTE DE LIBRO DIARIO"
        sheet["A1"].font = font_titulo
        sheet["A1"].alignment = Alignment(horizontal="center", vertical="center")
        sheet["A1"].fill = fill_titulo
        sheet.merge_cells("A1:M1")
        sheet.row_dimensions[1].height = 35

        # --- 2. ENCABEZADOS DE COLUMNA ---
        headers = [
            "N° Asiento", "N° Comprobante", "Fecha Asiento", "Periodo Contable", 
            "Tipo Asiento", "Estado", "N° Cuenta", "Nombre Cuenta", "Doc. Referencia", "Debe", "Haber", "Glosa General", "Glosa Detalle"
        ]
        
        sheet.row_dimensions[3].height = 25
        for columna, header in enumerate(headers, start=1):
            celda = sheet.cell(row=4, column=columna)
            celda.value = header
            celda.font = font_header
            celda.fill = fill_header
            celda.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

        # --- 3. RECORRIDO DE DATOS ---
        fila = 5
        
        for asiento in asientos:
            # Obtener valores soportando objetos o diccionarios
            
            num_asiento = asiento.get('numero_asiento')
            num_comprobante = asiento.get('numero_comprobante')
            fecha_asiento = asiento.get('fecha_asiento')
            tipo_asiento = asiento.get('asiento_tipo')
            estado = asiento.get('asiento_estado')
            glosa_general = asiento.get('glosa')
            
             # periodo
            periodo = asiento.get('periodo')
            # print(periodo)
            periodo_contable = f"{periodo.get('month_name')} - {periodo.get('year')}"
            
            #nulo
            is_null = asiento.get('is_null')
            
            if is_null:
                # Asignación de valores
                sheet.cell(row=fila, column=1, value=num_asiento)
                sheet.cell(row=fila, column=2, value=num_comprobante)
                sheet.cell(row=fila, column=3, value=fecha_asiento)
                sheet.cell(row=fila, column=4, value=periodo_contable)
                sheet.cell(row=fila, column=5, value=tipo_asiento)
                sheet.cell(row=fila, column=6, value=estado)
                sheet.cell(row=fila, column=7, value="ASIENTO NULO")
                
                for col_idx in range(1, 14):
                    celda = sheet.cell(row=fila, column=col_idx)
                    celda.font = font_nulo
                    celda.border = border_thin
                    # celda.color = "E2E8F0"
                    
                    # Alineación y formatos específicos
                    if col_idx in (10, 11):  # Debe, Haber, Saldo
                        celda.number_format = FORMATO_MONEDA
                        celda.alignment = Alignment(horizontal="right", vertical="center")
                    elif col_idx in (1, 3):    # Fecha, N° Asiento
                        celda.alignment = Alignment(horizontal="center", vertical="center")
                    else:
                        celda.alignment = Alignment(horizontal="left", vertical="center")
                
                fila += 2
                continue
            
            
            #movimientos
            movimientos = asiento.get('movimientos', [])
            for mov in movimientos:
                #cuenta
                cuenta = mov.get('cuenta')
                num_cuenta = cuenta.get('num_cuenta')
                nombre_cuenta = cuenta.get('nombre')
                doc_referencia = '-'
                debe = mov.get('debe', 0)
                haber = mov.get('haber', 0)
                glosa_detalle = mov.get('glosa')
                
                # Asignación de valores
                sheet.cell(row=fila, column=1, value=num_asiento)
                sheet.cell(row=fila, column=2, value=num_comprobante)
                sheet.cell(row=fila, column=3, value=fecha_asiento)
                sheet.cell(row=fila, column=4, value=periodo_contable)
                sheet.cell(row=fila, column=5, value=tipo_asiento)
                sheet.cell(row=fila, column=6, value=estado)
                sheet.cell(row=fila, column=7, value=num_cuenta)
                sheet.cell(row=fila, column=8, value=nombre_cuenta)
                sheet.cell(row=fila, column=9, value=doc_referencia)
                
                # Montos
                sheet.cell(row=fila, column=10, value=debe)
                sheet.cell(row=fila, column=11, value=haber)
                sheet.cell(row=fila, column=12, value=glosa_general)
                sheet.cell(row=fila, column=13, value=glosa_detalle)
                
                # Aplicar fuentes, alineación, bordes y formatos de moneda
                for col_idx in range(1, 14):
                    celda = sheet.cell(row=fila, column=col_idx)
                    celda.font = font_data
                    celda.border = border_thin
                    
                    # Alineación y formatos específicos
                    if col_idx in (10, 11):  # Debe, Haber, Saldo
                        celda.number_format = FORMATO_MONEDA
                        celda.alignment = Alignment(horizontal="right", vertical="center")
                    elif col_idx in (1, 3):    # Fecha, N° Asiento
                        celda.alignment = Alignment(horizontal="center", vertical="center")
                    else:
                        celda.alignment = Alignment(horizontal="left", vertical="center")
                
                fila += 1
            fila += 1 # Espacio en blanco entre cuentas
        
        # Inmovilizar paneles (deja fijos el título y los encabezados al hacer scroll)
        sheet.freeze_panes = "A5"

        # --- 4. AUTO-AJUSTE ANCHO DE COLUMNAS ---
        for col in sheet.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                # Evita calcular el ancho basado en filas combinadas para no distorsionar
                if cell.row in (1,) or cell.coordinate in sheet.merged_cells:
                    continue
                if cell.value is not None:
                    max_len = max(max_len, len(str(cell.value)))
            sheet.column_dimensions[col_letter].width = max(max_len + 4, 12)

        # --- 5. RESPUESTA HTTP ---
        output = BytesIO()
        workbook.save(output)
        output.seek(0)
        
        response = HttpResponse(
            output.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = 'attachment; filename="libro_diario.xlsx"'
        
        return response  
    
    #generar libro mayor excel
    @staticmethod
    def libro_mayor_excel(data):
        if isinstance(data, dict):
            cuentas = data.get('data', {}).get('cuentas', data.get('cuentas', []))
        elif isinstance(data, list):
            cuentas = data
        else:
            cuentas = []
            
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Libro Mayor"
        sheet.views.sheetView[0].showGridLines = True  # Asegura que las líneas de cuadrícula sean visibles

        # --- PALETA DE ESTILOS ---
        font_titulo = Font(name="Calibri", size=16, bold=True, color="1E293B")
        fill_titulo = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
        
        font_header = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        fill_header = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
        
        font_cuenta = Font(name="Calibri", size=11, bold=True, color="0F172A")
        fill_cuenta = PatternFill(start_color="E2E8F0", end_color="E2E8F0", fill_type="solid")
        
        font_data = Font(name="Calibri", size=10)
        
        # Bordes
        border_thin = Border(
            left=Side(style='thin', color='E2E8F0'),
            right=Side(style='thin', color='E2E8F0'),
            top=Side(style='thin', color='E2E8F0'),
            bottom=Side(style='thin', color='E2E8F0')
        )
        
        # Formato de moneda contable ($1.000 / -$1.000 / $0)
        FORMATO_MONEDA = '$#,##0;-$#,##0;"-"'

        # --- 1. TÍTULO GENERAL ---
        sheet["A1"] = "REPORTE DE LIBRO MAYOR"
        sheet["A1"].font = font_titulo
        sheet["A1"].alignment = Alignment(horizontal="center", vertical="center")
        sheet["A1"].fill = fill_titulo
        sheet.merge_cells("A1:J1")
        sheet.row_dimensions[1].height = 35

        # --- 2. ENCABEZADOS DE COLUMNA ---
        headers = [
            "N° Cuenta", "Nombre Cuenta", "Grupo", "Fecha", 
            "N° Asiento", "Glosa", "Doc Ref", "Debe", "Haber", "Saldo"
        ]
        
        sheet.row_dimensions[3].height = 25
        for columna, header in enumerate(headers, start=1):
            celda = sheet.cell(row=4, column=columna)
            celda.value = header
            celda.font = font_header
            celda.fill = fill_header
            celda.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

        # --- 3. RECORRIDO DE DATOS ---
        fila = 5
        
        for cta in cuentas:
            # Obtener valores soportando objetos o diccionarios
            
            num_cuenta = cta.get('num_cuenta')
            cta_nombre = cta.get('nombre')
            cta_tipo = cta.get('cuenta_tipo')
            saldo_inicial = cta.get('saldo_inicial', 0)
            fecha_desde = datetime.strptime(str(cta.get('fecha_desde')), "%Y-%m-%d").strftime("%d-%m-%Y")
            fecha_hasta = datetime.strptime(str(cta.get('fecha_hasta')), "%Y-%m-%d").strftime("%d-%m-%Y")
            
            #mostrar rangos de fecha de busqueda
            # --- 2. SUBTÍTULO GENERAL ---
            sheet["A2"] = f"{fecha_desde} - {fecha_hasta}"
            sheet["A2"].font = font_titulo
            sheet["A2"].alignment = Alignment(horizontal="center", vertical="center")
            sheet["A2"].fill = fill_titulo
            sheet.merge_cells("A2:J2")
            sheet.row_dimensions[1].height = 35
            
            
            # Fila separadora/encabezado por cuenta
            sheet.row_dimensions[fila].height = 22
            sheet[f"A{fila}"] = f"CUENTA: {num_cuenta} - {cta_nombre}"
            sheet[f"A{fila}"].font = font_cuenta
            sheet[f"A{fila}"].fill = fill_cuenta
            sheet[f"A{fila}"].alignment = Alignment(horizontal="left", vertical="center")
            sheet.merge_cells(f"A{fila}:F{fila}")
            
            sheet[f"G{fila}"] = f"SALDO INICIAL:"
            sheet[f"G{fila}"].font = font_cuenta
            sheet[f"G{fila}"].fill = fill_cuenta
            sheet[f"G{fila}"].alignment = Alignment(horizontal="right", vertical="center")
            sheet.merge_cells(f"G{fila}:I{fila}")
            
            sheet[f"J{fila}"].value = saldo_inicial
            sheet[f"J{fila}"].font = font_cuenta
            sheet[f"J{fila}"].fill = fill_cuenta
            sheet[f"J{fila}"].alignment = Alignment(horizontal="right", vertical="center")
            sheet[f"J{fila}"].number_format = FORMATO_MONEDA
            
            fila += 1
            
            movimientos = cta.get('movimientos', [])
            
            for mov in movimientos:
                # print(mov)
                sheet.row_dimensions[fila].height = 19
                
                # Asientos
                asiento = mov.get('asiento')
                
                fecha_asiento = asiento.get('fecha_asiento')
                num_asiento = asiento.get('numero_asiento')
                glosa = asiento.get('glosa')
                debe = mov.get('debe', 0)
                haber = mov.get('haber', 0)
                saldo = mov.get('saldo', 0)
                
                # Asignación de valores
                sheet.cell(row=fila, column=1, value=num_cuenta)
                sheet.cell(row=fila, column=2, value=cta_nombre)
                sheet.cell(row=fila, column=3, value=cta_tipo)
                sheet.cell(row=fila, column=4, value=fecha_asiento)
                sheet.cell(row=fila, column=5, value=num_asiento)
                sheet.cell(row=fila, column=6, value=glosa)
                sheet.cell(row=fila, column=7, value='-')
                
                # Montos
                sheet.cell(row=fila, column=8, value=debe)
                sheet.cell(row=fila, column=9, value=haber)
                sheet.cell(row=fila, column=10, value=saldo)
                
                # Aplicar fuentes, alineación, bordes y formatos de moneda
                for col_idx in range(1, 11):
                    celda = sheet.cell(row=fila, column=col_idx)
                    celda.font = font_data
                    celda.border = border_thin
                    
                    # Alineación y formatos específicos
                    if col_idx in (8, 9, 10):  # Debe, Haber, Saldo
                        celda.number_format = FORMATO_MONEDA
                        celda.alignment = Alignment(horizontal="right", vertical="center")
                    elif col_idx in (4, 5):    # Fecha, N° Asiento
                        celda.alignment = Alignment(horizontal="center", vertical="center")
                    else:
                        celda.alignment = Alignment(horizontal="left", vertical="center")
                
                fila += 1
                
            fila += 1 # Espacio en blanco entre cuentas
        
        # Inmovilizar paneles (deja fijos el título y los encabezados al hacer scroll)
        sheet.freeze_panes = "A5"

        # --- 4. AUTO-AJUSTE ANCHO DE COLUMNAS ---
        for col in sheet.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                # Evita calcular el ancho basado en filas combinadas para no distorsionar
                if cell.row in (1,) or cell.coordinate in sheet.merged_cells:
                    continue
                if cell.value is not None:
                    max_len = max(max_len, len(str(cell.value)))
            sheet.column_dimensions[col_letter].width = max(max_len + 4, 12)

        # --- 5. RESPUESTA HTTP ---
        output = BytesIO()
        workbook.save(output)
        output.seek(0)
        
        response = HttpResponse(
            output.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = 'attachment; filename="libro_mayor.xlsx"'
        
        return response
    
    #libro mayor pdf
    def libro_mayor_pdf(data, user):
        if isinstance(data, dict):
            cuentas = data.get('data', {}).get('cuentas', data.get('cuentas', []))
        elif isinstance(data, list):
            cuentas = data
        else:
            cuentas = []
        
        # print(cuentas)
        cuenta = cuentas[0]
            
        fecha_desde = datetime.strptime(str(cuenta.get('fecha_desde')), "%Y-%m-%d").strftime("%d-%m-%Y")
        fecha_hasta = datetime.strptime(str(cuenta.get('fecha_hasta')), "%Y-%m-%d").strftime("%d-%m-%Y")
        
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
            'SubtitleStyle', 
            parent=styles['Normal'], 
            fontSize=12, 
            leading=10,
            textColor=colors.HexColor("#000000"),
            alignment=1
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
                f"LIBRO MAYOR",
                title_style
            )
        )
        elements.append(Spacer(1, 5))
        
        rango_busqueda = f"Del {fecha_desde} al {fecha_hasta}"
        elements.append(
            Paragraph(
                f"{rango_busqueda}",
                subtitle_style
            )
        )

        elements.append(Spacer(1, 45))
        
        # ----------------------------------------------------
        # 2. ITERAR ASIENTOS CONTABLES
        # ----------------------------------------------------

        for cta in cuentas:
            cuenta_elements = []
            
            num_cuenta = cta.get('num_cuenta')
            cta_nombre = cta.get('nombre')
            cta_tipo = cta.get('cuenta_tipo')
            saldo_inicial = cta.get('saldo_inicial', 0)
            # fecha_desde = datetime.strptime(str(cta.get('fecha_desde')), "%Y-%m-%d").strftime("%d-%m-%Y")
            # fecha_hasta = datetime.strptime(str(cta.get('fecha_hasta')), "%Y-%m-%d").strftime("%d-%m-%Y")
            
            total_debe_cuenta = 0
            total_haber_cuenta = 0
            

            # Encabezado del Asiento
            header_txt = f"<b>Cuenta: {num_cuenta} - {cta_nombre}</b> | Saldo Inicial: {f"${saldo_inicial:,.0f}".replace(",", ".")}"
            
            # Tabla del detalle del asiento
            table_data = [
                # Fila 0: Encabezado del asiento
                [Paragraph(header_txt, asiento_header_style), "", "", ""],
                # Fila 1: Encabezados de columnas
                [
                    Paragraph("N° Asiento", cell_header_style),
                    Paragraph("N° Comprobante", cell_header_style),
                    Paragraph("Glosa", cell_header_style),
                    Paragraph("Debe (CLP)", cell_header_style),
                    Paragraph("Haber (CLP)", cell_header_style),
                    Paragraph("Saldo (CLP)", cell_header_style)
                ]
            ]
            

            # Filas de Movimientos
            for mov in cta.get('movimientos', []):
                debe = int(mov.get('debe', 0) or 0)
                haber = int(mov.get('haber', 0) or 0)
                saldo = int(mov.get('saldo', 0) or 0)

                total_debe_cuenta = total_debe_cuenta + debe
                total_haber_cuenta = total_haber_cuenta + haber
                
                asiento = mov.get('asiento')
                num_asiento = str(asiento.get('numero_asiento'))
                num_comprobante = asiento.get('numero_comprobante')
                glosa = asiento.get('glosa')
                
                table_data.append([
                    Paragraph(num_asiento, cell_style),
                    Paragraph(num_comprobante, cell_style),
                    Paragraph(glosa, cell_style),
                    Paragraph(
                        f"${debe:,.0f}".replace(",", "."),
                        cell_style
                    ),
                    Paragraph(
                        f"${haber:,.0f}".replace(",", "."),
                        cell_style
                    ),
                    Paragraph(
                        f"${saldo:,.0f}".replace(",", "."),
                        cell_style
                    )
                ])
                
                
            # Glosa General + Totales del Asiento
            glosa_gen = f"<b>Total Movimientos:</b>"
            table_data.append([
                Paragraph(glosa_gen, cell_style),
                "", "",
                Paragraph(
                    f"${total_debe_cuenta:,.0f}".replace(",", "."),
                    cell_style
                ),
                Paragraph(
                    f"${total_haber_cuenta:,.0f}".replace(",", "."),
                    cell_style
                ),
                Paragraph("", cell_style)
            ])
            

            t_asiento = Table(table_data, colWidths = [50, 65, 185, 80, 80, 80])
            t_asiento.setStyle(TableStyle([
                # Fila 0: Header Gris claro
                ('SPAN', (0, 0), (5, 0)),
                ('BACKGROUND', (0, 0), (5, 0), colors.HexColor("#E2F0E3")),
                
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
            
            

            cuenta_elements.append(t_asiento)
            cuenta_elements.append(Spacer(1, 10))

            # KeepTogether evita que un asiento individual se corte feo entre dos páginas
            elements.append(KeepTogether(cuenta_elements))
            
        
        
        elements.append(Spacer(1, 5))
        

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
    
    
        
        
        
        



