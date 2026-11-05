/**
 * LÓGICA DE TEMPLATE BUSQUEDA DEPOSITOS
 *
 */
//capturar el crftoken para las solicitudes
const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value;
document.addEventListener('DOMContentLoaded', () => {
    // Estado global de la vista de depósitos
    const depositosState = {
        depositosData: [],
        paginaActual: 1,
        registrosPorPagina: 10,
        filtros: {
            query: '',
            tipoProceso: 0,
            fechaDesde: '',
            fechaHasta: '',
            montoMin: 0,
            montoMax: 0
        },
    };

    let asientosContables = [];
    let depositosApp = [];
    let dataTableViewAux = null;

    const inputSearch = document.getElementById('input-busqueda-global');
    const btnClearSearch = document.getElementById('btn-clear-global-search');
    const btnSearch = document.getElementById('btn-search');
    const selectTipoProceso = document.getElementById('filtro-tipo-proceso');
    const inputFechaDesde = document.getElementById('filtro-fecha-desde');
    const inputFechaHasta = document.getElementById('filtro-fecha-hasta');
    const inputMontoMin = document.getElementById('filtro-monto-min');
    const inputMontoMax = document.getElementById('filtro-monto-max');
    const btnAplicarFiltros = document.getElementById('btn-aplicar-filtros');
    const tbody = document.getElementById('tbody-depositos');
    let dataTableInstance = null;
    const modalProcesoEl = document.getElementById('modal-proceso-origen');
    const modalProceso = modalProcesoEl ? new bootstrap.Modal(modalProcesoEl) : null;
    const modalAsientoEl = document.getElementById('modal-asiento');
    const modalAsiento = new bootstrap.Modal(modalAsientoEl);
    const tbodyModalMovements = document.getElementById('tbody-modal-movements');
    const modalTotalDebe = document.getElementById('modal-total-debe');
    const modalTotalHaber = document.getElementById('modal-total-haber');
    const modalDiferencia = document.getElementById('modal-diferencia');
    const modalStatusPill = document.getElementById('modal-status-pill');
    let modalRowCounter = 1;


    // Búsqueda en vivo (debounce ligero)
    if (inputSearch) {
        inputSearch.addEventListener('input', (e) => {
            depositosState.filtros.query = e.target.value.trim().toLowerCase();
            if (btnClearSearch) {
                btnClearSearch.classList.toggle('d-none', e.target.value.length === 0);
                btnSearch.classList.toggle('d-none', e.target.value.length === 0);
            }
        });
    }

    if (btnSearch) {
        btnSearch.addEventListener('click', () => {
            if (inputSearch) {
                search();
            }
        });
    }

    if (btnClearSearch) {
        btnClearSearch.addEventListener('click', () => {
            if (inputSearch) {
                inputSearch.value = '';
                depositosState.filtros.query = '';
                btnClearSearch.classList.add('d-none');
                btnSearch.classList.add('d-none');
                inputSearch.focus();
            }
        });
    }

    // Filtros rápidos reactivos
    [selectTipoProceso].forEach(el => {
        if (el) {
            el.addEventListener('change', () => {
                depositosState.filtros.tipoProceso = selectTipoProceso.value;
            });
        }
    });

    if (inputMontoMin) {
        inputMontoMin.addEventListener('input', (e) => {
            depositosState.filtros.montoMin = e.target.value.trim();
        });
    }

    if (inputMontoMax) {
        inputMontoMax.addEventListener('input', (e) => {
            depositosState.filtros.montoMax = e.target.value.trim();
        });
    }

    if (inputFechaDesde) {
        inputFechaDesde.addEventListener('input', (e) => {
            depositosState.filtros.fechaDesde = e.target.value.trim();
        });
    }

    if (inputFechaHasta) {
        inputFechaHasta.addEventListener('input', (e) => {
            depositosState.filtros.fechaHasta = e.target.value.trim();
        });
    }

    // Botón manual de aplicar filtros
    if (btnAplicarFiltros) {
        btnAplicarFiltros.addEventListener('click', () => {
            search();
        });
    }

    // buscar depositos
    const search = async () => {
        Swal.showLoading();
        depositosApp = [];
        asientosContables = [];
        const query = depositosState.filtros.query;
        const tipo = depositosState.filtros.tipoProceso;
        const montoMin = depositosState.filtros.montoMin;
        const montoMax = depositosState.filtros.montoMax;
        const fechaDesde = depositosState.filtros.fechaDesde;
        const fechaHasta = depositosState.filtros.fechaHasta;

        depositosState.depositosData = await getDepositos(query, tipo, fechaDesde, fechaHasta, montoMin, montoMax);
        loadTable();
    }

    const getDepositos = async (query = null, tipo = null, fechaDesde = null, fechaHasta = null, montoMin = null, montoMax = null) => {
        try {
            const response = await fetch(`/depositos/busqueda/`, {
                method: 'POST',
                headers: {
                    'Content-Type': "application/json",
                    'X-CSRFToken': csrftoken,
                    'X-App-Request': 'true'
                },
                body: JSON.stringify({
                    query,
                    tipo,
                    fechaDesde,
                    fechaHasta,
                    montoMin,
                    montoMax
                })
            })
            const data = await response.json();
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

    const loadTable = () => {
        Swal.close();
        if ($.fn.DataTable.isDataTable('.table-depositos')) {
            dataTableInstance.destroy();
        }
        if (depositosState.depositosData == 0){
            tbody.innerHTML = `
                <tr>
                    <td colspan="10" class="text-center py-5 text-muted">
                        <i class="bi bi-search display-6 d-block mb-2 text-secondary opacity-50"></i>
                        <h6 class="fw-bold text-dark">No se encontraron depósitos con los filtros aplicados</h6>
                        <p class="small mb-3">Prueba ajustando los términos de búsqueda o limpiando los filtros avanzados.</p>
                        <button class="btn btn-outline-primary btn-sm btn-restablecer">
                            <i class="bi bi-arrow-clockwise me-1"></i> Restablecer Filtros
                        </button>
                    </td>
                </tr>
            `;
            return;
        }

        dataTableInstance = $('.table-depositos').DataTable({
            data: depositosState.depositosData,
            responsive: false,
            pageLength: 10,
            lengthMenu: [[10, 25, 50, 100], [10, 25, 50, 100]],
            order: [[1, 'asc']],
            language: {
                search: "_INPUT_",
                searchPlaceholder: "Buscar en DataTables...",
                lengthMenu: "Mostrar registros _MENU_",
                info: "Mostrando _START_ a _END_ de _TOTAL_ asientos",
                infoEmpty: "Mostrando 0 a 0 de 0 asientos",
                infoFiltered: "(filtrado de _MAX_ registros totales)",
                zeroRecords: "No se encontraron asientos contables coincidentes",
                paginate: {
                    first: "«",
                    previous: "‹",
                    next: "›",
                    last: "»"
                }
            },
            columns: [
                {
                    data: 'voucher_number',
                    render: function (data) {
                        return `<span class="badge bg-light text-primary border font-monospace fw-bold fs-xs cursor-pointer">${data}</span>`;
                    }
                },
                { 
                    data: 'date', 
                    render: function (data) {
                        return `<div class="fw-semibold text-dark">${data}</div>`
                    }
                },
                {
                    data: 'person',
                    render: function (data, type, row) {
                        return `<strong class="text-dark d-block text-truncate fs-sm" style="max-width: 190px;" title="${data}">
                            ${data}
                        </strong>
                        <span class="badge bg-light text-secondary border font-monospace fs-xs">${formatRUT(row.rut)}</span>`;
                    }
                },
                {
                    data: null,
                    render: function (data, type, row) {
                        let proceso = ``;
                        row.applications.forEach(app => {
                            proceso += `<span class="badge bg-light text-dark border border-dark-subtle badge-attachment-btn fs-xs btn-proceso" 
                            data-app="${app.id}" data-id="${row.id}" title="Ver Proceso">${app.proceso.descripcion}</span>`
                            if (!depositosApp.some(item => item.id === app.id)) {
                                depositosApp.push(app);
                            }
                        })
                        return `${proceso}`
                    }
                },
                {
                    data: 'amount',
                    render: function (data) {
                        return `<span class="cell-currency-clp text-success fs-6 fw-bold">
                                    ${formatMoney(data)}
                                </span>`;
                    }
                },
                {
                    data: null,
                    render: function (data, type, row) {
                        return `<span class="badge bg-info-subtle text-info-emphasis border border-info-subtle badge-attachment-btn btn-document" data-id="${row.id}" 
                                    title="Ver ${row.documents.length} archivos adjuntos">
                                    <i class="bi bi-paperclip me-1"></i>${row.documents.length} adjuntos
                                </span>`
                    }
                },
                {
                    data: null,
                    render: function (data, type, row) {
                        let comprobante = ``;
                        row.applications.forEach(app => {
                            comprobante += `<span class="badge bg-primary-subtle text-primary border border-primary-subtle badge-asiento-btn btn-asiento"
                                                    title="Ver Partida Doble del Asiento" data-app="${app.id}" data-id="${row.id}">
                                                <i class="bi bi-journal-text me-1"></i>${app.asiento_contable.numero_comprobante}
                                            </span>`
                            if (!asientosContables.some(item => item.id === app.asiento_contable.id)) {
                                asientosContables.push(app.asiento_contable);
                            }
                        })

                        return `${comprobante}`
                    }
                }
            ]
        });
    }

    //capturar click btn document
    document.addEventListener('click', (e) => {
        if(e.target && e.target.closest('.btn-document')) {
            e.preventDefault();
            const target = e.target.closest('.btn-document');
            const id = Number(target.dataset.id);
            //1. Buscar el deposito
            const depositoEncontrado = depositosState.depositosData.find(a => a.id === id);
            
            if (depositoEncontrado) {
                abrirModalAdjuntos(depositoEncontrado);
            } else {
                Swal.fire({
                    icon: 'warning',
                    title: 'No se encontraron depositos.',
                })
            }
        }
    })

    //capturar click btn proceso
    document.addEventListener('click', (e) => {
        if(e.target && e.target.closest('.btn-proceso')) {
            e.preventDefault();
            const target = e.target.closest('.btn-proceso');
            const id = Number(target.dataset.id);
            const idApp = Number(target.dataset.app);
            //1. Buscar el deposito
            
            const depositoEncontrado = depositosState.depositosData.find(a => a.id === id);
            const appEncontrado = depositoEncontrado.applications.find(a => a.id === idApp);

            if (depositoEncontrado && appEncontrado) {
                viewOrigen(depositoEncontrado, appEncontrado);
            } else {
                Swal.fire({
                    icon: 'warning',
                    title: 'No se encontraron el proceso.',
                })
            }
        }
    });

    //capturar click asiento contable
    document.addEventListener('click', (e) => {
        if (e.target && e.target.closest('.btn-asiento')) {
            e.preventDefault();
            const target = e.target.closest('.btn-asiento');
            const id = Number(target.dataset.id);
            const idApp = Number(target.dataset.app);
            //1. Buscar el deposito
            const depositoEncontrado = depositosState.depositosData.find(a => a.id === id);
            const appEncontrado = depositoEncontrado.applications.find(a => a.id === idApp);
            if (depositoEncontrado && appEncontrado) {
                viewAsiento(appEncontrado.asiento_contable);
            } else {
                Swal.fire({
                    icon: 'warning',
                    title: 'No se encontro el asiento contable.',
                })
            }
        }
    })

    //ver asiento contable
    const viewAsiento = (asiento) => {
        if (asiento.length === 0) {
            Swal.fire({
                icon: 'warning',
                title: 'No se encontraron asientos contables.',
            })
            return;
        }

        document.getElementById('modal-asiento-num').value = asiento.numero_asiento;
        document.getElementById('modal-asiento-voucher').value = asiento.numero_comprobante;
        document.getElementById('modal-asiento-fecha').value = asiento.fecha_asiento;
        document.getElementById('modal-asiento-periodo').value = asiento.periodo.month_name + ' ' + asiento.periodo.year;
        document.getElementById('modal-asiento-tipo').value = asiento.asiento_tipo;
        document.getElementById('modal-asiento-glosa').value = asiento.glosa;

        // Badge de estado en modal
        const badge = document.getElementById('modal-asiento-badge-estado');
        badge.textContent = asiento.asiento_estado;
        badge.className = 'badge bg-light text-dark';

        // Limpiar tabla de movimientos del modal y cargar los movimientos
        tbodyModalMovements.innerHTML = '';
        modalRowCounter = 1;

        if (Array.isArray(asiento.movimientos) && asiento.movimientos.length > 0) {
            asiento.movimientos.forEach(m => createModalMovementRow(m));
        }

        recalculateModalTotals();
        modalAsiento.show();
    }

    /**
     * Crear una fila de movimiento dentro de la grilla del modal
     */
    const createModalMovementRow = (data = {}) => {
        const rowId = modalRowCounter++;
        const tr = document.createElement('tr');
        tr.className = 'modal-mov-row';
        tr.dataset.modalRowId = rowId;

        const defaultGlosa = data?.glosa || $('#modal-asiento-glosa').val().toUpperCase() || '';
        const defaultDebe = data?.debe !== undefined ? data.debe : 0;
        const defaultHaber = data?.haber !== undefined ? data.haber : 0;

        //auxiliares
        const auxiliares = data?.auxiliares.length > 0 ?? false;

        tr.innerHTML = `
            <td class="text-center align-middle">
                <span class="badge bg-light text-secondary border modal-row-number">0</span>
            </td>
            <td>
                <div class="input-group input-group-sm input-account-group">
                    <input type="text" class="form-control form-control-sm modal-input-codigo" 
                           placeholder="Código" value="${data?.cuenta?.num_cuenta}" list="list-cuentas" maxlength="15" style="max-width: 85px; font-weight: 600;" readonly>
                    <input type="text" class="form-control form-control-sm modal-input-nombre bg-light" 
                           placeholder="Nombre cuenta" value="${data?.cuenta?.nombre}" readonly>
                </div>
            </td>
            <td>
                <input type="text" class="form-control form-control-sm modal-input-glosa py-1" placeholder="Detalle línea" value="${defaultGlosa}" readonly>
            </td>
            <td>
                <input type="text" class="form-control form-control-sm input-currency input-debe py-1 modal-input-debe" 
                       placeholder="0" value="${defaultDebe > 0 ? formatMoney(defaultDebe) : ''}" readonly>
            </td>
            <td>
                <input type="text" class="form-control form-control-sm input-currency input-haber py-1 modal-input-haber" 
                       placeholder="0" value="${defaultHaber > 0 ? formatMoney(defaultHaber) : ''}" readonly>
            </td>
            <td class="text-center align-middle">
                ${auxiliares ? `<button class="btn btn-outline-secondary btn-view-aux" type="button" title="Ver auxiliar" data-id="${data.id}">
                    <i class="bi bi-person"></i>
                </button>` : ''}
            </td>
        `;

        // setupModalRowEvents(tr);
        tbodyModalMovements.appendChild(tr);
        renumberModalRows();
        recalculateModalTotals();

        return tr;
    }

    const renumberModalRows = () => {
        const rows = tbodyModalMovements.querySelectorAll('tr');
        rows.forEach((r, idx) => {
            const numBadge = r.querySelector('.modal-row-number');
            if (numBadge) numBadge.textContent = idx + 1;
        });
    }

    /**
     * Recalcular totales y estado de balance dentro del modal
     */
    const recalculateModalTotals = () => {
        let sumDebe = 0;
        let sumHaber = 0;

        const rows = tbodyModalMovements.querySelectorAll('tr');
        rows.forEach(r => {
            sumDebe += parseMoney(r.querySelector('.modal-input-debe')?.value);
            sumHaber += parseMoney(r.querySelector('.modal-input-haber')?.value);
        });

        const diff = sumDebe - sumHaber;

        modalTotalDebe.textContent = formatMoney(sumDebe);
        modalTotalHaber.textContent = formatMoney(sumHaber);
        modalDiferencia.textContent = formatMoney(diff);

        if (sumDebe === 0 && sumHaber === 0) {
            modalStatusPill.className = 'status-pill bg-secondary text-white';
            modalStatusPill.innerHTML = '<i class="bi bi-circle"></i> SIN MONTOS';
        } else if (diff === 0) {
            modalStatusPill.className = 'status-pill balanced';
            modalStatusPill.innerHTML = '<i class="bi bi-check-circle-fill"></i> ASIENTO CUADRADO';
        } else {
            modalStatusPill.className = 'status-pill unbalanced';
            modalStatusPill.innerHTML = `<i class="bi bi-exclamation-triangle-fill"></i> DESCUADRADO (${formatMoney(diff)})`;
        }
    }


    //capturar click btn ver aux
    document.addEventListener('click', (e) => {
        if(e.target && e.target.closest('.btn-view-aux')) {
            e.preventDefault();
            const target = e.target.closest('.btn-view-aux');
            const idMovimiento = Number(target.dataset.id);

            // //buscar los auxiliares
            // 1. Buscar el movimiento
            const movimientoEncontrado = asientosContables
                .flatMap(asiento => asiento.movimientos || []) // Aplana todos los movimientos de todos los asientos en una sola lista
                .find(movimiento => movimiento.id === idMovimiento);

            // 2. Obtener auxiliares o asignar un array vacío si no existe
            const auxiliares = movimientoEncontrado.auxiliares;

            if(auxiliares.length > 0) {
                viewAux(auxiliares);
            }
        }
    })

    //cargar aux en tbl y abrir modal
    const viewAux = (data) => {
        if (data.length == 0 || data == null) {
            return
        }

        if ($.fn.DataTable.isDataTable('#tabla-view-auxiliares-modal')) {
            dataTableViewAux.destroy();
        }

        dataTableViewAux = $('#tabla-view-auxiliares-modal').DataTable({
            data: data,
            responsive: false,
            pageLength: 10,
            lengthMenu: [[10, 25, 50, 100], [10, 25, 50, 100]],
            order: [[1, 'asc']],
            language: {
                search: "_INPUT_",
                searchPlaceholder: "Buscar en DataTables...",
                lengthMenu: "Mostrar registros _MENU_",
                info: "Mostrando _START_ a _END_ de _TOTAL_ asientos",
                infoEmpty: "Mostrando 0 a 0 de 0 asientos",
                infoFiltered: "(filtrado de _MAX_ registros totales)",
                zeroRecords: "No se encontraron asientos contables coincidentes",
                paginate: {
                    first: "«",
                    previous: "‹",
                    next: "›",
                    last: "»"
                }
            },
            columns: [
                { data: 'rut' },
                { data: 'nombre_persona' },
                { data: 'monto',
                    render: function (data) {
                        return `${formatMoney(data)}`;
                    }
                 },
            ],
            initComplete: function () {
                $('#modal-view-aux').modal('show');
            }
        });
    }



    //ver origen
    const viewOrigen = (deposito, app) => {
        // 1. Encabezado del modal
        document.getElementById('modal-proc-deposito-num').textContent = deposito.voucher_number;;
        document.getElementById('modal-proc-fecha').textContent = deposito.date;
        document.getElementById('modal-proc-nombre').textContent = app.proceso.descripcion;
        document.getElementById('modal-proc-glosa').textContent = deposito.description;
        document.getElementById('modal-proc-monto').textContent = `${formatMoney(app.amount)}`;

        // Metadatos
        document.getElementById('modal-proc-tercero').textContent = app.proceso.descripcion;
        document.getElementById('modal-proc-tercero-id').textContent = deposito.voucher_number;
        document.getElementById('modal-proc-socio').textContent = app.person;
        document.getElementById('modal-proc-socio-detalle').textContent = formatRUT(app.rut);
        // document.getElementById('modal-proc-module').textContent = data.origen.module;
        document.getElementById('modal-proc-usuario').textContent = deposito.user_create;
        document.getElementById('modal-proc-creado').textContent = app.objeto_afectado.created_at;

        // 4. Documentos y Respaldo Adjuntos
        const containerAdjuntos = document.getElementById('modal-proc-adjuntos-list');
        let adjuntosHtml = '';

        adjuntosHtml += `
                <div class="attachment-preview-card">
                    <div class="d-flex align-items-center gap-3 overflow-hidden">
                        <div class="attachment-icon-box bg-danger-subtle text-danger border border-danger-subtle shadow-sm">
                            <i class="bi bi-file-earmark-pdf-fill"></i>
                        </div>
                        <div class="overflow-hidden">
                            <div class="fw-bold text-dark fs-sm text-truncate" title="Comprobante Proceso">
                                Comprobante Proceso
                            </div>
                        </div>
                    </div>
                    <div class="d-flex align-items-center gap-1 flex-shrink-0">
                        <button type="button" class="btn btn-primary btn-sm py-1 px-2 d-flex align-items-center gap-1 btn-print" data-id="${app.id}">
                            <i class="bi bi-download"></i> Descargar
                        </button>
                    </div>
                </div>`;

        containerAdjuntos.innerHTML = adjuntosHtml;

        if (modalProceso) {
            modalProceso.show();
        }
    }

    const abrirModalAdjuntos = (dep) => {
        depositosState.depositoSeleccionado = dep;

        const modalEl = document.getElementById('modal-ver-adjuntos');
        const container = document.getElementById('contenedor-galeria-adjuntos');
        const titleFolio = document.getElementById('adjuntos-folio-title');
        const titleSocio = document.getElementById('adjuntos-socio-title');

        if (!modalEl || !container) return;

        if (titleFolio) titleFolio.textContent = dep.voucher_number;
        if (titleSocio) titleSocio.textContent = `${dep.person} (${formatRUT(dep.rut)}) — Fecha: ${dep.date}`;

        const adjuntos = dep.documents || [];

        if (adjuntos.length === 0) {
            Swal.fire({
                icon: 'warning',
                title: 'Sin documentos adjuntos',
                text: 'Esta operación no posee vouchers o comprobantes anexados en el registro.',
            })
            return;
        } else {
            let html = '';
            adjuntos.forEach((file, idx) => {
                let previewThumb = '';
                if (file.file_type == 'image/jpeg' && file.url) {
                    previewThumb = `
                        <img src="${file.url}" alt="${file.name}" class="attachment-thumb-img shadow-sm" 
                            onclick="abrirModalZoomImagen('${file.url}', '${file.name}')" title="Clic para ampliar voucher">
                    `;
                } else if (file.file_type == 'application/pdf') {
                    previewThumb = `
                        <div class="attachment-icon-box bg-danger-subtle text-danger border border-danger-subtle shadow-sm">
                            <i class="bi bi-file-earmark-pdf-fill"></i>
                        </div>
                    `;
                } else {
                    previewThumb = `
                        <div class="attachment-icon-box bg-secondary-subtle text-secondary border border-secondary-subtle shadow-sm">
                            <i class="bi bi-file-earmark-text"></i>
                        </div>
                    `;
                }

                html += `
                <div class="attachment-preview-card mb-3">
                    <div class="d-flex align-items-center gap-3 overflow-hidden">
                        ${previewThumb}
                        <div class="overflow-hidden">
                            <div class="fw-bold text-dark fs-sm text-truncate" title="${file.name}">
                                ${file.name}
                            </div>
                            <div class="text-muted fs-xs mt-1">
                                <span><i class="bi bi-hdd-network me-1"></i>${formatBytes(file.size)}</span>
                                <span class="mx-1">•</span>
                            </div>
                            <span class="badge bg-light text-secondary border fs-xs mt-1">
                                ${file.file_type == 'application/pdf' ? 'Documento PDF Digital' : 'Comprobante / Voucher Gráfico'}
                            </span>
                        </div>
                    </div>

                    <div class="d-flex align-items-center gap-2 flex-shrink-0">
                        ${file.file_type == 'image/jpeg' && file.url ? `
                            <button type="button" class="btn btn-outline-primary btn-sm py-1 px-3 d-flex align-items-center gap-1"
                                    onclick="abrirModalZoomImagen('${file.url}', '${file.name}')">
                                <i class="bi bi-zoom-in"></i> Ver en Grande
                            </button>
                        ` : ''}
                        <a href="${file.url || '#'}" download="${file.name}" target="_blank" 
                            class="btn btn-primary btn-sm py-1 px-3 d-flex align-items-center gap-1 ${!file.url ? 'disabled' : ''}">
                            <i class="bi bi-download"></i> Descargar
                        </a>
                    </div>
                </div>
                `;
            });
            container.innerHTML = html;
        }

        const modal = new bootstrap.Modal(modalEl);
        modal.show();
    }

    //btn print
    document.addEventListener('click', (e) => {
        if (e.target && e.target.closest('.btn-print')) {
            e.preventDefault();
            const target = e.target.closest('.btn-print');
            generatePdf(target.dataset.id);
        }
    })

    // gerenar pdf 
    const generatePdf = async (data) => {
        Swal.showLoading();
        try {
            const response = await fetch(`/depositos/comprobante-app/pdf/${parseInt(data)}/`, {
                method: 'GET',
                headers: {
                    'Content-Type': "application/json",
                    'X-CSRFToken': csrftoken,
                    'X-App-Request': 'true'
                },
            })

            if (!response.ok) {
                throw new Error("No fue posible generar el PDF.");
            }

            const blob = await response.blob();
            const pdfUrl = URL.createObjectURL(blob);
            Swal.close();
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


    //limpiar filtros
    document.addEventListener('click', (e) => {
        if (e.target && e.target.closest('.btn-restablecer')) {
            e.preventDefault();
            resetearFiltros();
        }
    })

    /**
     * Restablece los filtros al estado por defecto
     */
    const resetearFiltros = () => {
        document.getElementById('input-busqueda-global').value = '';
        document.getElementById('btn-clear-global-search')?.classList.add('d-none');
        document.getElementById('filtro-tipo-proceso').value = 0;
        document.getElementById('filtro-fecha-desde').value = '';
        document.getElementById('filtro-fecha-hasta').value = '';
        document.getElementById('filtro-monto-min').value = '';
        document.getElementById('filtro-monto-max').value = '';

        depositosState.filtros = {
            query: '',
            tipoProceso: 0,
            fechaDesde: '',
            fechaHasta: '',
            montoMin: 0,
            montoMax: 0
        };
        depositosState.depositosData = [];
        depositosApp = [];
        asientosContables = [];
    }

    /**
     * Formatear número a moneda (2 decimales)
     */
    function formatMoney(amount) {
        const num = parseInt(amount) || 0;
        return num.toLocaleString('es-CL', { 
            style: 'currency',
            currency: 'CLP',
            minimumFractionDigits: 0,
            maximumFractionDigits: 0 });
    }

    /**
     * Formatear RUT Chileno con puntos y guión
     * Ejemplo: 154829147 -> 15.482.914-7
     */
    function formatRUT(rutStr) {
        if (!rutStr) return '';
        let clean = rutStr.replace(/[^0-9kK]/g, '').toUpperCase();
        if (clean.length < 2) return clean;
        let cuerpo = clean.slice(0, -1);
        let dv = clean.slice(-1);
        return cuerpo.replace(/\B(?=(\d{3})+(?!\d))/g, '.') + '-' + dv;
    }

    /**
     * Formatear bytes a tamaño legible (KB / MB)
     */
    function formatBytes(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }

    /**
     * Convertir texto formateado a número flotante
     */
    function parseMoney(val) {
        if (!val) return 0;
        if (typeof val === 'number') return isNaN(val) ? 0 : Math.round(val);
        
        // Remueve el símbolo $, puntos de miles, espacios y cualquier carácter no numérico excepto el signo menos (-)
        const cleaned = val.toString().replace(/[^0-9-]/g, '');
        const parsed = parseInt(cleaned, 10);
        
        return isNaN(parsed) ? 0 : parsed;
    }
})