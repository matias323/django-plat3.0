
//capturar el crftoken para las solicitudes
const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value;

document.addEventListener("DOMContentLoaded", () => {
    let asientosData = [];

    //inputs de busqueda
    const filterPeriodo = document.getElementById('filter-periodo');
    const filterTipo = document.getElementById('filter-tipo');
    const filterEstado = document.getElementById('filter-estado');
    const filterFechaDesde = document.getElementById('filter-fecha-desde');
    const filterFechaHasta = document.getElementById('filter-fecha-hasta');

    //valores de busqueda
    let periodo = 0;
    let tipo = 0;
    let estado = 0;
    let fechaDesde = '';
    let fechaHasta = '';
    

    /**
     * Obtener clase de badge para tipo de asiento
     */
    function getBadgeTipoClass(tipo) {
        switch (tipo) {
            case 'APERTURA': return 'bg-primary text-white';
            case 'EGRESOS': return 'bg-danger text-white';
            case 'INGRESOS': return 'bg-info text-dark';
            case 'TRASPASO': return 'bg-secondary text-white';
            case 'AJUSTE': return 'bg-dark text-white';
            case 'CIERRE': return 'bg-success text-white';
            default: return 'bg-light text-dark border';
        }
    }

    /**
     * Obtener clase de badge para estado
     */
    function getBadgeEstadoClass(estado) {
        switch (estado) {
            case 'CONTABILIZADO': return 'bg-success text-white';
            case 'BORRADOR': return 'bg-warning text-dark';
            case 'ANULADO': return 'bg-danger text-white';
            default: return 'bg-secondary text-white';
        }
    }

    function formatMoney(amount) {
        const num = parseInt(amount) || 0;
        return num.toLocaleString('es-CL', { 
            style: 'currency',
            currency: 'CLP',
            minimumFractionDigits: 0,
            maximumFractionDigits: 0 });
    }

    //capturar click buscar
    document.addEventListener('click', async (e) => {
        if(e.target && e.target.closest('#btn-buscar-libro-diario')) {
            e.preventDefault();
            Swal.showLoading();
            periodo = filterPeriodo.options[filterPeriodo.selectedIndex].value;
            tipo = filterTipo.options[filterTipo.selectedIndex].value;
            estado = filterEstado.options[filterEstado.selectedIndex].value;
            fechaDesde = filterFechaDesde.value.trim();
            fechaHasta = filterFechaHasta.value.trim();

            asientosData = await buscarAsientos(periodo, tipo, estado, fechaDesde, fechaHasta);
            actualizarKpis(asientosData);
            renderizarLibroDiario(asientosData);
            Swal.close();
            if (asientosData.length === 0) {
                Swal.fire({
                    icon: 'warning',
                    title: 'No se encontraron asientos.',
                })
            }
        }
    })

    // buscar asientos
    const buscarAsientos = async (periodo, tipo, estado, fechaDesde, fechaHasta) => {
        try {
            const response = await fetch(`/contabilidad/asientos_contables/busqueda/buscar/`, {
                method: 'POST',
                headers: {
                    'Content-Type': "application/json",
                    'X-CSRFToken': csrftoken,
                    'X-App-Request': 'true'
                },
                body: JSON.stringify({
                    periodo,
                    tipo,
                    estado,
                    fechaDesde,
                    fechaHasta
                })
            })
            const data = await response.json();
            console.log(data)
            return data.data;
        } catch (error) {
            console.error(error);
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: 'No fue posible buscar los asientos.',
            })
            return [];
        }
    }

    /**
     * Actualiza los contadores y sumas en las tarjetas KPI
     */
    function actualizarKpis(asientos) {
        const totalAsientosEl = document.getElementById('kpi-total-asientos');
        const totalMovimientosEl = document.getElementById('kpi-total-movimientos');
        const totalDebeEl = document.getElementById('kpi-total-debe');
        const totalHaberEl = document.getElementById('kpi-total-haber');
        const badgeCuadreEl = document.getElementById('kpi-badge-cuadre');

        let totalMovimientos = 0;
        let sumaDebe = 0;
        let sumaHaber = 0;

        asientos.forEach(a => {
            if (!a.is_null) {
                (a.movimientos || []).forEach(m => {
                    totalMovimientos++;
                    sumaDebe += Number(m.debe) || 0;
                    sumaHaber += Number(m.haber) || 0;
                });
            }
        });

        if (totalAsientosEl) totalAsientosEl.textContent = asientos.length;
        if (totalMovimientosEl) totalMovimientosEl.textContent = totalMovimientos;
        if (totalDebeEl) totalDebeEl.textContent = formatMoney(sumaDebe);
        if (totalHaberEl) totalHaberEl.textContent = formatMoney(sumaHaber);

        // Indicador de Cuadre
        if (badgeCuadreEl) {
            const diff = (sumaDebe - sumaHaber);
            if (diff === 0) {
                badgeCuadreEl.className = 'badge bg-success-subtle text-success border border-success-subtle px-2 py-1';
                badgeCuadreEl.innerHTML = '<i class="bi bi-check-circle-fill me-1"></i> Sumas Iguales (Cuadrado)';
            } else {
                badgeCuadreEl.className = 'badge bg-danger-subtle text-danger border border-danger-subtle px-2 py-1';
                badgeCuadreEl.innerHTML = `<i class="bi bi-exclamation-triangle-fill me-1"></i> Descuadre: ${formatMoney(diff)}`;
            }
        }
    }

    /**
     * Renderiza el listado oficial de asientos contables del Libro Diario
     */
    function renderizarLibroDiario(asientos) {
        const contenedor = document.getElementById('contenedor-asientos-diario');
        const grandTotalContainer = document.getElementById('contenedor-sumas-iguales');
        if (!contenedor) return;


        if (asientos.length === 0) {
            contenedor.innerHTML = `
                <div class="card border-0 shadow-sm text-center py-5 my-4">
                    <div class="card-body">
                        <div class="display-6 text-muted mb-3"><i class="bi bi-search"></i></div>
                        <h5 class="fw-bold text-dark">No se encontraron asientos contables</h5>
                        <p class="text-muted mb-3">No existen registros que coincidan con los filtros seleccionados.</p>
                    </div>
                </div>
            `;
            const btnReset = document.getElementById('btn-reset-filtros-empty');
            if (btnReset) {
                btnReset.addEventListener('click', () => {
                    document.getElementById('btn-limpiar-filtros')?.click();
                });
            }
            if (grandTotalContainer) grandTotalContainer.classList.add('d-none');
            return;
        }

        let sumaTotalDebe = 0;
        let sumaTotalHaber = 0;

        let html = '';

        // card con boton imprimir y excel
        html += `
            <div class="card border-0 shadow-sm">
                <div class="card-body">
                    <div class="d-flex justify-content-between align-items-center mb-3">
                        <h5 class="fw-bold text-dark">Libro Diario</h5>
                        <div>
                            <button type="button" class="btn btn-sm btn-outline-primary" id="btn-imprimir-libro-diario"><i class="bi bi-printer me-1"></i> Imprimir</button>
                            <button type="button" class="btn btn-sm btn-outline-success" id="btn-exportar-libro-diario"><i class="bi bi-file-earmark-excel me-1"></i> Exportar a Excel</button>
                        </div>
                    </div>
                </div>
            </div><br>
        `;

        asientos.forEach((asiento, index) => {
            const isAnulado = asiento.is_null === true;
            const badgeTipoClass = getBadgeTipoClass(asiento.asiento_tipo);
            const badgeEstadoClass = getBadgeEstadoClass(asiento.asiento_estado);
            let doc_referencia = asiento.origen ? asiento.origen.voucher_number : '';

            // Subtotales del asiento
            let subtotalDebe = 0;
            let subtotalHaber = 0;
            (asiento.movimientos || []).forEach(m => {
                subtotalDebe += Number(m.debe) || 0;
                subtotalHaber += Number(m.haber) || 0;
            });

            if (!isAnulado) {
                sumaTotalDebe += subtotalDebe;
                sumaTotalHaber += subtotalHaber;
            }

            const isCuadrado = (subtotalDebe - subtotalHaber) === 0;

            html += `
            <article class="journal-entry-card ${isAnulado ? 'opacity-75 border-danger-subtle' : ''}">
                <!-- Encabezado del Asiento -->
                <header class="journal-entry-header d-flex flex-wrap justify-content-between align-items-center gap-2">
                    <div class="d-flex align-items-center flex-wrap gap-2">
                        <span class="journal-number-badge">
                            <i class="bi bi-journal-check text-primary me-1"></i>${asiento.numero_asiento}
                        </span>
                        <span class="badge ${badgeTipoClass} px-2 py-1">${asiento.asiento_tipo || 'DIARIO'}</span>
                        <span class="badge ${badgeEstadoClass} px-2 py-1">${asiento.asiento_estado || 'BORRADOR'}</span>
                        <span class="text-muted small ms-1">
                            <i class="bi bi-calendar3 me-1"></i><strong>Fecha:</strong> ${asiento.fecha_asiento || '-'}
                        </span>
                        <span class="text-muted small">
                            <i class="bi bi-clock-history me-1"></i><strong>Período:</strong> ${asiento.periodo.month_name} - ${asiento.periodo.year}
                        </span>
                    </div>
                </header>

                <!-- Glosa General -->
                <div class="px-3 py-2 bg-light border-bottom text-secondary small d-flex align-items-center gap-2">
                    <i class="bi bi-card-text text-primary"></i>
                    <strong class="text-dark">Glosa:</strong> 
                    <span class="${isAnulado ? 'text-decoration-line-through' : ''}">${asiento.glosa || 'Sin descripción'}</span>
                    <span class="badge bg-secondary-subtle text-dark ms-auto">Moneda: CLP</span>
                </div>

                <!-- Tabla de Cuentas y Movimientos -->
                <div class="table-responsive">
                    <table class="table journal-entry-table table-sm table-hover align-middle">
                        <thead>
                            <tr>
                                <th style="width: 50px;" class="text-center">#</th>
                                <th style="width: 140px;">Código Cuenta</th>
                                <th>Denominación de la Cuenta</th>
                                <th style="width: 130px;">Referencia / Doc</th>
                                <th>Glosa Detallada</th>
                                <th style="width: 140px;" class="text-end">Debe</th>
                                <th style="width: 140px;" class="text-end">Haber</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${asiento.is_null ? 
                            `<tr>
                                <td colspan="8" class="text-center text-muted">
                                    <span class="text-danger">
                                        <i class="bi bi-exclamation-triangle-fill"></i>Asiento contable NULO
                                    </span>
                                </td>
                            </tr>` : ''}
                            ${(asiento.movimientos || []).map((mov, idx) => `
                                <tr>
                                    <td class="text-center text-muted small">${idx + 1}</td>
                                    <td>
                                        <span class="badge bg-light text-dark font-monospace border px-2 py-1 fw-bold">
                                            ${mov.cuenta.num_cuenta || '-'}
                                        </span>
                                    </td>
                                    <td>
                                        <div class="fw-semibold text-dark">${mov.cuenta.nombre || '-'}</div>
                                    </td>
                                    <td>
                                        ${doc_referencia ? `<span class="badge bg-secondary-subtle text-secondary font-monospace">${doc_referencia}</span>` : '<span class="text-muted">-</span>'}
                                    </td>
                                    <td class="text-muted small">${mov.glosa || '-'}</td>
                                    <td class="text-end cell-currency ${mov.debe > 0 ? 'text-success fw-bold' : 'text-muted'}">
                                        ${mov.debe > 0 ? formatMoney(mov.debe) : '-'}
                                    </td>
                                    <td class="text-end cell-currency ${mov.haber > 0 ? 'text-primary fw-bold' : 'text-muted'}">
                                        ${mov.haber > 0 ? formatMoney(mov.haber) : '-'}
                                    </td>
                                </tr>
                            `).join('')}
                        </tbody>
                        <tfoot>
                            <tr class="table-light fw-bold">
                                <td colspan="5" class="text-end text-uppercase small text-muted pe-3">
                                    ${isCuadrado ? 
                                        '<span class="text-success"><i class="bi bi-check2-all me-1"></i> Asiento Cuadrado</span>' : 
                                        '<span class="text-danger"><i class="bi bi-exclamation-octagon-fill me-1"></i> Asiento Descuadrado</span>'}
                                    &nbsp;|&nbsp; Subtotales Asiento:
                                </td>
                                <td class="text-end cell-currency text-success border-top border-2">
                                    ${formatMoney(subtotalDebe)}
                                </td>
                                <td class="text-end cell-currency text-primary border-top border-2">
                                    ${formatMoney(subtotalHaber)}
                                </td>
                            </tr>
                        </tfoot>
                    </table>
                </div>
            </article>
            `;
        });

        contenedor.innerHTML = html;
    }

     /**
     * Limpiar filtros
     */
    document.addEventListener('click', (e) => {
        if (e.target && e.target.closest('#btn-clear-filters')) {
            e.preventDefault();
            if (filterPeriodo) filterPeriodo.value= 0;
            if (filterTipo) filterTipo.value = 0;
            if (filterEstado) filterEstado.value = 0;
            if (filterFechaDesde) filterFechaDesde.value = '';
            if (filterFechaHasta) filterFechaHasta.value = '';
            asientosData = [];
            const contenedor = document.getElementById('contenedor-asientos-diario');
            contenedor.innerHTML = '';
            
        }
    });

    //capturar click btn excel
    document.addEventListener('click', (e) => {
        if (e.target && e.target.closest('#btn-exportar-libro-diario')) {
            e.preventDefault();
            libroDiarioExcel();
        }
    });

    const libroDiarioExcel = async () => {
        try {
            const response = await fetch("/contabilidad/asientos_contables/libro_diario/excel/",
                {
                    method: "POST",
                    headers: {
                        "X-Requested-With": "XMLHttpRequest",
                        'X-CSRFToken': csrftoken,
                        'X-App-Request': 'true'
                    },

                    body: JSON.stringify({
                        periodo,
                        tipo,
                        estado,
                        fechaDesde,
                        fechaHasta
                    })
                }
            );

            if (!response.ok) {
                throw new Error(
                    "No fue posible generar el archivo Excel"
                );
            }

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const link = document.createElement("a");
            link.href = url;
            link.download = "libro_diario.xlsx";
            document.body.appendChild(link);
            link.click();
            link.remove();
            window.URL.revokeObjectURL(url);
        } catch (error) {
            console.error(error);
            Swal.fire({
                icon: "error",
                title: "Error",
                text: error.message,
            });
        } finally {
            Swal.close();
        }
    }

    /**
     * Exportar el Libro Diario actual en formato CSV
     */
    // function exportarLibroDiarioCsv() {
    //     const asientos = asientosData;
    //     if (asientos.length === 0) {
    //         alert('No hay registros para exportar con los filtros seleccionados.');
    //         return;
    //     }

    //     const headers = [
    //         'Numero Asiento',
    //         'Numero de Comprobante',
    //         'Fecha Asiento',
    //         'Periodo Contable',
    //         'Tipo Asiento',
    //         'Moneda',
    //         'Estado',
    //         'Glosa General',
    //         'Linea',
    //         'Numero Cuenta',
    //         'Nombre Cuenta',
    //         'Doc Referencia',
    //         'Glosa Detalle',
    //         'Debe',
    //         'Haber'
    //     ];

    //     const rows = [];
    //     rows.push(headers.join(';'));

    //     asientos.forEach((a, index) => {
    //         const asientoData = [
    //             `"${a.numero_asiento || ''}"`,
    //             `"${a.numero_comprobante || ''}"`,
    //             `"${a.fecha_asiento || ''}"`,
    //             `"${a.periodo.month_name} - ${a.periodo.year}"`,
    //             `"${a.asiento_tipo || ''}"`,
    //             `"${'CLP'}"`,
    //             `"${a.asiento_estado || ''}"`,
    //             `"${(a.glosa || '').replace(/"/g, '""')}"`,
    //         ];
    //         if (a.is_null) {
    //             const movimientoData = ['ASIENTO NULO'];
    //             const fullRow = [...asientoData, ...movimientoData];
    //             rows.push(fullRow.join(';'));
    //             rows.push('');
    //             return;
    //         }
    //         (a.movimientos || []).forEach((m, idx) => {
    //             const movimientoData = [  
    //                 idx + 1,
    //                 `"${m.cuenta.num_cuenta || ''}"`,
    //                 `"${(m.cuenta.nombre || '').replace(/"/g, '""')}"`,
    //                 `"${m.refDoc || ''}"`,
    //                 `"${(m.glosa || '').replace(/"/g, '""')}"`,
    //                 (Number(m.debe) || 0).toFixed(0),
    //                 (Number(m.haber) || 0).toFixed(0)
    //             ];
    //             const fullRow = [...asientoData, ...movimientoData];
    //             rows.push(fullRow.join(';'));
    //         });
    //         // 🔹 Agregar una fila vacía entre asientos (excepto después del último)
    //         if (index < asientos.length - 1) {
    //             rows.push('');
    //         }
    //     });

    //     const csvContent = '\uFEFF' + rows.join('\r\n');
    //     const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    //     const url = URL.createObjectURL(blob);
    //     const link = document.createElement('a');
    //     link.setAttribute('href', url);
    //     link.setAttribute('download', `Libro_Diario.csv`);
    //     document.body.appendChild(link);
    //     link.click();
    //     document.body.removeChild(link);
    // }

    //capturar click btn pdf
    document.addEventListener('click', (e) => {
        if (e.target && e.target.closest('#btn-imprimir-libro-diario')) {
            e.preventDefault();
            generarPdf(periodo, tipo, estado, fechaDesde, fechaHasta);
        }
    });


    //generar pdf
    const generarPdf = async (periodo, tipo, estado, fechaDesde, fechaHasta) => {
        try {
            const response = await fetch(`/contabilidad/asientos_contables/libro_diario/pdf/`, {
                method: 'POST',
                headers: {
                    'Content-Type': "application/json",
                    'X-CSRFToken': csrftoken,
                    'X-App-Request': 'true'
                },
                body: JSON.stringify({
                    periodo,
                    tipo,
                    estado,
                    fechaDesde,
                    fechaHasta
                })
            })

            if (!response.ok) {
                throw new Error("No fue posible generar el PDF.");
            }

            const blob = await response.blob();
            const pdfUrl = URL.createObjectURL(blob);
            window.open(pdfUrl, '_blank');

            setTimeout(() => {
                URL.revokeObjectURL(pdfUrl);
            }, 1000);

        } catch (error) {
            console.error(error);
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: 'No fue posible generar el PDF.',
            })
        }
    }




});