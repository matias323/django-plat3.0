//capturar el crftoken para las solicitudes
const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value;

document.addEventListener("DOMContentLoaded", () => {

    //inputs de busqueda
    const filterPeriodo = document.getElementById('filter-periodo');
    const filterFechaDesde = document.getElementById('filter-fecha-desde');
    const filterFechaHasta = document.getElementById('filter-fecha-hasta');
    const modalAccounts = new bootstrap.Modal(document.getElementById('modal-accounts'));
    const inputSearchAccountModal = document.getElementById('search-account-modal');
    const tableAccountsBody = document.getElementById('tbody-accounts-catalog');
    const inputCuenta = document.querySelector('.input-codigo-cuenta');
    const inputNombre = document.querySelector('.input-nombre-cuenta');
    const inputCuentaId = document.querySelector('.input-cuenta-id');

    //valores de busqueda
    let periodo = 0;
    let cuenta = 0;
    let fechaDesde = '';
    let fechaHasta = '';

    // Estado global del Libro Mayor
    const mayorState = {
        dataCuentas: [],
        vistaActiva: 'tabular', // 'tabular' | 'cuentast' | 'balance'
    };


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
        if(e.target && e.target.closest('#btn-buscar-libro-mayor')) {
            e.preventDefault();
            Swal.showLoading();
            periodo = filterPeriodo.options[filterPeriodo.selectedIndex].value;
            cuenta = inputCuentaId.value.trim();
            fechaDesde = filterFechaDesde.value.trim();
            fechaHasta = filterFechaHasta.value.trim();

            let data = await buscarData(periodo, fechaDesde, fechaHasta, cuenta);
            Swal.close();
            if (!data.success) {
                Swal.fire({
                    icon: 'warning',
                    title: data.message,
                })
            }
            mayorState.dataCuentas = data.data.cuentas;
            initLibroMayor();
        }
    });

    // buscar asientos
    const buscarData = async (periodo, fechaDesde, fechaHasta, cuenta) => {
        try {
            const response = await fetch(`/contabilidad/asientos_contables/libro_mayor/data/`, {
                method: 'POST',
                headers: {
                    'Content-Type': "application/json",
                    'X-CSRFToken': csrftoken,
                    'X-App-Request': 'true'
                },
                body: JSON.stringify({
                    periodo,
                    fechaDesde,
                    fechaHasta,
                    cuenta
                })
            })
            const data = await response.json();
            return data;
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
     * Inicialización principal
     */
    function initLibroMayor() {

        // 1. Configurar escuchadores de eventos
        configurarEventosVistas();

        // 2. Renderizar vista activa y KPIs
        renderizarTodo();
    }


    /**
     * Configurar pestañas / alternador de vistas (Tabular, Cuentas T, Balance)
     */
    function configurarEventosVistas() {
        const navButtons = document.querySelectorAll('[data-view-target]');
        navButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                navButtons.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                mayorState.vistaActiva = btn.dataset.viewTarget;
                renderizarVistaActiva();
            });
        });
    }

    /**
     * Renderiza todo (KPIs y la vista actualmente seleccionada)
     */
    function renderizarTodo() {
        actualizarKpis();
        renderizarVistaActiva();
    }

    /**
     * Actualiza tarjetas KPI superiores
     */
    function actualizarKpis() {
        const kpiTotalCuentas = document.getElementById('kpi-mayor-total-cuentas');
        const kpiTotalDebe = document.getElementById('kpi-mayor-total-debe');
        const kpiTotalHaber = document.getElementById('kpi-mayor-total-haber');
        const kpiEstadoCuadre = document.getElementById('kpi-mayor-cuadre');
        const cuentas = mayorState.dataCuentas;
        let sumaDebe = 0;
        let sumaHaber = 0;
        let cuentasSaldadas = 0;

        cuentas.forEach(cta => {
            sumaDebe += cta.total_debe;
            sumaHaber += cta.total_haber;
            cuentasSaldadas++;
        });

        if (kpiTotalCuentas) kpiTotalCuentas.textContent = cuentas.length;
        if (kpiTotalDebe) kpiTotalDebe.textContent = formatMoney(sumaDebe);
        if (kpiTotalHaber) kpiTotalHaber.textContent = formatMoney(sumaHaber);

        if (kpiEstadoCuadre) {
            const diff = (sumaDebe - sumaHaber);
            if (diff === 0) {
                kpiEstadoCuadre.className = 'badge bg-success-subtle text-success border border-success-subtle px-2 py-1';
                kpiEstadoCuadre.innerHTML = `<i class="bi bi-check-circle-fill me-1"></i> Balance Equilibrado (100% Cuadrado)`;
            } else {
                kpiEstadoCuadre.className = 'badge bg-danger-subtle text-danger border border-danger-subtle px-2 py-1';
                kpiEstadoCuadre.innerHTML = `<i class="bi bi-exclamation-triangle-fill me-1"></i> Descuadre: ${formatMoney(diff)}`;
            }
        }
    }

    /**
     * Despacha el render según la vista activa
     */
    function renderizarVistaActiva() {
        const contenedor = document.getElementById('contenedor-vista-mayor');
        if (!contenedor) return;

        if (mayorState.dataCuentas.length === 0) {
            contenedor.innerHTML = `
                <div class="card border-0 shadow-sm text-center py-5 my-4">
                    <div class="card-body">
                        <div class="display-6 text-muted mb-3"><i class="bi bi-inbox"></i></div>
                        <h5 class="fw-bold text-dark">No se encontraron movimientos</h5>
                        <p class="text-muted mb-3">No existen registros que coincidan con la cuenta o filtros seleccionados.</p>
                    </div>
                </div>
            `;
            const btnReset = document.getElementById('btn-reset-filtros-empty-mayor');
            if (btnReset) {
                btnReset.addEventListener('click', () => {
                    document.getElementById('btn-limpiar-filtros-mayor')?.click();
                });
            }
            return;
        }

        switch (mayorState.vistaActiva) {
            case 'tabular':
                renderizarVistaTabular(contenedor);
                break;
            case 'cuentast':
                renderizarVistaCuentasT(contenedor);
                break;
            case 'balance':
                renderizarVistaBalanceComprobacion(contenedor);
                break;
            default:
                renderizarVistaTabular(contenedor);
        }
    }

    /**
     * =========================================================================
     * VISTA 1: FORMATO TABULAR DETALLADO DEL LIBRO MAYOR
     * =========================================================================
     */
    function renderizarVistaTabular(contenedor) {
        let html = '';
        let mayorStateCuentas =  mayorState.dataCuentas;

        // card con boton imprimir y excel
        html += `
            <div class="card border-0 shadow-sm">
                <div class="card-body">
                    <div class="d-flex justify-content-between align-items-center mb-3">
                        <h5 class="fw-bold text-dark">Libro Mayor</h5>
                        <div>
                            <button type="button" class="btn btn-sm btn-outline-primary" id="btn-libro-mayor"><i class="bi bi-printer me-1"></i> Imprimir</button>
                            <button type="button" class="btn btn-sm btn-outline-success" id="btn-libro-mayor-csv"><i class="bi bi-file-earmark-excel me-1"></i> Exportar a Excel</button>
                        </div>
                    </div>
                </div>
            </div><br>
        `;

        mayorStateCuentas.forEach((cta) => {
            let cuentaMovimientos = Object.values(cta.movimientos);

            html += `
            <article class="ledger-account-card">
                <!-- Encabezado de la Cuenta -->
                <div class="ledger-account-header d-flex flex-wrap justify-content-between align-items-center gap-2">
                    <div class="d-flex align-items-center gap-2">
                        <span class="badge bg-dark font-monospace fs-6 px-3 py-2">${cta.num_cuenta}</span>
                        <div>
                            <h5 class="fw-bold mb-0 text-dark">${cta.nombre}</h5>
                            <div class="text-muted small">
                                <span>Grupo: <strong>${cta.cuenta_tipo}</strong></span> &nbsp;•&nbsp; 
                            </div>
                        </div>
                    </div>
                    <div class="text-end">
                        <span class="badge bg-primary-subtle text-primary border border-primary px-3 py-1 fs-6">
                            <i class="bi bi-arrow-up-right me-1"></i> SALDO INICAL: ${formatMoney(cta.saldo_inicial)}
                        </span>
                    </div>
                </div>

                <!-- Tabla de Movimientos y Saldo Progresivo -->
                <div class="table-responsive">
                    <table class="table ledger-table table-hover align-middle">
                        <thead>
                            <tr>
                                <th style="width: 105px;">Fecha</th>
                                <th style="width: 140px;">N° Asiento</th>
                                <th>Glosa / Concepto de la Operación</th>
                                <th style="width: 140px;">Doc. Referencia</th>
                                <th style="width: 135px;" class="text-end">Debe</th>
                                <th style="width: 135px;" class="text-end">Haber</th>
                                <th style="width: 140px;" class="text-end bg-success-subtle text-success">Saldo</th>
                            </tr>
                        </thead>
                        <tbody>`;
            cuentaMovimientos.forEach(mov => {
                html += `
                    <tr>
                        <td class="text-nowrap">${mov.asiento.fecha_asiento || '-'}</td>
                        <td>
                            <span class="badge bg-light text-primary border font-monospace text-decoration-none btn-asiento" data-id="${mov.asiento.id}">
                                <i class="bi bi-box-arrow-up-right me-1"></i>${mov.asiento.numero_asiento}
                            </span>
                        </td>
                        <td>
                            <div class="fw-semibold text-dark">${mov.glosa}</div>
                        </td>
                        <td>
                            ${mov.asiento.origen ? `<span class="badge bg-light text-secondary border font-monospace">${mov.asiento.origen.voucher_number}</span>` : '<span class="text-muted">-</span>'}
                        </td>
                        <td class="text-end cell-currency ${mov.debe > 0 ? 'text-success fw-bold' : 'text-muted'}">
                            ${mov.debe > 0 ? formatMoney(mov.debe) : '-'}
                        </td>
                        <td class="text-end cell-currency ${mov.haber > 0 ? 'text-primary fw-bold' : 'text-muted'}">
                            ${mov.haber > 0 ? formatMoney(mov.haber) : '-'}
                        </td>
                        <td class="text-end cell-currency text-success">
                            ${formatMoney(mov.saldo)}
                        </td>
                    </tr>
                `;
            });

            html += `
                    </tbody>
                    <tfoot>
                        <!-- Fila de Sumas Totales -->
                        <tr class="table-light">
                            <td colspan="4" class="text-end text-uppercase small text-muted pe-3">
                                <strong>Sumas Totales de la Cuenta:</strong>
                            </td>
                            <td class="text-end cell-currency text-success fw-bold border-top border-2">
                                ${formatMoney(cta.total_debe)}
                            </td>
                            <td class="text-end cell-currency text-primary fw-bold border-top border-2">
                                ${formatMoney(cta.total_haber)}
                            </td>
                            <td colspan="2" class="text-center text-muted small bg-light">
                                Balance por Cuenta
                            </td>
                        </tr>
                        <!-- Fila de Saldo Final Definitivo -->
                        <tr class="bg-light fw-bold border-top border-dark">
                            <td colspan="6" class="text-end text-uppercase small pe-3">
                                <span class="badge bg-success me-2">
                                    <i class="bi bi-arrow-up-right me-1"></i>
                                </span>
                                SALDO FINAL AL CIERRE DEL PERÍODO:
                            </td>
                            <td class="text-end cell-currency text-success fs-6 t-closing-line">
                                ${formatMoney(cta.saldo_final)}
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
     * =========================================================================
     * VISTA 2: ESQUEMA GRÁFICO DE CUENTAS EN "T"
     * =========================================================================
     */
    function renderizarVistaCuentasT(contenedor) {
        let html = `
            <div class="row g-4">
        `;

        // card con boton imprimir y excel
        html += `
            <div class="card border-0 shadow-sm">
                <div class="card-body">
                    <div class="d-flex justify-content-between align-items-center mb-3">
                        <h5 class="fw-bold text-dark">Libro Mayor</h5>
                        <div>
                            <button type="button" class="btn btn-sm btn-outline-primary" id="btn-libro-mayor"><i class="bi bi-printer me-1"></i> Imprimir</button>
                            <button type="button" class="btn btn-sm btn-outline-success" id="btn-libro-mayor-csv"><i class="bi bi-file-earmark-excel me-1"></i> Exportar a Excel</button>
                        </div>
                    </div>
                </div>
            </div><br>
        `;

        mayorState.dataCuentas.forEach(cta => {
            const debits = cta.movimientos.filter(m => m.debe > 0);
            const credits = cta.movimientos.filter(m => m.haber > 0);

            html += `
            <div class="col-12 col-md-6 col-xl-4">
                <div class="t-account-card">
                    <!-- Parte Superior de la Cuenta T -->
                    <div class="t-account-top">
                        <div class="d-flex justify-content-between align-items-center mb-1">
                            <span class="badge bg-dark font-monospace">${cta.num_cuenta}</span>
                            <span class="badge ${cta.cuenta_tipo_id in [1, 5] ? 'bg-success-subtle text-success border border-success' : 'bg-primary-subtle text-primary border border-primary'} fs-xs">
                                Grupo: ${cta.cuenta_tipo}
                            </span>
                        </div>
                        <div class="t-account-title text-truncate" title="${cta.nombre}">${cta.nombre}</div>
                    </div>

                    <!-- Barra Superior de la T: DEBE | HABER -->
                    <div class="t-account-labels">
                        <div class="t-label-debe"><i class="bi bi-arrow-down-left"></i> DEBE (Débito)</div>
                        <div class="t-label-haber">HABER (Crédito) <i class="bi bi-arrow-up-right"></i></div>
                    </div>

                    <!-- Columnas Centrales de la T -->
                    <div class="t-account-columns">
                        <!-- Columna Izquierda: DEBE -->
                        <div class="t-col-debe">
                            ${debits.length > 0 ? debits.map(d => `
                                <div class="t-movement-item" title="${d.fecha_asiento} | ${d.asiento.numero_asiento} | ${d.glosa}">
                                    <span class="t-movement-ref">${d.asiento.numero_asiento}</span>
                                    <span class="t-movement-amount text-success">${formatMoney(d.debe)}</span>
                                </div>
                            `).join('') : '<div class="text-center text-muted small py-4">Sin débitos</div>'}
                        </div>

                        <!-- Columna Derecha: HABER -->
                        <div class="t-col-haber">
                            ${credits.length > 0 ? credits.map(c => `
                                <div class="t-movement-item" title="${c.fecha_asiento} | ${c.asiento.numero_asiento} | ${c.glosa}">
                                    <span class="t-movement-ref">${c.asiento.numero_asiento}</span>
                                    <span class="t-movement-amount text-primary">${formatMoney(c.haber)}</span>
                                </div>
                            `).join('') : '<div class="text-center text-muted small py-4">Sin créditos</div>'}
                        </div>
                    </div>

                    <!-- Subtotales de la Cuenta T -->
                    <div class="t-account-subtotals">
                        <div class="t-subtotal-debe">
                            <span class="small text-muted d-block fs-xs">TOTAL DEBE</span>
                            ${formatMoney(cta.total_debe)}
                        </div>
                        <div class="t-subtotal-haber">
                            <span class="small text-muted d-block fs-xs">TOTAL HABER</span>
                            ${formatMoney(cta.total_haber)}
                        </div>
                    </div>

                    <!-- Saldo Neto y Cierre Contable -->
                    <div class="t-account-balance-footer">
                        <div>
                            <span class="text-muted fs-xs d-block">SALDO FINAL</span>
                            <strong class="text-success">
                                SALDO
                            </strong>
                        </div>
                        <div class="text-end">
                            <span class="fs-6 fw-bold font-monospace t-closing-line text-success">
                                ${formatMoney(cta.saldo_final)}
                            </span>
                        </div>
                    </div>
                </div>
            </div>
            `;
        });

        html += `</div>`;
        contenedor.innerHTML = html;
    }

    //btn exportar excel
    document.addEventListener('click', (e) => {
        if (e.target && e.target.closest('#btn-libro-mayor-csv')) {
            e.preventDefault();
            Swal.showLoading();
            libroMayorExcel();
        }
    });

    const libroMayorExcel = async () => {
        try {
            const response = await fetch("/contabilidad/asientos_contables/libro_mayor/excel/",
                {
                    method: "POST",
                    headers: {
                        "X-Requested-With": "XMLHttpRequest",
                        'X-CSRFToken': csrftoken,
                        'X-App-Request': 'true'
                    },

                    body: JSON.stringify({
                        periodo,
                        fechaDesde,
                        fechaHasta,
                        cuenta
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
            link.download = "libro_mayor.xlsx";
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

    //capturar click btn pdf
    document.addEventListener('click', (e) => {
        if (e.target && e.target.closest('#btn-libro-mayor')) {
            e.preventDefault();
            generarPdf(periodo, fechaDesde, fechaHasta, cuenta);
        }
    });

    //generar pdf
    const generarPdf = async (periodo, fechaDesde, fechaHasta, cuenta) => {
        try {
            const response = await fetch(`/contabilidad/asientos_contables/libro_mayor/pdf/`, {
                method: 'POST',
                headers: {
                    'Content-Type': "application/json",
                    'X-CSRFToken': csrftoken,
                    'X-App-Request': 'true'
                },
                body: JSON.stringify({
                    periodo,
                    fechaDesde,
                    fechaHasta,
                    cuenta
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


    /**
     * Exportar el Libro Mayor en formato CSV
     */
    // function exportarLibroMayorCsv() {
    //     const cuentas = mayorState.dataCuentas;
    //     if (cuentas.length === 0) {
    //         alert('No hay movimientos mayorizados para exportar con los filtros seleccionados.');
    //         return;
    //     }

    //     const headers = [
    //         'Numero Cuenta',
    //         'Nombre Cuenta',
    //         'Grupo',
    //         'Fecha Asiento',
    //         'Numero Asiento',
    //         'Glosa Movimiento',
    //         'Doc Referencia',
    //         'Debe',
    //         'Haber',
    //         'Saldo',
    //     ];

    //     const rows = [];
    //     rows.push(headers.join(';'));

    //     cuentas.forEach((cta,index) => {
    //         // 🔹 1. Fila de Saldo Inicial por Cuenta
    //         const filaSaldoInicial = [
    //             `"${cta.num_cuenta}"`,
    //             `"${cta.nombre.replace(/"/g, '""')}"`,
    //             `"${cta.cuenta_tipo || ''}"`,
    //             '""', // Fecha Asiento
    //             '""', // Numero Asiento
    //             '"SALDO INICIAL"', // Glosa Movimiento
    //             '""', // Doc Referencia
    //             (0).toFixed(0), // Debe
    //             (0).toFixed(0), // Haber
    //             (cta.saldo_inicial || 0).toFixed(0), // Saldo Inicial
    //         ];
    //         rows.push(filaSaldoInicial.join(';'));
    //         cta.movimientos.forEach(m => {
    //             const row = [
    //                 `"${cta.num_cuenta}"`,
    //                 `"${cta.nombre.replace(/"/g, '""')}"`,
    //                 `"${cta.cuenta_tipo}"`,
    //                 `"${m.fecha_asiento || ''}"`,
    //                 `"${m.asiento.numero_asiento || ''}"`,
    //                 `"${(m.glosa || '').replace(/"/g, '""')}"`,
    //                 `"${m.refDoc || ''}"`,
    //                 (m.debe || 0).toFixed(0),
    //                 (m.haber || 0).toFixed(0),
    //                 (m.saldo || 0).toFixed(0),
    //             ];
    //             rows.push(row.join(';'));
    //         });
    //         // 🔹 Agregar una fila vacía entre asientos (excepto después del último)
    //         if (index < cuentas.length - 1) {
    //             rows.push('');
    //         }
    //     });

    //     const csvContent = '\uFEFF' + rows.join('\r\n');
    //     const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    //     const url = URL.createObjectURL(blob);
    //     const link = document.createElement('a');
    //     link.setAttribute('href', url);
    //     link.setAttribute('download', `Libro_Mayor.csv`);
    //     document.body.appendChild(link);
    //     link.click();
    //     document.body.removeChild(link);
    // }






    /**
     * Obtener cuenta por código exacto
     */
    function obtenerCuentaPorCodigo(num_cuenta) {
        return CATALOGO_CUENTAS.find(c => c.num_cuenta === num_cuenta) || null;
    }

    // Inicializar Datalist de cuentas para autocompletado rápido
    const datalistCuentas = document.getElementById('list-cuentas');
    if (datalistCuentas && typeof CATALOGO_CUENTAS !== 'undefined') {
        CATALOGO_CUENTAS.forEach(c => {
            const opt = document.createElement('option');
            opt.value = c.num_cuenta;
            opt.textContent = `${c.num_cuenta} - ${c.nombre}`;
            datalistCuentas.appendChild(opt);
        });
    }

    /**
     * Buscar cuentas por término (código o nombre)
     */
    function buscarCuentas(query) {
        if (!query) return CATALOGO_CUENTAS;
        const q = query.toLowerCase().trim();
        return CATALOGO_CUENTAS.filter(c => 
            c.num_cuenta.toLowerCase().includes(q) || 
            c.nombre.toLowerCase().includes(q) 
        );
    }

    /**
     * Modal del Plan de Cuentas
     */

    document.addEventListener('click', (e) => {
        if (e.target && e.target.closest('.btn-search-account')) {
            openAccountsModal();
        }
    });

    function openAccountsModal() {
        if (inputSearchAccountModal) inputSearchAccountModal.value = '';
        renderAccountsTable(CATALOGO_CUENTAS);
        modalAccounts.show();
        setTimeout(() => {
            if (inputSearchAccountModal) inputSearchAccountModal.focus();
        }, 300);
    }

    function renderAccountsTable(accountsList) {
        if (!tableAccountsBody) return;
        tableAccountsBody.innerHTML = '';

        if (accountsList.length === 0) {
            tableAccountsBody.innerHTML = `
                <tr>
                    <td colspan="4" class="text-center text-muted py-4">
                        <i class="bi bi-search fs-3 d-block mb-2"></i>
                        No se encontraron cuentas que coincidan con la búsqueda.
                    </td>
                </tr>
            `;
            return;
        }

        accountsList.forEach(acc => {
            const tr = document.createElement('tr');
            tr.className = 'account-item-selectable';
            tr.innerHTML = `
                <td class="fw-bold text-primary" style="">${acc.num_cuenta}</td>
                <td style="">${acc.nombre}</td>
                <td>
                    <span class="badge ${acc.is_auxiliar == true ? 'bg-primary' : 'bg-secondary'}">
                        ${acc.is_auxiliar == true ? 'Si' : 'No'}
                    </span>
                </td>
                <td class="text-center" style="">
                    <span class="badge ${acc.is_tratamiento_especial == true ? 'bg-primary' : 'bg-secondary'}">
                         ${acc.is_tratamiento_especial == true ? 'Si' : 'No'}
                    </span>
                </td>
            `;

            tr.addEventListener('click', () => {
                selectAccountForActiveRow(acc);
            });

            tableAccountsBody.appendChild(tr);
        });
    }

    if (inputSearchAccountModal) {
        inputSearchAccountModal.addEventListener('input', (e) => {
            const filtered = buscarCuentas(e.target.value);
            renderAccountsTable(filtered);
        });
    }

    function selectAccountForActiveRow(acc) {
        if (inputCuenta) {
            inputCuenta.value = acc.num_cuenta;
            inputCuenta.classList.remove('is-invalid');
            inputCuenta.classList.add('is-valid');
        }
        if (inputNombre) {
            inputNombre.value = acc.nombre;
        }
        if (inputCuentaId) {
            inputCuentaId.value = acc.id;
        }

        modalAccounts.hide();
    }

    // Cambio directo en código de cuenta
    inputCuenta.addEventListener('input', () => {
        const code = inputCuenta.value.trim();
        const account = obtenerCuentaPorCodigo(code);
        if (account) {
            inputNombre.value = account.nombre;
            inputCuentaId.value = account.id;
            inputCuenta.classList.remove('is-invalid');
            inputCuenta.classList.add('is-valid');
        } else {
            inputNombre.value = '';
            inputCuentaId.value = '';
            inputCuenta.classList.remove('is-valid');
        }
    });



});

