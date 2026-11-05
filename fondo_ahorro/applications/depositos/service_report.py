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
from xml.sax.saxutils import escape


class ReportService:
    
    @staticmethod
    def comprobante_pdf(data, user=None):
        
        # if isinstance(data, dict):
        #     deposito = data.get('data', {}).get('cuentas', data.get('cuentas', []))
        # elif isinstance(data, list):
        #     deposito = data
        # else:
        #     deposito = []
        
        deposito = data[0]
    
        deposito_app = deposito["applications"]
        
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
                f"COMPROBANTE DE DEPOSITO",
                title_style
            )
        )
        elements.append(Spacer(1, 2))
        elements.append(
            Paragraph(
                f"{deposito['description']}",
                title_style
            )
        )

        elements.append(Spacer(1, 45))
        
        # ---------------------------------------
        # 2. METADATA
        # ---------------------------------------
        creador = deposito["user_create"].upper()
        # proceso = deposito_app["proceso"]
        fecha_deposito = deposito["date"]
        fecha_deposito = fecha_deposito.strftime("%d/%m/%Y")
        metadata_data = [
            # [
            #     Paragraph("<b>Fecha Deposito:</b>", label_style),
            #     Paragraph(str(fecha_deposito), value_style),

            #     Paragraph("<b>Tipo Proceso:</b>", label_style),
            #     Paragraph(str(proceso["descripcion"]), value_style),
            # ],
            # [
            #     Paragraph("<b>N° Deposito:</b>", label_style),
            #     Paragraph(deposito["deposit_number"], value_style),

            #     Paragraph("<b>Monto:</b>", label_style),
            #     Paragraph(str(deposito["amount"]), value_style),
            # ],
            [
                Paragraph("<b>Socio:</b>", label_style),
                Paragraph(f"{deposito_app[0]["person"]}", value_style),  
            ],
            [
                Paragraph("<b>Grado:</b>", label_style),
                Paragraph(f"{deposito_app[0]["employee_grade"].upper()}", value_style),

                Paragraph("<b>Codigo Funcionario:</b>", label_style),
                Paragraph(f"{deposito_app[0]["employee_codigo"]}", value_style),
            ],
            [
                Paragraph("<b>Realizo por:</b>", label_style),
                Paragraph(f"{creador}", value_style),
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
        
        monto_formateado = f"{deposito['amount']:,.0f}".replace(',','.')
        # ---------------------------------------
        # 3. DATA
        # ---------------------------------------
        table_data = [
            [
                Paragraph("N° Deposito", cell_header_style),
                Paragraph("Descripción / Glosa", cell_header_style),
                Paragraph("Fecha Deposito", cell_header_style),
                Paragraph("Monto", cell_header_style)
            ]
        ]
        table_data.append([
            Paragraph(str(deposito["deposit_number"]), cell_style),
            Paragraph(escape(deposito["description"]), cell_style),
            Paragraph(fecha_deposito, cell_style),
            Paragraph(f"${monto_formateado}", cell_style),
        ])
        
        
        mov_table = Table(
            table_data,
            colWidths=[70, 330, 70, 70]
        )

        mov_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#20682A")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),

                ("ALIGN", (2, 0), (3, -1), "RIGHT"),

                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),

                ("GRID", (0, 0), (-1, -2), 0.5,
                    colors.HexColor("#CFE1CB")),

                # ("SPAN", (0, -1), (1, -1)),

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
        
        
        
        
        